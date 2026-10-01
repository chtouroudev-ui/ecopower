#!/usr/bin/env python3
"""Capture read-only EXPLAIN (ANALYZE, BUFFERS) plans for Nelyio hot paths."""
from __future__ import annotations
import argparse,json,os
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def env():
 p=ROOT/'data'/'postgres.env'
 if p.is_file():
  for raw in p.read_text(encoding='utf-8-sig').splitlines():
   line=raw.strip()
   if line and not line.startswith('#') and '=' in line:
    k,v=line.split('=',1);os.environ.setdefault(k.strip(),v.strip())

def explain(cur,label,sql,params):
 cur.execute('EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) '+sql,params)
 return {'label':label,'plan':cur.fetchone()[0]}

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--label',default='measurement');ap.add_argument('--output');args=ap.parse_args()
 env();dsn=os.environ.get('NELYIO_DATABASE_URL','').strip()
 if not dsn:raise SystemExit('NELYIO_DATABASE_URL absent')
 import psycopg
 out={'generated_at':datetime.now(timezone.utc).isoformat(),'label':args.label,'read_only':True,'plans':[]}
 with psycopg.connect(dsn,autocommit=True,connect_timeout=5) as con:
  with con.cursor() as cur:
   cur.execute("SET statement_timeout='120s'")
   cur.execute("SELECT day,import_id FROM supervision.call_coverage ORDER BY day DESC LIMIT 1");call=cur.fetchone()
   if call:
    day,imp=call;cur.execute('SELECT COALESCE(MIN(start),0),COALESCE(MAX(start),0)+1 FROM supervision.phone_calls WHERE import_id=%s',(imp,));lo,hi=cur.fetchone()
    out['plans'].append(explain(cur,'calls_latest_day_page',
      'SELECT call_id,indice,start,ani,dnis,first_agent,last_agent,campaign,end_reason FROM supervision.phone_calls WHERE import_id=%s AND start>=%s AND start<%s ORDER BY start DESC,call_id DESC LIMIT 100',(imp,lo,hi)))
    out['plans'].append(explain(cur,'calls_latest_day_anomalies',
      "SELECT call_id,start,end_reason,duration,conversation,wait FROM supervision.phone_calls WHERE import_id=%s AND start>=%s AND start<%s AND (COALESCE(end_reason,'') NOT IN ('','0') OR duration<0 OR conversation<0 OR wait<0)",(imp,lo,hi)))
    cur.execute("SELECT ani FROM supervision.phone_calls WHERE import_id=%s AND start>=%s AND start<%s AND COALESCE(ani,'')<>'' LIMIT 1",(imp,lo,hi));sample=cur.fetchone()
    if sample:
     digits=''.join(ch for ch in str(sample[0] or '') if ch.isdigit())[-6:]
     if digits:
      out['plans'].append(explain(cur,'calls_ani_partial',
       "SELECT call_id,indice,start,ani,last_agent FROM supervision.phone_calls WHERE import_id=%s AND start>=%s AND start<%s AND regexp_replace(COALESCE(ani,''),'[^0-9]','','g') LIKE %s ORDER BY start DESC LIMIT 100",(imp,lo,hi,'%'+digits+'%')))
   out['plans'].append(explain(cur,'active_activity_roster',
     "SELECT DISTINCT ON (a.agent) a.agent,a.name FROM supervision.activities a WHERE a.import_id=(SELECT import_id FROM supervision.coverage ORDER BY day DESC LIMIT 1) AND TRIM(COALESCE(a.agent,''))<>'' AND a.agent<>'0' ORDER BY a.agent,a.id DESC",()))
   cur.execute("SELECT day,import_id FROM supervision.call_coverage ORDER BY day DESC LIMIT 1");q=cur.fetchone()
   if q:
    qday,qimp=q
    out['plans'].append(explain(cur,'quality_inbound_latest_day',
      'SELECT campaign,COUNT(*) received,SUM(answered) answered,SUM(abandoned) abandoned FROM supervision.quality_inbound_facts WHERE import_id=%s AND day=%s GROUP BY campaign',(qimp,qday)))
   cur.execute("SELECT day,source_import_id FROM details.active_days WHERE source_kind='export' ORDER BY day DESC LIMIT 1");detail_ref=cur.fetchone()
   if detail_ref:
    detail_day,detail_import=detail_ref
    bounds=cur.execute("SELECT EXTRACT(EPOCH FROM (%s::date + time '08:00') AT TIME ZONE 'Europe/Paris'), EXTRACT(EPOCH FROM (%s::date + time '19:00') AT TIME ZONE 'Europe/Paris')",(detail_day,detail_day)).fetchone()
    out['plans'].append(explain(cur,'details_latest_export_page',
      "SELECT id,event_uid,start,end,agent,client,state,kind FROM details.detail_events WHERE event_source='export' AND source_import_id=%s AND start<%s AND \"end\">%s ORDER BY start DESC,id DESC LIMIT 100",(detail_import,float(bounds[1]),float(bounds[0]))))
 path=Path(args.output or (ROOT/'logs'/f'explain_{args.label}.json'));path.parent.mkdir(parents=True,exist_ok=True)
 path.write_text(json.dumps(out,ensure_ascii=False,indent=2,default=str),encoding='utf-8');print('Plans écrits :',path)
if __name__=='__main__':main()
