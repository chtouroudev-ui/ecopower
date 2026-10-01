"""Nelyio business-time helpers for Europe/Paris without external tz packages.

France follows EU daylight-saving rules: CET (UTC+1) in winter and CEST
(UTC+2) from the last Sunday in March at 01:00 UTC until the last Sunday in
October at 01:00 UTC. Nelyio uses this timezone for display and business-day
windows. Import parsing keeps its explicit source offset separately.
"""
from calendar import monthrange
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache

DISPLAY_TIMEZONE = "Europe/Paris"
WINTER_OFFSET_MINUTES = 60
SUMMER_OFFSET_MINUTES = 120
_WINTER_TZ = timezone(timedelta(minutes=WINTER_OFFSET_MINUTES))
_SUMMER_TZ = timezone(timedelta(minutes=SUMMER_OFFSET_MINUTES))


@lru_cache(maxsize=64)
def _last_sunday(year, month):
    last = date(year, month, monthrange(year, month)[1])
    return last - timedelta(days=(last.weekday() + 1) % 7)


@lru_cache(maxsize=32)
def _dst_utc_bounds(year):
    march = _last_sunday(year, 3)
    october = _last_sunday(year, 10)
    start = datetime(year, 3, march.day, 1, 0, tzinfo=timezone.utc)
    end = datetime(year, 10, october.day, 1, 0, tzinfo=timezone.utc)
    return start, end


def france_offset_for_utc_timestamp(ts):
    instant = datetime.fromtimestamp(float(ts), timezone.utc)
    start, end = _dst_utc_bounds(instant.year)
    return SUMMER_OFFSET_MINUTES if start <= instant < end else WINTER_OFFSET_MINUTES


def france_offset_for_local_datetime(local_dt):
    """Return the France offset for a naive local wall-clock datetime.

    Nelyio business windows never use the missing/ambiguous 02:xx transition
    hour. For completeness, the spring 02:xx hour is treated as winter time
    and the autumn 02:xx hour as summer time.
    """
    if local_dt.tzinfo is not None:
        local_dt = local_dt.replace(tzinfo=None)
    start_day = _last_sunday(local_dt.year, 3)
    end_day = _last_sunday(local_dt.year, 10)
    current = local_dt.date()
    if current < start_day or current > end_day:
        return WINTER_OFFSET_MINUTES
    if start_day < current < end_day:
        return SUMMER_OFFSET_MINUTES
    if current == start_day:
        return SUMMER_OFFSET_MINUTES if local_dt.hour >= 3 else WINTER_OFFSET_MINUTES
    return SUMMER_OFFSET_MINUTES if local_dt.hour < 3 else WINTER_OFFSET_MINUTES


def france_offset_for_day(day, hour=12):
    local_dt = datetime.strptime(str(day), "%Y-%m-%d").replace(hour=int(hour))
    return france_offset_for_local_datetime(local_dt)


def local_datetime(ts):
    instant = datetime.fromtimestamp(float(ts), timezone.utc)
    start, end = _dst_utc_bounds(instant.year)
    return instant.astimezone(_SUMMER_TZ if start <= instant < end else _WINTER_TZ)


def display(ts):
    dt = local_datetime(ts)
    return f"{dt.year:04d}-{dt.month:02d}-{dt.day:02d} {dt.hour:02d}:{dt.minute:02d}:{dt.second:02d}"


def local_day(ts):
    return local_datetime(ts).strftime("%Y-%m-%d")


def local_wall_timestamp(day, hour=0, minute=0, second=0):
    local_dt = datetime.strptime(str(day), "%Y-%m-%d").replace(
        hour=int(hour), minute=int(minute), second=int(second), microsecond=0
    )
    offset = france_offset_for_local_datetime(local_dt)
    return local_dt.replace(tzinfo=timezone(timedelta(minutes=offset))).timestamp()


def day_bounds(day, start_time=None, end_time=None):
    if start_time is None and end_time is None:
        start = local_wall_timestamp(day)
        next_day = (datetime.strptime(str(day), "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
        end = local_wall_timestamp(next_day)
        return start, end
    if not start_time or not end_time:
        raise ValueError("start_time and end_time are both required")
    sh, sm = [int(x) for x in str(start_time).split(":", 1)]
    eh, em = [int(x) for x in str(end_time).split(":", 1)]
    return local_wall_timestamp(day, sh, sm), local_wall_timestamp(day, eh, em)


def today():
    return local_day(datetime.now(timezone.utc).timestamp())
