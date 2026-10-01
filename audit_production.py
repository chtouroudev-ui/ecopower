"""Read-only quality audit on an existing runtime. No repair, import or purge.
python audit_production.py --date-from 2026-09-01 --date-to 2026-09-22 --json logs/audit_data.json
"""
from __future__ import annotations
import argparse,json,time
from datetime import date,timedelta
from pathlib import Path

def run(first='',last=''):
    from supervision_db import connect
    from quality_precision_check import run as check_day,latest_day
    first=first or latest_day();last=last or first
    if not first:raise ValueError('Aucune journée appels disponible; exactitude non vérifiable.')
    start,end=date.fromisoformat(first),date.fromisoformat(last)
    if not 0<=(end-start).days<=365:raise ValueError('Choisir 1 à 366 jours.')
    output={'date_from':first,'date_to':last,'read_only':True,'days':[],
            'scope':'Horaires de travail configurés, tous agents et campagnes',
            'limit':'Cohérence interne et anomalies source; ne remplace pas le rapprochement avec le rapport Hermes au même périmètre.'}
    def reference_state():
        with connect() as c:
            running=c.execute("SELECT COUNT(*) FROM import_jobs WHERE status='running'").fetchone()[0]
            refs=[tuple(r) for r in c.execute('''SELECT cc.day,cc.import_id,qi.digest,cov.import_id,qa.digest
                FROM call_coverage cc LEFT JOIN quality_inbound_imports qi ON qi.import_id=cc.import_id
                LEFT JOIN coverage cov ON cov.day=cc.day LEFT JOIN quality_agent_imports qa ON qa.import_id=cov.import_id
                WHERE cc.day BETWEEN ? AND ? ORDER BY cc.day''',(first,last))]
            settings=[tuple(r) for r in c.execute('SELECT key,value FROM settings ORDER BY key')]
        return running,refs,settings
    before=reference_state();running=before[0]
    output['import_running']=bool(running)
    for i in range((end-start).days+1):
        day=(start+timedelta(days=i)).isoformat();clock=time.perf_counter()
        try:r=check_day(day)
        except Exception as exc:r={'date':day,'ok':False,'error':str(exc)}
        r['elapsed_seconds']=round(time.perf_counter()-clock,3);output['days'].append(r)
    after=reference_state()
    output['stable_references']=before==after
    output['ok']=not running and not after[0] and output['stable_references'] and all(r['ok'] for r in output['days'])
    return output

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--date-from',default='');p.add_argument('--date-to',default='');p.add_argument('--json',type=Path)
    args=p.parse_args()
    try:result=run(args.date_from,args.date_to)
    except Exception as exc:result={'ok':False,'error':str(exc)}
    if args.json:
        args.json.parent.mkdir(parents=True,exist_ok=True)
        args.json.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    if result.get('error'):print('NON VALIDE - '+result['error'])
    for row in result.get('days',[]):
        s=row.get('service',{})
        print(('OK' if row['ok'] else 'NON VALIDE')+' - '+row['date']+' - traités='+str(s.get('handled'))+' - abandons='+str(s.get('abandoned'))+' - '+str(row['elapsed_seconds'])+'s')
    if result.get('import_running'):print('Import en cours: relancer après sa fin pour un rapprochement stable.')
    return 0 if result['ok'] else 1

if __name__=='__main__':raise SystemExit(main())
