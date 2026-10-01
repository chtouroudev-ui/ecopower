#!/usr/bin/env python3
"""Summarize logs/performance.jsonl without exposing request parameters."""
import argparse,json,statistics
from collections import defaultdict
from pathlib import Path
ap=argparse.ArgumentParser();ap.add_argument('path',nargs='?',default='logs/performance.jsonl');ap.add_argument('--top',type=int,default=30);args=ap.parse_args()
groups=defaultdict(list)
for line in Path(args.path).read_text(encoding='utf-8').splitlines():
    try:r=json.loads(line)
    except Exception:continue
    groups[(r.get('service',''),r.get('endpoint',''))].append(r)
rows=[]
for key,vals in groups.items():
    ts=[float(x.get('total_ms',0)) for x in vals]
    rows.append({'service':key[0],'endpoint':key[1],'calls':len(vals),'median_ms':round(statistics.median(ts),2),'max_ms':round(max(ts),2),
      'sql_median_ms':round(statistics.median(float(x.get('sql_ms',0)) for x in vals),2),
      'sql_count_median':round(statistics.median(int(x.get('sql_count',0)) for x in vals),1),
      'auth_median_ms':round(statistics.median(float(x.get('auth_ms',0)) for x in vals),2),
      'worker_median_ms':round(statistics.median(float(x.get('worker_ms',0)) for x in vals),2),
      'compute_median_ms':round(statistics.median(float(x.get('compute_ms',0)) for x in vals),2),
      'json_median_ms':round(statistics.median(float(x.get('json_ms',0)) for x in vals),2),
      'response_bytes_median':round(statistics.median(int(x.get('response_bytes',0)) for x in vals),1)})
rows.sort(key=lambda x:x['max_ms'],reverse=True)
print(json.dumps(rows[:max(1,args.top)],ensure_ascii=False,indent=2))
