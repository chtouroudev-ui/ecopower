#!/usr/bin/env python3
"""Summarize a browser HAR by endpoint without retaining query parameters."""
from __future__ import annotations
import argparse,json,statistics
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlsplit
ap=argparse.ArgumentParser();ap.add_argument('har');ap.add_argument('--output');args=ap.parse_args()
data=json.loads(Path(args.har).read_text(encoding='utf-8-sig'))
groups=defaultdict(list)
for e in data.get('log',{}).get('entries',[]):
    req=e.get('request',{});url=req.get('url','');path=urlsplit(url).path;method=req.get('method','GET')
    t=float(e.get('time') or 0);tim=e.get('timings') or {};wait=float(tim.get('wait') or 0)
    resp=e.get('response') or {};content=resp.get('content') or {};body=int(resp.get('bodySize') or 0); csize=int(content.get('size') or 0); size=body if body>0 else csize
    groups[(method,path)].append({'ms':t,'wait_ms':wait,'bytes':max(0,size),'status':int(resp.get('status') or 0)})
rows=[]
for (method,path),vals in groups.items():
    times=[x['ms'] for x in vals];waits=[x['wait_ms'] for x in vals];sizes=[x['bytes'] for x in vals]
    rows.append({'method':method,'path':path,'calls':len(vals),'median_ms':round(statistics.median(times),2),'max_ms':round(max(times),2),
                 'sum_ms':round(sum(times),2),'max_wait_ms':round(max(waits),2),'max_bytes':max(sizes),'statuses':sorted(set(x['status'] for x in vals))})
rows.sort(key=lambda x:x['max_ms'],reverse=True)
out={'entries':sum(len(v) for v in groups.values()),'summed_request_ms':round(sum(r['sum_ms'] for r in rows),2),'endpoints':rows}
text=json.dumps(out,ensure_ascii=False,indent=2)
if args.output:Path(args.output).write_text(text,encoding='utf-8')
print(text)
