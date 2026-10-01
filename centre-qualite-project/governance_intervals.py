"""Pure, second-precision interval helpers shared by Nelyio governance.

Ranges are half-open offsets [start, end) in seconds from an observed event.
The original event is never changed. Zero-duration logs are point observations:
a one-second matching probe is used, but it never creates a lost-time second.
"""
from datetime import datetime, timedelta
import math

from nelyio_time import local_datetime

CONTRACT_VERSION = 'V56-intervals-1'
ACTION_KEYS = ('exclude_statistics', 'exclude_lost_time', 'exclude_score', 'mark_authorized')


def observed_seconds(event):
    """Keep the existing integer-second API; reject negative/invalid durations."""
    try:
        return max(0, int(event.get('seconds') or 0))
    except (ValueError, TypeError, OverflowError):
        return 0


def event_datetime(event):
    """Prefer precise local display time over a coarse day/hour or raw epoch.

    Timestamp-only fallbacks use Nelyio business time, never the host timezone.
    Explicit offsets in ISO strings are normalized through the same helper.
    """
    text = str(event.get('start_text') or '').strip()
    if text:
        try:
            dt = datetime.fromisoformat(text.replace('Z', '+00:00'))
            if dt.tzinfo is not None:
                dt = local_datetime(dt.timestamp()).replace(tzinfo=None)
            return dt.replace(microsecond=0)
        except (ValueError, TypeError, OverflowError, OSError):
            pass
    day = str(event.get('day') or '')[:10]
    hour = str(event.get('hour') or '').strip().replace('h', ':')
    if hour.endswith(':'):
        hour += '00'
    if day and hour:
        try:
            return datetime.fromisoformat(day + ' ' + hour).replace(microsecond=0)
        except ValueError:
            pass
    start = event.get('start')
    if isinstance(start, (int, float)) and math.isfinite(start):
        try:
            return local_datetime(start).replace(tzinfo=None, microsecond=0)
        except (ValueError, OverflowError, OSError):
            pass
    return None


def event_bounds(event):
    start = event_datetime(event)
    if start is None:
        return None
    try:
        return start, start + timedelta(seconds=max(1, observed_seconds(event)))
    except OverflowError:
        return None


def merge_ranges(ranges):
    """Union valid ranges; overlaps and touching ends never double-count."""
    merged = []
    for lo, hi in sorted((a, b) for a, b in ranges if b > a):
        if merged and lo <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], hi)
        else:
            merged.append([lo, hi])
    return merged


def range_seconds(ranges):
    return sum(hi - lo for lo, hi in merge_ranges(ranges))


def subtract_ranges(ranges, removed):
    remaining = merge_ranges(ranges)
    for lo, hi in merge_ranges(removed):
        next_ranges = []
        for start, end in remaining:
            if hi <= start or lo >= end:
                next_ranges.append([start, end])
            else:
                if start < lo:
                    next_ranges.append([start, lo])
                if hi < end:
                    next_ranges.append([hi, end])
        remaining = next_ranges
    return remaining


def overlap_offsets(bounds, start, end):
    if not bounds or end <= start:
        return []
    origin, event_end = bounds
    lo, hi = max(origin, start), min(event_end, end)
    if hi <= lo:
        return []
    return [[int((lo - origin).total_seconds()), int((hi - origin).total_seconds())]]


def declaration_ranges(declaration, event):
    bounds = event_bounds(event)
    if not bounds:
        return []
    try:
        start = declaration.get('_start_dt') or datetime.strptime(str(declaration.get('start_at')), '%Y-%m-%d %H:%M:%S')
        end = declaration.get('_end_dt') or datetime.strptime(str(declaration.get('end_at')), '%Y-%m-%d %H:%M:%S')
        return overlap_offsets(bounds, start, end)
    except (ValueError, TypeError, OverflowError):
        return []


def time_minutes(text):
    if not text:
        return None
    try:
        h, m = map(int, str(text).split(':')[:2])
        if 0 <= h <= 23 and 0 <= m <= 59:
            return h * 60 + m
    except (ValueError, TypeError):
        pass
    return None


def policy_ranges(policy, event):
    """Intersect a recurring schedule with the event, including midnight.

    Date bounds are inclusive calendar dates. Overnight windows are attached to
    their start date/weekday (Thursday 23:00-01:00 includes Friday 00:30).
    Equal start/end retains the existing full-day interpretation.
    """
    bounds = event_bounds(event)
    if not bounds:
        return []
    start, end = bounds
    low = policy.get('_time_from_min') if '_time_from_min' in policy else time_minutes(policy.get('time_from'))
    high = policy.get('_time_to_min') if '_time_to_min' in policy else time_minutes(policy.get('time_to'))
    # Invalid persisted clocks must not accidentally authorize an entire day.
    if (policy.get('time_from') and low is None) or (policy.get('time_to') and high is None):
        return []
    low = 0 if low is None else low
    high = 1440 if high is None else high
    weekdays = policy.get('_weekdays_set')
    if weekdays is None:
        weekdays = {int(x) for x in (policy.get('weekdays') or []) if str(x).isdigit()}
    date_from = str(policy.get('date_from') or '')[:10]
    date_to = str(policy.get('date_to') or '')[:10]
    overnight = high < low
    cursor = start.replace(hour=0, minute=0, second=0, microsecond=0)
    if overnight:
        cursor -= timedelta(days=1)
    result = []
    while cursor < end:
        day = cursor.strftime('%Y-%m-%d')
        if (not date_from or day >= date_from) and (not date_to or day <= date_to) and (not weekdays or cursor.weekday() in weekdays):
            if low == high:
                window_start, window_end = cursor, cursor + timedelta(days=1)
            else:
                window_start = cursor + timedelta(minutes=low)
                window_end = cursor + timedelta(minutes=high, days=int(overnight))
            result.extend(overlap_offsets(bounds, window_start, window_end))
        cursor += timedelta(days=1)
    return merge_ranges(result)


def summarize_actions(event, action_intervals):
    """A legacy exclude flag now means FULL coverage, not any overlap."""
    seconds = observed_seconds(event)
    if not any(action_intervals.values()):
        return dict(contract_version=CONTRACT_VERSION, observed_seconds=seconds,
                    exclude_statistics=False, exclude_lost_time=False,
                    exclude_score=False, mark_authorized=False,
                    action_intervals={}, excluded_seconds=0,
                    effective_seconds=seconds, statistics_effective_seconds=seconds,
                    score_effective_seconds=seconds, partially_excluded=False,
                    partially_authorized=False)
    probe_seconds = max(1, seconds)
    normalized = {}
    result = {'contract_version': CONTRACT_VERSION, 'observed_seconds': seconds}
    covered = {}
    for key in ACTION_KEYS:
        ranges = merge_ranges((max(0, lo), min(probe_seconds, hi)) for lo, hi in action_intervals.get(key, ()))
        if ranges:
            normalized[key] = ranges
        length = sum(hi - lo for lo, hi in ranges)
        covered[key] = min(seconds, length)
        result[key] = length >= probe_seconds
    excluded = covered['exclude_lost_time']
    result.update(
        action_intervals=normalized,
        excluded_seconds=excluded,
        effective_seconds=seconds - excluded,
        statistics_effective_seconds=seconds - covered['exclude_statistics'],
        partially_excluded=0 < excluded < seconds,
        partially_authorized=0 < covered['mark_authorized'] < seconds,
    )
    score_ranges = normalized.get('exclude_score', []) + normalized.get('exclude_statistics', []) + normalized.get('exclude_lost_time', [])
    result['score_effective_seconds'] = seconds - min(seconds, range_seconds(score_ranges))
    return result


def attach_decision(out, prefix, decision):
    """Consistent public annotations for Policy, Declaration and Governance."""
    for key in ('exclude_statistics', 'exclude_lost_time', 'exclude_score'):
        out[prefix + '_' + key] = bool(decision[key])
    out[prefix + '_authorized'] = bool(decision['mark_authorized'])
    for key in ('observed_seconds', 'excluded_seconds', 'effective_seconds', 'statistics_effective_seconds', 'score_effective_seconds', 'partially_excluded', 'partially_authorized', 'contract_version'):
        out[prefix + '_' + key] = decision[key]
    return out
