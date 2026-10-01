"""RC29 Phase 4 workforce helpers for Quality Distributions.

The configured population and observed evidence are deliberately separate:
- ACTIVE population comes only from configured ACTIVE queue assignments.
- expected/worked/not-worked are only asserted for days with Stats.AGENT coverage.
- pause is a DISTINCT-agent overlap count for each time bucket.
- positive work evidence never includes offline, pause, coaching or unknown-only rows.
"""
from __future__ import annotations

from collections import defaultdict


def expected_agents(scope, selected_groups=None, campaign='', agent=''):
    """Return the canonical configured ACTIVE population for a perimeter."""
    if selected_groups:
        base=set().union(*(set(g.get('member_agent_ids',[])) for g in selected_groups))
    else:
        base=set((scope.get('agent_files') or {}).keys())
    campaign=str(campaign or '').strip()
    if campaign:
        line_ids={int(x.get('line_id')) for x in (scope.get('campaign_to_files') or {}).get(campaign,[]) if x.get('line_id') is not None}
        if not line_ids:
            base=set()
        else:
            agent_files=scope.get('agent_files') or {}
            base={aid for aid in base if line_ids.intersection({int(x) for x in agent_files.get(aid,[])})}
    agent=str(agent or '').strip()
    if agent and agent!='__unassigned__':
        base={agent} if agent in base else set()
    elif agent=='__unassigned__':
        # An unassigned call row has no reliable configured workforce identity.
        base=set()
    return set(base)


def _overlaps(interval, start, end):
    a,b=interval
    return float(b)>float(start) and float(a)<float(end)


def bucket_status(population, work_intervals, pause_intervals, start, end):
    """Return per-bucket sets.

    Worked is cumulative within the selected day/window: once positive work
    evidence exists before bucket end, a later disconnection does not turn the
    agent into "not worked". Pause is an overlap-at-this-bucket measure.
    """
    population=set(population or ())
    worked=set()
    paused=set()
    for aid in population:
        if any(float(b)>float(a) and float(a)<float(end) for a,b in work_intervals.get(aid,())):
            worked.add(aid)
        if any(_overlaps(x,start,end) for x in pause_intervals.get(aid,())):
            paused.add(aid)
    return {
        'active':set(population),
        'expected':set(population),
        'worked':worked,
        'not_worked':population-worked,
        'pause':paused,
    }


def merge_intervals(target, aid, interval):
    a,b=interval
    if b<=a:return
    target[aid].append((float(a),float(b)))


def new_interval_map():
    return defaultdict(list)
