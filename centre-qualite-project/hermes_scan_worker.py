"""Short-lived passive CDP scanner for the Hermes supervision tab.

Raw payloads are analyzed in memory only. Reports persist endpoint paths,
callback/schema names and current Nelyio coverage, never raw bodies, headers,
cookies, credentials or complete websocket frames.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import inspect
import json
from pathlib import Path
import re
import subprocess
import sys
import time
from urllib.parse import urlsplit

import hermes_diagnostic as diag
from hermes_cdp_login import SUPERVISION_HOST, _find_target

ROOT=Path(__file__).resolve().parent
MAX_BODY=1024*1024
KNOWN_FUNCTIONS={"UpQuR","UpQuH","UpQuMR","UpQuCB","UpAgtH","UpAgtCtxH","UpAgtCtxQu","UpAgtGState","UpAgtMState","UpAgtSH","UpAgtTState","UpCaR"}
FUNC_RE=re.compile(r"\b(Up[A-Za-z0-9_]{2,40})\s*\(")
SENSITIVE_SCHEMA_PARTS={"password","passwd","pwd","token","cookie","authorization","secret","credential","sessionid","session_id"}


def _same_host(url: str) -> bool:
    try:return urlsplit(str(url)).hostname==SUPERVISION_HOST
    except Exception:return False


def _source_key(url: str) -> str:
    p=urlsplit(str(url));return p.path or "/"


def _schema(value, prefix="", depth=0, out=None):
    out=out if out is not None else set()
    if depth>3 or len(out)>=200:return out
    if isinstance(value,dict):
        for k,v in list(value.items())[:100]:
            part=str(k);key=(prefix+"."+part if prefix else part)[:160]
            if any(word in part.casefold() for word in SENSITIVE_SCHEMA_PARTS):continue
            out.add(key);_schema(v,key,depth+1,out)
    elif isinstance(value,list) and value:
        _schema(value[0],prefix+"[]",depth+1,out)
    return out


def analyze_payload(text: str) -> dict:
    text=str(text or "")[:MAX_BODY]
    funcs=Counter(FUNC_RE.findall(text))
    schemas=set()
    stripped=text.lstrip()
    if stripped.startswith(("{","[")):
        try:schemas=_schema(json.loads(text))
        except (ValueError,TypeError):pass
    return {"functions":dict(funcs),"schema_keys":sorted(schemas)[:200]}


def _coverage() -> dict:
    try:
        import collection_store as store
        snap=store.live_supervision_snapshot(include_quality=False)
        catalog=snap.get("live_queue_catalog") or {};native=snap.get("native_queue_metrics") or {};by=native.get("by_line") or {}
        missing_daily=[];missing_realtime=[]
        for lid,name in sorted(catalog.items(),key=lambda x:(str(x[1]).casefold(),str(x[0]))):
            metrics=by.get(str(lid)) or {}
            item={"line_id":str(lid),"name":str(name or lid)[:200]}
            if not metrics.get("UpQuH"):missing_daily.append(item)
            if not metrics.get("UpQuR"):missing_realtime.append(item)
        return {"catalog_lines":len(catalog),"upquh_lines":int(native.get("upquh_count") or 0),"upqur_lines":int(native.get("upqur_count") or 0),
                "missing_upquh":missing_daily[:250],"missing_upqur":missing_realtime[:250],"day":snap.get("day"),
                "normalized_events":int((snap.get("persistence") or {}).get("normalized_events") or 0)}
    except Exception as exc:
        return {"error":str(exc)[:300],"catalog_lines":0,"upquh_lines":0,"upqur_lines":0,"missing_upquh":[],"missing_upqur":[]}


def _open_if_needed(port: int) -> None:
    worker=ROOT/"hermes_supervision_worker.py"
    subprocess.run([sys.executable,str(worker),"--port",str(port)],cwd=str(ROOT),stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,shell=False,timeout=130,check=False)


def _wait_target(port: int, timeout: float):
    end=time.time()+timeout
    while time.time()<end:
        try:
            target=_find_target(port,SUPERVISION_HOST)
            if target:return target
        except Exception:pass
        if diag.stop_requested():return None
        time.sleep(.5)
    return None


def scan(port: int, duration: int, open_if_missing: bool) -> dict:
    diag.update_scan_state(status="checking_browser", message="Vérification du navigateur Hermes…")
    target=None
    try:target=_find_target(port,SUPERVISION_HOST)
    except Exception:target=None
    if not target and open_if_missing:
        diag.update_scan_state(status="opening_browser", message="Ouverture / connexion Hermes en cours…")
        _open_if_needed(port)
        diag.update_scan_state(status="waiting_browser", message="Attente de l'onglet Supervision Hermes…")
        target=_wait_target(port,75)
    if not target:
        raise RuntimeError("Onglet Supervision Hermes introuvable sur le port CDP local.")
    diag.update_scan_state(status="running", message="Analyse Hermes en cours…")
    try:
        from websockets.sync.client import connect
    except ImportError as exc:raise RuntimeError("Module websockets absent pour le diagnostic Hermes.") from exc
    options=dict(open_timeout=3,close_timeout=1,max_size=2*1024*1024,compression=None)
    if "proxy" in inspect.signature(connect).parameters:options["proxy"]=None
    sources=defaultdict(lambda:{"count":0,"statuses":Counter(),"mime":Counter(),"resource_types":Counter(),"functions":Counter(),"schema_keys":Counter()})
    ws_urls={};pending_body={};command_context={};next_id=0;all_functions=Counter();websocket_frames=0
    started=time.time()
    with connect(target["websocket"],**options) as sock:
        next_id+=1;sock.send(json.dumps({"id":next_id,"method":"Network.enable","params":{}}))
        deadline=started+duration
        while time.time()<deadline and not diag.stop_requested():
            try:raw=sock.recv(timeout=.5)
            except TimeoutError:continue
            except Exception as exc:raise RuntimeError("Connexion CDP interrompue pendant l'analyse.") from exc
            try:msg=json.loads(raw)
            except (ValueError,TypeError):continue
            if "id" in msg:
                ctx=command_context.pop(msg.get("id"),None)
                if ctx and not msg.get("error"):
                    result=msg.get("result") or {};body=str(result.get("body") or "")
                    if result.get("base64Encoded"):body=""
                    if body:
                        a=analyze_payload(body);src=sources[ctx]
                        for k,v in a["functions"].items():src["functions"][k]+=v;all_functions[k]+=v
                        for k in a["schema_keys"]:src["schema_keys"][k]+=1
                continue
            method=msg.get("method");params=msg.get("params") or {}
            if method=="Network.responseReceived":
                resp=params.get("response") or {};url=str(resp.get("url") or "")
                if not _same_host(url):continue
                rtype=str(params.get("type") or "");key=_source_key(url);src=sources[key]
                src["count"]+=1;src["statuses"][str(resp.get("status") or "")]+=1;src["mime"][str(resp.get("mimeType") or "")]+=1;src["resource_types"][rtype]+=1
                if rtype in {"XHR","Fetch"}:pending_body[str(params.get("requestId") or "")]=key
            elif method=="Network.loadingFinished":
                rid=str(params.get("requestId") or "");key=pending_body.pop(rid,None)
                if key:
                    next_id+=1;command_context[next_id]=key
                    sock.send(json.dumps({"id":next_id,"method":"Network.getResponseBody","params":{"requestId":rid}}))
            elif method=="Network.webSocketCreated":
                url=str(params.get("url") or "")
                if _same_host(url):ws_urls[str(params.get("requestId") or "")]=_source_key(url)
            elif method=="Network.webSocketFrameReceived":
                rid=str(params.get("requestId") or "");key=ws_urls.get(rid)
                if key:
                    websocket_frames+=1;payload=str((params.get("response") or {}).get("payloadData") or "")
                    if len(payload)<=MAX_BODY:
                        a=analyze_payload(payload);src=sources[key];src["resource_types"]["WebSocket"]+=1
                        for k,v in a["functions"].items():src["functions"][k]+=v;all_functions[k]+=v
                        for k in a["schema_keys"]:src["schema_keys"][k]+=1
    finished=time.time();rows=[]
    for path,data in sorted(sources.items()):
        funcs=sorted(data["functions"].items(),key=lambda x:(-x[1],x[0]))
        rows.append({"path":path[:300],"count":int(data["count"]),"statuses":dict(data["statuses"]),"mime":dict(data["mime"]),"resource_types":dict(data["resource_types"]),
                     "functions":[{"name":k,"count":int(v),"known":k in KNOWN_FUNCTIONS} for k,v in funcs],
                     "schema_keys":[k for k,_ in data["schema_keys"].most_common(100)],
                     "known":bool(funcs) and all(k in KNOWN_FUNCTIONS for k,_ in funcs)})
    return {"started_at":int(started),"finished_at":int(finished),"duration_seconds":round(finished-started,1),"target_host":SUPERVISION_HOST,
            "sources":rows,"functions":[{"name":k,"count":int(v),"known":k in KNOWN_FUNCTIONS} for k,v in sorted(all_functions.items(),key=lambda x:(-x[1],x[0]))],
            "websocket_frames_analyzed":websocket_frames,"coverage":_coverage(),
            "privacy":{"raw_bodies_persisted":False,"cookies_persisted":False,"headers_persisted":False,"credentials_persisted_in_report":False}}


def main() -> int:
    ap=argparse.ArgumentParser();ap.add_argument("--duration",type=int,required=True);ap.add_argument("--port",type=int,required=True);ap.add_argument("--actor",default="admin");ap.add_argument("--open-if-missing",action="store_true")
    args=ap.parse_args();report_path=""
    try:
        report=scan(args.port,args.duration,args.open_if_missing);rid=time.strftime("%Y%m%d_%H%M%S",time.localtime(report["started_at"]))
        report["report_id"]="scan_"+rid;report["actor"]=str(args.actor)[:128];diag.REPORT_DIR.mkdir(parents=True,exist_ok=True)
        path=diag.REPORT_DIR/(report["report_id"]+".json");path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8");report_path=str(path);diag.finish_scan(report_path=report_path);return 0
    except Exception as exc:
        diag.finish_scan(error=str(exc)[:500]);return 2

if __name__=="__main__":raise SystemExit(main())
