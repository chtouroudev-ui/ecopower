from __future__ import annotations
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))


def test_incident_page_is_history_and_statistics_only():
    js=(ROOT/'static'/'live-views.js').read_text(encoding='utf-8')
    assert 'Historique des signalements' in js
    assert 'Incidents par agent' in js
    assert 'Distribution par type' in js and 'Distribution par jour' in js
    assert 'Intervalle maximal : 90 jours' in js
    # The Centre card now navigates to history instead of presenting an action workflow.
    assert 'Voir l’historique' in js
    slice_=js[js.index('async function liveIncidentsView'):]
    assert 'Gérer l’incident' not in slice_
    assert 'ACTION EN COURS' not in slice_


def test_incident_stats_are_agent_totals_and_distribution():
    import live_quality
    rows=[
        {'scope_type':'AGENT','scope_key':'1001','agent':'1001','agent_name':'Alice','category':'hold','triggered_at':100},
        {'scope_type':'AGENT','scope_key':'1001','agent':'1001','agent_name':'Alice','category':'hold','triggered_at':200},
        {'scope_type':'AGENT','scope_key':'1002','agent':'1002','agent_name':'Bob','category':'offline','triggered_at':300},
        {'scope_type':'GROUP','scope_key':'2','scope_label':'MED02','category':'other','triggered_at':400},
    ]
    stats=live_quality.incident_stats(rows)
    assert stats['total']==4 and stats['agent_incidents']==3 and stats['collective_incidents']==1
    alice=next(x for x in stats['agents'] if x['agent']=='1001')
    assert alice['total']==2 and alice['counts']['hold']==2
    assert {x['key']:x['count'] for x in stats['categories']}['hold']==2


def test_incident_period_is_bounded_to_90_days():
    from routes_collection import _incident_period
    a,b,lo,hi=_incident_period({'from':['2026-09-01'],'to':['2026-09-30']})
    assert (a,b)==('2026-09-01','2026-09-30') and hi>lo
    import pytest
    with pytest.raises(ValueError):_incident_period({'from':['2026-06-01'],'to':['2026-09-30']})
