"""Isolated synthetic benchmark for Phase 4 campaign aggregation.

Never reads production databases. Run: python live_campaigns_phase4_benchmark.py
"""
from __future__ import annotations
import json, os, statistics, tempfile, time
from datetime import date, timedelta
from pathlib import Path

os.environ['NELYIO_FORCE_SQLITE']='1'
os.environ['NELYIO_SKIP_STARTUP_DETAILS_SYNC']='1'

from quality_reference_20260901_test import _install_isolated_runtime


def run():
    with tempfile.TemporaryDirectory(prefix='nelyio-phase4-bench-') as td:
        tmp=Path(td);_install_isolated_runtime(tmp)
        import quality_service
        import supervision_db
        from supervision_db import connect
        from quality_metrics import ensure_schema
        from nelyio_time import day_bounds, local_wall_timestamp

        quality={
            'source_type':'imported','source_label':'Phase4 synthetic','source_day':'2026-09-25','updated_at':'2026-09-25T15:00:00Z',
            'campaigns':[{'campaign_id':f'C{i:02d}','campaign_name':f'Campaign {i:02d}'} for i in range(30)],
            'queues':[], 'agents':[], 'observations':[],'scope_sources':{'agent_queues':{'day':'2026-09-25'}}
        }
        for i in range(30):
            for j in range(2):
                quality['queues'].append({'line_id':7000+i*2+j,'line_name':f'File {i:02d}-{j+1}','campaign_ids':[f'C{i:02d}']})
        for a in range(114):
            camp=a%30
            quality['agents'].append({'agent_id':str(1000+a),'queues':[{'line_id':7000+camp*2+(a%2),'line_name':'Synthetic','activation_state':'active','assignment_source':'configuration'}]})
        quality_service.QUALITY_DATA_FILE.parent.mkdir(parents=True,exist_ok=True)
        quality_service.QUALITY_DATA_FILE.write_text(json.dumps(quality),encoding='utf-8')

        supervision_db.init()
        target=date(2026,9,25)
        days=[target-timedelta(days=7*i) for i in range(5)]
        with connect() as c:
            ensure_schema(c)
            rid=1
            call_rows=[];detail_rows=[]
            for d in reversed(days):
                day=d.isoformat();lo,_=day_bounds(day,'08:00','19:00')
                c.execute('INSERT OR REPLACE INTO call_coverage(day,import_id) VALUES(?,?)',(day,rid))
                c.execute('INSERT OR REPLACE INTO quality_inbound_imports(import_id,digest,version,rows_count,source) VALUES(?,?,?,?,?)',(rid,f'd{rid}',2,12000,'synthetic'))
                facts=[]
                for i in range(12000):
                    camp=i%30;agent=str(1000+(i%114)) if i%7 else '0';abandon=int(agent=='0');wait=float((i*7)%240);stamp=lo+60+(i%600)*60
                    facts.append((rid,i+1,day,stamp,f'C{camp:02d}',f'Campaign {camp:02d}',agent,1,int(agent!='0'),abandon,0,0,0,0,0,wait,0,'{}',0,90.0))
                    if d==target:
                        call_id=f'{rid}-{i}';line=str(7000+camp*2+(i%2))
                        call_rows.append((rid,call_id,str(i),stamp,'1',90.0,70.0,wait,'','','','',agent,agent,f'C{camp:02d}','0',int(agent=='0'),abandon,0,int(agent!='0')))
                        detail_rows.append((rid,call_id,90.0,wait,wait,line,line,f'C{camp:02d}',f'C{camp:02d}',''))
                c.executemany('''INSERT INTO quality_inbound_facts(import_id,row_number,day,start,campaign,campaign_name,agent,received,answered,abandoned,closed,overflow,rerouted,before_queue,transferred,wait,invalid_duration,payload,lost,call_duration) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',facts)
                rid+=1
            c.executemany('INSERT INTO phone_calls VALUES('+','.join('?'*20)+')',call_rows)
            c.executemany('INSERT INTO phone_call_details VALUES('+','.join('?'*10)+')',detail_rows)

        import db_compat
        original=db_compat.connect;queries=[]
        def traced(*args,**kwargs):
            con=original(*args,**kwargs);con.set_trace_callback(queries.append);return con
        db_compat.connect=traced
        try:
            import live_campaigns
            clock=local_wall_timestamp(target.isoformat(),15,0)
            times=[];counts=[];last=None
            for _ in range(7):
                queries.clear();t=time.perf_counter();last=live_campaigns.historical_view({},clock=clock);times.append(time.perf_counter()-t);counts.append(len([q for q in queries if q.lstrip().upper().startswith('SELECT')]))
            return {
                'rows_per_day':12000,'campaigns':30,'reference_days':4,
                'median_seconds':round(statistics.median(times),4),'p95_seconds':round(sorted(times)[-1],4),
                'select_statements_median':int(statistics.median(counts)),
                'campaigns_today':len(last['today']['campaigns']),
                'bounded_plan':last['query_plan'],
            }
        finally:
            db_compat.connect=original

if __name__=='__main__':
    print(json.dumps(run(),ensure_ascii=False,indent=2))
