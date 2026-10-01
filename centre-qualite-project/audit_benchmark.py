"""Synthetic, isolated SQLite benchmark. Never opens the installed runtime DBs.
python audit_benchmark.py --json benchmark.json
"""
import argparse,json,os,shutil,subprocess,sys,tempfile,time,statistics
from pathlib import Path

def worker(root):
    os.environ['NELYIO_FORCE_SQLITE']='1';os.environ['NELYIO_SKIP_STARTUP_DETAILS_SYNC']='1'
    import sqlite3
    from datetime import date,timedelta
    from concurrent.futures import ThreadPoolExecutor
    from nelyio_time import day_bounds
    c=sqlite3.connect(root/'NELYIO_Supervision.db')
    facts=[];activity=[];phone=[];support_activity=[];activity_id=1
    for i in range(30):
        day=(date(2026,8,1)+timedelta(days=i)).isoformat();lo,_=day_bounds(day,'09:00','19:00');ident=i+1
        c.execute('INSERT OR REPLACE INTO call_coverage VALUES(?,?)',(day,ident))
        c.execute('INSERT OR REPLACE INTO coverage VALUES(?,?)',(day,ident))
        c.execute('INSERT OR REPLACE INTO imports(id,digest,name,imported_at,imported_by,rows_count,offset_minutes,reference_day) VALUES(?,?,?,?,?,?,?,?)',(ident,'synthetic-'+str(ident),'synthetic.zip','2026-09-24','benchmark',50,120,day))
        c.execute('INSERT OR REPLACE INTO call_imports(import_id,rows_count) VALUES(?,?)',(ident,2000))
        c.execute('INSERT OR REPLACE INTO quality_inbound_imports(import_id,digest,version,rows_count,source) VALUES(?,?,?,?,?)',(ident,'synthetic',2,2000,'synthetic'))
        c.execute('INSERT OR REPLACE INTO quality_agent_imports VALUES(?,?,?,?,?)',(ident,'synthetic',50,0,0))
        for j in range(2000):
            treated=(j%5!=0);agent=str(1000+j%50) if treated else '0';stamp=lo+j
            facts.append((ident,j,day,stamp,'A','Synthetic',agent,1,int(treated),int(not treated),0,0,0,0,0,10,0,'{}',0))
            phone.append((ident,f'C{ident}-{j}',str(j%250),stamp,'IN',90.0,8.0 if j%250==0 else 70.0,10.0,'216000'+str(j%10000).zfill(4),'7111','','',agent,agent,'A','42' if j%300==0 else '0',0,int(not treated),0,1))
        for j in range(50):
            agent=str(1000+j);activity.append((ident,str(j),agent,'Agent '+str(j),lo,lo+28800,'work','A','',0))
            support_activity.append((activity_id,ident,agent,'Agent '+str(j),lo,lo+28800,'Pret','ready','A',''));activity_id+=1
            if j%10==0:
                support_activity.append((activity_id,ident,agent,'Agent '+str(j),lo+3600,lo+3630,'Déconnecté','offline','A',''));activity_id+=1
    cols={r[1] for r in c.execute('PRAGMA table_info(quality_inbound_facts)')}
    if 'lost' not in cols:c.execute('ALTER TABLE quality_inbound_facts ADD COLUMN lost INTEGER')
    c.executemany('''INSERT INTO quality_inbound_facts(
      import_id,row_number,day,start,campaign,campaign_name,agent,received,answered,abandoned,
      closed,overflow,rerouted,before_queue,transferred,wait,invalid_duration,payload,lost)
      VALUES('''+','.join('?'*19)+')',facts)
    c.executemany('INSERT INTO quality_agent_facts VALUES('+','.join('?'*10)+')',activity)
    c.executemany('INSERT INTO phone_calls VALUES('+','.join('?'*20)+')',phone)
    c.executemany('INSERT INTO activities(id,import_id,agent,name,start,end,state,kind,campaign,session) VALUES(?,?,?,?,?,?,?,?,?,?)',support_activity)
    c.commit();c.close()
    c=sqlite3.connect(root/'TECHIN_Stock_Manager.db')
    for j in range(50):c.execute('INSERT OR REPLACE INTO user_directory(user_key,user_identifier,first_name,last_name) VALUES(?,?,?,?)',(str(1000+j),str(1000+j),'Agent',str(j)))
    for g in range(5):
        c.execute('INSERT OR REPLACE INTO user_groups(id,name,description,created_by,updated_by) VALUES(?,?,?,?,?)',(g+1,'G'+str(g+1),'Synthetic','benchmark','benchmark'))
        for lid in (7100+2*g,7101+2*g):c.execute('INSERT OR REPLACE INTO quality_group_lines(group_id,line_id,created_by) VALUES(?,?,?)',(g+1,lid,'benchmark'))
    c.commit();c.close()
    quality={
      'source_type':'imported','source_label':'Synthetic configured assignments','source_day':'2026-08-30','updated_at':'2026-09-24T00:00:00Z',
      'campaigns':[],
      'queues':[{'line_id':7100+i,'line_name':'File '+str(i+1),'campaign_ids':[]} for i in range(10)],
      'agents':[{'agent_id':str(1000+j),'agent_first_name':'Agent','agent_last_name':str(j),'queues':[
          {'line_id':7100+(j%10),'line_name':'File '+str((j%10)+1),'activation_state':'active','assignment_source':'configuration'},
          {'line_id':7100+((j+1)%10),'line_name':'File '+str(((j+1)%10)+1),'activation_state':'active','assignment_source':'configuration'}
      ]} for j in range(50)],
      'observations':[], 'scope_sources':{'agent_queues':{'day':'2026-08-30'}}
    }
    (root/'data'/'quality_priorities.json').write_text(json.dumps(quality),encoding='utf-8')
    from quality_agents import view
    from quality_metrics import overview
    from quality_distributions import view as distribution
    from support_views import support_view,diagnostic_incidents_view
    from calls import calls_view
    from quality_service import load_quality_priorities,invalidate_quality_priorities_cache
    import group_workspace
    import db_compat
    original=db_compat.connect;queries=[]
    def traced(*a,**kw):
        con=original(*a,**kw);con.set_trace_callback(queries.append);return con
    db_compat.connect=traced
    scope={'date_from':['2026-08-01'],'date_to':['2026-08-30'],'time_from':['08:00'],'time_to':['19:00']}
    result={'backend':'SQLite isolé, données synthétiques','calls':60000,'agents':50,'days':30,'repetitions':5,'measurements':{}}
    for name,fn in [('quality_agents',view),('quality_service',overview),('distribution',distribution)]:
        values=[];counts=[]
        for _ in range(5):
            queries.clear();t=time.perf_counter();out=fn(scope);values.append(time.perf_counter()-t);counts.append(len(queries))
            actual=(out['summary']['handled'] if name=='quality_agents' else
                    out['total']['treated_agent'] if name=='quality_service' else out['total']['treated'])
            assert actual==48000
        result['measurements'][name]={'median_seconds':round(statistics.median(values),4),'sql_statements':int(statistics.median(counts))}
    for name,fn in [('support',support_view),('calls',calls_view),('diagnostic',diagnostic_incidents_view)]:
        values=[]
        for _ in range(3):
            t=time.perf_counter();out=fn(scope);values.append(time.perf_counter()-t)
        result['measurements'][name]={'median_seconds':round(statistics.median(values),4),'sql_statements':'instrumented_at_runtime'}
    priorities_cold=[]
    for _ in range(5):
        invalidate_quality_priorities_cache();group_workspace.invalidate_group_workspace_cache()
        t=time.perf_counter();catalog=load_quality_priorities();priorities_cold.append(time.perf_counter()-t)
        assert catalog['stats']['agents']==50 and catalog['stats']['queues']==100
    t=time.perf_counter();load_quality_priorities();priorities_warm=time.perf_counter()-t
    group_values=[]
    for _ in range(5):
        group_workspace.invalidate_group_workspace_cache()
        t=time.perf_counter();status=group_workspace.status();group_values.append(time.perf_counter()-t)
        assert status['stats']['agents']==50 and status['group_summary']['saved']==5
    result['measurements']['teams_files_priorities_cold']={'median_seconds':round(statistics.median(priorities_cold),4),'sql_statements':'instrumented_at_runtime'}
    result['measurements']['teams_files_priorities_warm']={'median_seconds':round(priorities_warm,4),'sql_statements':'cache_hit'}
    result['measurements']['groups_status']={'median_seconds':round(statistics.median(group_values),4),'sql_statements':'instrumented_at_runtime'}
    t=time.perf_counter()
    with ThreadPoolExecutor(max_workers=5) as pool:results=list(pool.map(lambda _:view(scope),range(5)))
    result['five_concurrent_agent_views_seconds']=round(time.perf_counter()-t,4)
    result['five_results_correct']=all(x['summary']['handled']==48000 for x in results)
    mixed=[('quality_agents',view),('distribution',distribution),('support',support_view),('calls',calls_view),('diagnostic',diagnostic_incidents_view)]
    t=time.perf_counter()
    with ThreadPoolExecutor(max_workers=5) as pool:
        mixed_results=[f.result() for f in [pool.submit(fn,scope) for _,fn in mixed]]
    result['five_mixed_views_seconds']=round(time.perf_counter()-t,4)
    result['five_mixed_views_ok']=all(isinstance(x,dict) for x in mixed_results)
    return result

def main():
    p=argparse.ArgumentParser();p.add_argument('--worker',action='store_true');p.add_argument('--json',type=Path);args=p.parse_args()
    root=Path(__file__).resolve().parent
    if args.worker:
        print(json.dumps(worker(root),ensure_ascii=False));return
    with tempfile.TemporaryDirectory(prefix='nelyio-benchmark-') as tmp:
        dest=Path(tmp)
        for path in root.glob('*.py'):shutil.copy2(path,dest/path.name)
        # Empty schema fixtures, supplied by this package. Never copy production data.
        import zipfile
        fixture=root/'audit_empty_schemas.zip'
        if not fixture.is_file():raise SystemExit('audit_empty_schemas.zip absent; benchmark annulé pour protéger les données de production.')
        with zipfile.ZipFile(fixture) as z:z.extractall(dest)
        (dest/'data').mkdir(exist_ok=True)
        run=subprocess.run([sys.executable,str(dest/'audit_benchmark.py'),'--worker'],capture_output=True,text=True)
        if run.returncode:raise SystemExit(run.stderr or run.stdout)
        result=json.loads(run.stdout)
    if args.json:args.json.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf8')
    print(json.dumps(result,indent=2,ensure_ascii=False))

if __name__=='__main__':main()
