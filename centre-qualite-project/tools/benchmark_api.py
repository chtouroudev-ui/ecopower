#!/usr/bin/env python3
"""Benchmark HTTP Nelyio with independent authenticated virtual users.

Credentials are read from environment variables by default and are never
written to the report: NELYIO_BENCH_USER / NELYIO_BENCH_PASSWORD.
"""
from __future__ import annotations
import argparse, concurrent.futures, http.cookiejar, json, os, ssl, statistics, time, urllib.error, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_ENDPOINTS=[
 ('quality','/api/quality/overview'),
 ('distribution','/api/quality/distributions'),
 ('diagnostic','/api/supervision/diagnostic-incidents'),
 ('calls','/api/supervision/calls'),
 ('groups','/api/groups/status'),
]

def client(base,user,password,insecure=False):
    jar=http.cookiejar.CookieJar();ctx=ssl._create_unverified_context() if insecure else ssl.create_default_context()
    op=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar),urllib.request.HTTPSHandler(context=ctx))
    data=json.dumps({'username':user,'password':password}).encode()
    req=urllib.request.Request(base+'/api/login',data=data,headers={'Content-Type':'application/json'},method='POST')
    with op.open(req,timeout=30) as r: json.loads(r.read())
    return op

def get(op,url,timeout):
    t=time.perf_counter();status=0;size=0;err=''
    try:
        with op.open(url,timeout=timeout) as r:
            status=r.status;body=r.read();size=len(body)
    except urllib.error.HTTPError as e:
        status=e.code;body=e.read();size=len(body);err=body[:240].decode('utf-8','replace')
    except Exception as e: err=f'{type(e).__name__}: {e}'
    return {'seconds':round(time.perf_counter()-t,4),'status':status,'bytes':size,'error':err}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--base-url',default='http://127.0.0.1:9051');ap.add_argument('--users',type=int,default=5)
    ap.add_argument('--rounds',type=int,default=3);ap.add_argument('--timeout',type=float,default=120);ap.add_argument('--insecure',action='store_true')
    ap.add_argument('--output',default='BENCHMARK_API_RUNTIME.json')
    args=ap.parse_args();base=args.base_url.rstrip('/')
    user=os.environ.get('NELYIO_BENCH_USER','');password=os.environ.get('NELYIO_BENCH_PASSWORD','')
    if not user or not password: raise SystemExit('Définir NELYIO_BENCH_USER et NELYIO_BENCH_PASSWORD dans l’environnement.')
    n=max(1,min(20,args.users));clients=[client(base,user,password,args.insecure) for _ in range(n)]
    # Warm-up sequential so measurements do not include first session/page initialization.
    for i,(_,path) in enumerate(DEFAULT_ENDPOINTS[:n]): get(clients[i],base+path,args.timeout)
    records=[]
    for rnd in range(max(1,args.rounds)):
        jobs=[]
        with concurrent.futures.ThreadPoolExecutor(max_workers=n) as ex:
            for i in range(n):
                label,path=DEFAULT_ENDPOINTS[i%len(DEFAULT_ENDPOINTS)]
                jobs.append((label,ex.submit(get,clients[i],base+path,args.timeout)))
            for label,f in jobs:
                row=f.result();row.update(round=rnd+1,scenario=label);records.append(row)
    summary={}
    for label,_ in DEFAULT_ENDPOINTS:
        vals=[r['seconds'] for r in records if r['scenario']==label and not r['error']]
        if vals: summary[label]={'count':len(vals),'median_s':round(statistics.median(vals),4),'max_s':round(max(vals),4)}
    report={'generated_at':datetime.now(timezone.utc).isoformat(),'base_url':base,'virtual_users':n,'rounds':args.rounds,'records':records,'summary':summary}
    Path(args.output).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2));print('Rapport :',args.output)

if __name__=='__main__': main()
