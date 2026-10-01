"""Regression test for V6 agent handled-call ownership.

Stats.AGENT owns the per-agent handled count. Stats.INBOUND remains the
service-level source for answered/wait/call-duration fields. This reproduces
the transferred-call mismatch that motivated PATCH V6: 8 unique inbound
sessions for an agent while Stats.INBOUND contains only 7 final rows.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parent
os.environ['NELYIO_FORCE_SQLITE']='1'
os.environ['NELYIO_SKIP_STARTUP_DETAILS_SYNC']='1'
sys.path.insert(0,str(ROOT))

from quality_reference_20260901_test import _install_isolated_runtime


def run() -> dict:
    checks=[]
    with tempfile.TemporaryDirectory(prefix='nelyio-v6-agent-counts-') as td:
        tmp=Path(td);_install_isolated_runtime(tmp)
        import supervision_db
        from supervision_db import connect
        from quality_metrics import ensure_schema as ensure_quality_schema
        from quality_agents import ensure_schema as ensure_agent_schema, view
        from nelyio_time import day_bounds

        supervision_db.init()
        day='2026-09-18';lo,hi=day_bounds(day,'00:00','23:59')
        with connect() as c:
            ensure_quality_schema(c);ensure_agent_schema(c)
            c.execute('INSERT OR REPLACE INTO coverage(day,import_id) VALUES(?,?)',(day,1))
            c.execute('INSERT OR REPLACE INTO call_coverage(day,import_id) VALUES(?,?)',(day,1))
            c.execute("INSERT OR REPLACE INTO quality_inbound_imports(import_id,digest,version,rows_count,source) VALUES(?,?,?,?,?)",
                      (1,'v6-fixture',2,7,'Stats.INBOUND'))

            # Eight real inbound interactions for agent 1039. The ninth row
            # repeats S8 and must NOT create a ninth handled call.
            rows=[]
            for i in range(8):
                start=lo+3600+i*120
                rows.append((i+1,1,'1039','Agent 1039',start,start+60,'Inbound call','call','86652925',f'S{i+1}'))
            rows.append((9,1,'1039','Agent 1039',lo+3600+8*120,lo+3600+8*120+30,'Inbound call','call','86652925','S8'))
            c.executemany('INSERT INTO activities(id,import_id,agent,name,start,end,state,kind,campaign,session) VALUES(?,?,?,?,?,?,?,?,?,?)',rows)

            # Stats.INBOUND has only seven final rows for the agent/campaign.
            facts=[]
            for i in range(7):
                start=lo+3600+i*120
                facts.append((1,i+1,day,start,'86652925','CABINET NEOPHTA','1039',1,1,0,0,0,0,0,0,10.0,0,'{}',0,60.0))
            c.executemany('''INSERT INTO quality_inbound_facts(
                import_id,row_number,day,start,campaign,campaign_name,agent,
                received,answered,abandoned,closed,overflow,rerouted,before_queue,
                transferred,wait,invalid_duration,payload,lost,call_duration)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',facts)

        result=view({'date_from':[day],'date_to':[day],'time_from':['00:00'],'time_to':['23:59'],'agent':['1039']})
        row=next(r for r in result['rows'] if r['agent']=='1039')
        mapped=(row.get('distribution_exact') or 0)+(row.get('distribution_ambiguous') or 0)+(row.get('distribution_unmapped') or 0)
        checks.extend([
            {'name':'handled_from_stats_agent_sessions','ok':row.get('handled')==8,'actual':row.get('handled'),'expected':8},
            {'name':'answered_still_from_stats_inbound','ok':row.get('answered')==7,'actual':row.get('answered'),'expected':7},
            {'name':'distribution_uses_same_agent_counter','ok':mapped==8,'actual':mapped,'expected':8},
            {'name':'handled_source_declared','ok':result.get('handled_source')=='Stats.AGENT / Inbound call / SessionID unique','actual':result.get('handled_source'),'expected':'Stats.AGENT / Inbound call / SessionID unique'},
            {'name':'handled_compatible','ok':result.get('handled_compatible') is True,'actual':result.get('handled_compatible'),'expected':True},
            {'name':'short_calls_not_reintroduced_in_quality_agents','ok':'short_calls' not in row,'actual':'short_calls' in row,'expected':False},
        ])
        return {'ok':all(c['ok'] for c in checks),'checks':checks,'handled':row.get('handled'),'answered':row.get('answered')}


def test_v6_agent_handled_uses_stats_agent_sessions():
    result=run()
    assert result['ok'] is True, result


def main() -> int:
    r=run()
    print(('OK' if r['ok'] else 'ECHEC')+' - V6 Qualité agents / comptage interactions')
    for c in r['checks']:
        print(('OK' if c['ok'] else 'ECHEC'),'-',c['name'],':',c['actual'])
    return 0 if r['ok'] else 1

if __name__=='__main__':
    raise SystemExit(main())
