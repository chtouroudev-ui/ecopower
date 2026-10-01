"""RC2I validation for file-based group filters and Quality agents.

Usage:
  python quality_rc2i_test.py --zip /path/SIMPLIFY2.2026-09-01.export.zip

Runs only in temporary SQLite databases. Production databases are never opened.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parent
os.environ['NELYIO_FORCE_SQLITE']='1'
os.environ['NELYIO_SKIP_STARTUP_DETAILS_SYNC']='1'
sys.path.insert(0,str(ROOT))

from quality_reference_20260901_test import _install_isolated_runtime


def run(reference_zip: Path) -> dict:
    raw=reference_zip.read_bytes()
    checks=[]
    with tempfile.TemporaryDirectory(prefix='nelyio-rc2i-') as td:
        tmp=Path(td);_install_isolated_runtime(tmp)
        import sqlite3
        import quality_service
        from quality_importer import extract_snapshot,agent_key
        from quality_metrics import ingest_inbound,overview
        from quality_agents import ingest as ingest_agent,view as agent_view
        from quality_scope import invalidate_quality_scope_cache,load_quality_file_scope
        from supervision_db import connect

        snapshot=extract_snapshot(raw,reference_zip.name)
        if not snapshot:raise RuntimeError('Configuration Qualité absente de l export')
        quality_service.QUALITY_DATA_FILE.write_text(json.dumps(snapshot,ensure_ascii=False),encoding='utf-8')

        # Pick a real queue that has at least one campaign and one ACTIVE agent.
        active_by_line={}
        for a in snapshot.get('agents',[]):
            aid=agent_key(a.get('agent_id'))
            for q in a.get('queues',[]):
                state=str(q.get('activation_state') or '').lower()
                if state == 'active':
                    active_by_line.setdefault(int(q['line_id']),set()).add(aid)
        queue=next((q for q in snapshot.get('queues',[]) if q.get('campaign_ids') and active_by_line.get(int(q['line_id']))),None)
        if queue is None:raise RuntimeError('Aucune file testable avec campagne + agent actif')
        line_id=int(queue['line_id']);campaign_ids={str(x) for x in queue.get('campaign_ids',[])}

        # Create a group anchored ONLY by the queue. No campaign is stored on the group.
        db=sqlite3.connect(str(tmp/'TECHIN_Stock_Manager.db'))
        try:
            db.execute("INSERT INTO user_groups(id,name,description,created_by,updated_by) VALUES(?,?,?,?,?)",(9001,'RC2I FILE GROUP','test','audit','audit'))
            db.execute("INSERT INTO quality_group_lines(group_id,line_id,created_by) VALUES(?,?,?)",(9001,line_id,'audit'))
            db.commit()
        finally:db.close()
        invalidate_quality_scope_cache();scope=load_quality_file_scope(force=True)
        group=next(g for g in scope['groups'] if g['id']=='9001')
        checks += [
            dict(name='group_basis_files',ok=group['basis']=='configured_files',actual=group['basis'],expected='configured_files'),
            dict(name='group_has_one_file',ok=group['line_ids']==[line_id],actual=group['line_ids'],expected=[line_id]),
            dict(name='group_campaigns_derived_from_file',ok=set(group['campaign_ids'])==campaign_ids,actual=group['campaign_ids'],expected=sorted(campaign_ids)),
            dict(name='group_members_from_active_files',ok=set(group['member_agent_ids'])==active_by_line[line_id],actual=len(group['member_agent_ids']),expected=len(active_by_line[line_id])),
        ]

        ingest_inbound(raw,reference_zip.name,1,120)
        ingest_agent(raw,reference_zip.name,1,120)
        with connect() as con:
            from quality_rules import agent_unassigned_sql
            con.execute('INSERT OR REPLACE INTO call_coverage(day,import_id) VALUES(?,?)',('2026-09-01',1))
            con.execute('INSERT OR REPLACE INTO coverage(day,import_id) VALUES(?,?)',('2026-09-01',1))
            members=sorted(active_by_line[line_id]);parts=[];args=[]
            if members:
                parts.append('agent IN ('+','.join('?'*len(members))+')');args.extend(members)
            if campaign_ids:
                parts.append('('+agent_unassigned_sql('quality_inbound_facts')+' AND campaign IN ('+','.join('?'*len(campaign_ids))+'))');args.extend(sorted(campaign_ids))
            expected_group=con.execute("SELECT COUNT(*) FROM quality_inbound_facts WHERE day='2026-09-01' AND ("+' OR '.join(parts)+')',args).fetchone()[0]

        q=overview({'date_from':['2026-09-01'],'date_to':['2026-09-01'],'work_hours':['0'],'group':['9001']})
        checks.append(dict(name='service_group_filters_by_active_file_agents',ok=q['total']['received']==expected_group,actual=q['total']['received'],expected=expected_group))
        checks.append(dict(name='service_group_has_treated_agents',ok=(q['total']['treated_agent'] or 0)>0,actual=q['total']['treated_agent'],expected='>0'))
        checks.append(dict(name='service_group_basis_label',ok='Files' in q.get('group_basis',''),actual=q.get('group_basis'),expected='Files ...'))

        from quality_distributions import view as distribution_view
        dist=distribution_view({'date_from':['2026-09-01'],'date_to':['2026-09-01'],'time_from':['00:00'],'time_to':['23:59'],'group':['9001']})
        checks.append(dict(name='distribution_group_filters_by_active_file_agents',ok=dist['total']['received']==expected_group,actual=dist['total']['received'],expected=expected_group))
        checks.append(dict(name='distribution_group_has_treated_agents',ok=(dist['total']['treated'] or 0)>0,actual=dist['total']['treated'],expected='>0'))

        # Agent filter must be real server-side filtering, not a cosmetic UI filter.
        all_q=overview({'date_from':['2026-09-01'],'date_to':['2026-09-01'],'work_hours':['0']})
        candidate=next((a for a in sorted(all_q['agents'],key=lambda x:x['handled'],reverse=True) if a['handled']>0),None)
        if not candidate:raise RuntimeError('Aucun agent traité pour test')
        one=overview({'date_from':['2026-09-01'],'date_to':['2026-09-01'],'work_hours':['0'],'agent':[candidate['agent']]})
        checks.append(dict(name='service_agent_filter',ok=one['total']['treated_agent']==candidate['handled'],actual=one['total']['treated_agent'],expected=candidate['handled']))

        t0=time.perf_counter()
        qa=agent_view({'date_from':['2026-09-01'],'date_to':['2026-09-01'],'time_from':['00:00'],'time_to':['23:59']})
        elapsed=time.perf_counter()-t0
        checks.append(dict(name='agent_view_bulk_mode',ok=qa.get('performance_mode')=='bulk_queries',actual=qa.get('performance_mode'),expected='bulk_queries'))
        checks.append(dict(name='agent_view_integrity',ok=qa.get('integrity',{}).get('ok') is True,actual=qa.get('integrity',{}).get('ok'),expected=True))
        visible_avg={r['agent'] for r in qa['rows'] if r.get('call_average') is not None}
        with connect() as con:
            source_avg={agent_key(r[0]) for r in con.execute("SELECT DISTINCT agent FROM quality_agent_facts WHERE kind='inbound' AND end>start")}
        checks.append(dict(name='call_average_visible',ok=len(visible_avg)>0,actual=len(visible_avg),expected='>0'))
        missing_avg=sorted(source_avg-visible_avg)
        checks.append(dict(name='all_inbound_agents_have_call_average',ok=not missing_avg,actual=missing_avg[:10],expected=[]))
        bad_days=[r['agent'] for r in qa['rows'] if ((r.get('handled') or 0)>0 or (r.get('presence_seconds') or 0)>0 or (r.get('disconnected_seconds') or 0)>0) and r.get('worked_days')!=1]
        checks.append(dict(name='active_day_if_any_data',ok=not bad_days,actual=bad_days[:10],expected=[]))
        bad_distribution=[r['agent'] for r in qa['rows'] if r.get('handled') is not None and (r['distribution_exact']+r['distribution_ambiguous']+r['distribution_unmapped'])!=r['handled']]
        checks.append(dict(name='file_distribution_conserves_calls',ok=not bad_distribution,actual=bad_distribution[:10],expected=[]))
        checks.append(dict(name='agent_view_runtime_smoke',ok=elapsed<15,actual=round(elapsed,3),expected='<15s on one-day reference fixture'))

        # Group membership in agent view must be derived from configured files.
        qag=agent_view({'date_from':['2026-09-01'],'date_to':['2026-09-01'],'time_from':['00:00'],'time_to':['23:59'],'group':['9001']})
        returned={r['agent'] for r in qag['rows']}
        checks.append(dict(name='agent_group_membership_from_files',ok=returned.issubset(active_by_line[line_id]),actual=len(returned),expected=f'only {len(active_by_line[line_id])} file members'))

        return {
            'ok':all(c['ok'] for c in checks),
            'queue_tested':{'line_id':line_id,'campaigns':sorted(campaign_ids),'active_agents':len(active_by_line[line_id])},
            'agent_view':{'rows':len(qa['rows']),'call_average_visible_agents':sum(r.get('call_average') is not None for r in qa['rows']),'elapsed_seconds':elapsed},
            'checks':checks,
        }


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--zip',type=Path,required=True);ap.add_argument('--json',type=Path)
    args=ap.parse_args()
    try:r=run(args.zip)
    except Exception as exc:r={'ok':False,'error':f'{type(exc).__name__}: {exc}'}
    if args.json:args.json.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
    if r.get('error'):
        print('ECHEC -',r['error']);return 1
    print(('OK' if r['ok'] else 'ECHEC')+' - RC2I Qualité / files / agents')
    print('File test:',r['queue_tested'])
    print('Vue agents:',r['agent_view'])
    for c in r['checks']:
        print(('OK' if c['ok'] else 'ECHEC'),'-',c['name'],':',c.get('actual'))
    return 0 if r['ok'] else 1

if __name__=='__main__':raise SystemExit(main())
