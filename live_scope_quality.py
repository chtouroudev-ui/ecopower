"""RC29 Phase 2: bounded historical quality metrics for Live scope rows.

This module deliberately separates imported Stats.INBOUND metrics from the
frequent Hermes Live refresh. It never changes Live state and never infers a
zero when the imported period is unavailable.
"""
from __future__ import annotations

from datetime import datetime

from nelyio_time import day_bounds, today
from quality_importer import agent_key
from quality_metrics import _version_ready
from quality_scope import load_quality_file_scope
from supervision_db import connect, config


def _get(qs, key, default=""):
    value=(qs or {}).get(key,[default])
    if isinstance(value,(list,tuple)):
        value=value[0] if value else default
    return str(value or "").strip()


def _qos(treated, received, closed, hangup_before_queue):
    treated=int(treated or 0);received=int(received or 0);closed=int(closed or 0);before=int(hangup_before_queue or 0)
    denominator=received-closed-before
    return None if denominator<=0 else round(100.0*treated/denominator, 4)


def _empty_bucket():
    return {"received":0,"treated":0,"abandoned":0,"closed":0,"hangup_before_queue":0}


def _add(bucket, *, received=1, treated=False, abandoned=False, closed=False, hangup_before_queue=False):
    bucket["received"]+=int(received or 0)
    bucket["treated"]+=1 if treated else 0
    bucket["abandoned"]+=1 if abandoned else 0
    bucket["closed"]+=1 if closed else 0
    bucket["hangup_before_queue"]+=1 if hangup_before_queue else 0


def _finalize(bucket, quality="reliable", reason=""):
    if bucket is None:
        return {"received":None,"treated":None,"abandoned":None,"closed":None,"hangup_before_queue":None,"qos":None,"quality":"unavailable","reason":reason or "scope_not_attributable"}
    return {
        "received":int(bucket["received"]),
        "treated":int(bucket["treated"]),
        "abandoned":int(bucket["abandoned"]),
        "closed":int(bucket["closed"]),
        "hangup_before_queue":int(bucket["hangup_before_queue"]),
        "qos":_qos(bucket["treated"],bucket["received"],bucket["closed"],bucket["hangup_before_queue"]),
        "quality":quality,
        "reason":reason,
    }


def view(qs=None):
    """Return one explicit imported period, keyed by Live scope identity.

    Group membership follows configured files -> ACTIVE agents. Campaign is the
    Stats.INBOUND CampaignID. Queue attribution is only exposed when the
    configured campaign->file mapping is unique; ambiguous queue attribution is
    returned as unavailable instead of guessed.
    """
    qs=qs or {}
    settings=config()
    day=_get(qs,"day",today()) or today()
    try:
        datetime.strptime(day,"%Y-%m-%d")
    except ValueError as exc:
        raise ValueError("Jour historique Live invalide.") from exc
    start=_get(qs,"time_from",settings.get("work_start") or "08:00")
    end=_get(qs,"time_to",settings.get("work_end") or "19:00")
    try:
        start=datetime.strptime(start,"%H:%M").strftime("%H:%M")
        end=datetime.strptime(end,"%H:%M").strftime("%H:%M")
    except ValueError as exc:
        raise ValueError("Période historique Live invalide.") from exc
    if start>=end:
        raise ValueError("La fin de période doit être après le début.")
    selected_group=_get(qs,"group")

    scope=load_quality_file_scope()
    groups=[dict(g) for g in (scope.get("groups") or []) if str(g.get("id") or "")!="unassigned"]
    if selected_group:
        groups=[g for g in groups if str(g.get("id") or "")==selected_group]
        if not groups:
            raise ValueError("Groupe métier inconnu pour les métriques historiques Live.")
    allowed_group_ids={str(g.get("id") or "") for g in groups}
    allowed_services={str(g.get("service_name") or "").strip() for g in groups if str(g.get("service_name") or "").strip()}
    allowed_lines={str(x) for g in groups for x in (g.get("line_ids") or []) if str(x)} if selected_group else None

    group_members={str(g.get("id") or ""):{agent_key(x) for x in (g.get("member_agent_ids") or []) if agent_key(x)} for g in groups}
    group_campaigns={str(g.get("id") or ""):{str(x) for x in (g.get("campaign_ids") or []) if str(x)} for g in groups}
    group_service={str(g.get("id") or ""):str(g.get("service_name") or "").strip() for g in groups}
    agent_groups={}
    for gid,members in group_members.items():
        for aid in members:agent_groups.setdefault(aid,set()).add(gid)
    campaign_groups={}
    for gid,cids in group_campaigns.items():
        for cid in cids:campaign_groups.setdefault(cid,set()).add(gid)

    campaign_to_files={str(k):[str(x.get("line_id") or "") for x in (v or []) if str(x.get("line_id") or "")] for k,v in (scope.get("campaign_to_files") or {}).items()}
    if allowed_lines is not None:
        campaign_to_files={cid:[x for x in lines if x in allowed_lines] for cid,lines in campaign_to_files.items()}

    buckets={"SERVICE":{},"GROUP":{},"CAMPAIGN":{},"QUEUE":{}}
    queue_ambiguous=set()
    agent_rows=[]
    with connect() as con:
        # Agent handled-call counts for the Live roster use Stats.AGENT and are
        # refreshed with the same 60 s companion cache as scope history. They
        # are deliberately historical/partial for the current day, not invented
        # from Hermes state transitions.
        try:
            aref=con.execute("""SELECT cov.import_id FROM coverage cov
                                  WHERE cov.day=? LIMIT 1""",(day,)).fetchone()
            if aref:
                alo,ahi=day_bounds(day,start,end)
                allowed_agents=None
                if selected_group:
                    allowed_agents=set().union(*(group_members.get(gid,set()) for gid in allowed_group_ids))
                qrows=con.execute("""SELECT agent,COUNT(DISTINCT CASE
                                      WHEN kind='inbound' AND TRIM(COALESCE(session,''))<>'' THEN session
                                      WHEN kind='inbound' THEN row_key END) AS handled
                                  FROM quality_agent_facts
                                  WHERE import_id=? AND start>=? AND start<?
                                  GROUP BY agent""",(int(aref['import_id']),float(alo),float(ahi))).fetchall()
                for qr in qrows:
                    aid=agent_key(qr['agent'])
                    if not aid or (allowed_agents is not None and aid not in allowed_agents):
                        continue
                    agent_rows.append({"agent":aid,"handled":int(qr['handled'] or 0),"quality":"partial" if day==today() else "reliable"})
        except Exception:
            agent_rows=[]
        ref=con.execute("""SELECT cc.import_id,q.version FROM call_coverage cc
                           LEFT JOIN quality_inbound_imports q ON q.import_id=cc.import_id
                           WHERE cc.day=? LIMIT 1""",(day,)).fetchone()
        ready=bool(ref and _version_ready(ref["version"]))
        if not ready:
            return {"source":"Stats.INBOUND","day":day,"time_from":start,"time_to":end,"period_label":f"{start}–{end}",
                    "available":False,"formula":"Traités / (Reçus - Clôturés - Raccrochés avant file) × 100","rows":[],"agents":agent_rows,
                    "limitations":["Aucun import Stats.INBOUND compatible n'est disponible pour cette période."]}
        lo,hi=day_bounds(day,start,end)
        rows=con.execute("""SELECT campaign,agent,received,abandoned,closed,before_queue FROM quality_inbound_facts
                            WHERE import_id=? AND day=? AND start>=? AND start<?""",(ref["import_id"],day,lo,hi))
        for raw in rows:
            cid=str(raw["campaign"] or "").strip();aid=agent_key(raw["agent"])
            assigned=bool(aid and aid!='0')
            abandoned=bool(raw["abandoned"]);closed=bool(raw["closed"]);before=bool(raw["before_queue"])
            if cid:
                b=buckets["CAMPAIGN"].setdefault(cid,_empty_bucket());_add(b,received=1,treated=assigned,abandoned=abandoned,closed=closed,hangup_before_queue=before)
            gids=(agent_groups.get(aid,set()) if assigned else campaign_groups.get(cid,set())) & allowed_group_ids
            services=set()
            for gid in gids:
                b=buckets["GROUP"].setdefault(gid,_empty_bucket());_add(b,received=1,treated=assigned,abandoned=abandoned,closed=closed,hangup_before_queue=before)
                service=group_service.get(gid,"")
                if service:services.add(service)
            for service in services:
                b=buckets["SERVICE"].setdefault(service,_empty_bucket());_add(b,received=1,treated=assigned,abandoned=abandoned,closed=closed,hangup_before_queue=before)
            lines=sorted(set(campaign_to_files.get(cid,[])))
            if len(lines)==1:
                qid=lines[0]
                b=buckets["QUEUE"].setdefault(qid,_empty_bucket());_add(b,received=1,treated=assigned,abandoned=abandoned,closed=closed,hangup_before_queue=before)
            elif len(lines)>1:
                queue_ambiguous.update(lines)

    # Restrict campaign/queue output when a group is selected. This prevents the
    # historical companion endpoint from widening the server-side Live scope.
    allowed_campaigns={x for g in groups for x in (g.get("campaign_ids") or []) if str(x)} if selected_group else None
    out=[]
    for scope_type,mapping in buckets.items():
        for key,bucket in mapping.items():
            if scope_type=="CAMPAIGN" and allowed_campaigns is not None and key not in {str(x) for x in allowed_campaigns}:continue
            if scope_type=="QUEUE" and allowed_lines is not None and key not in allowed_lines:continue
            if scope_type=="SERVICE" and selected_group and key not in allowed_services:continue
            metric=_finalize(bucket,quality="partial" if scope_type=="QUEUE" else "reliable",reason="unique_campaign_queue_mapping" if scope_type=="QUEUE" else "")
            out.append({"scope_type":scope_type,"scope_key":key,**metric})
    # Explicitly mark configured queues whose campaign attribution is ambiguous.
    for key in sorted(queue_ambiguous):
        if allowed_lines is not None and key not in allowed_lines:continue
        if not any(x["scope_type"]=="QUEUE" and x["scope_key"]==key for x in out):
            out.append({"scope_type":"QUEUE","scope_key":key,**_finalize(None,reason="ambiguous_campaign_queue_mapping")})
    return {"source":"Stats.INBOUND","day":day,"time_from":start,"time_to":end,"period_label":f"{start}–{end}",
            "available":True,"formula":"Traités / (Reçus - Clôturés - Raccrochés avant file) × 100","rows":out,"agents":agent_rows,
            "limitations":["Les métriques historiques sont rafraîchies séparément du Live Hermes.",
                           "Une file n'est alimentée que lorsque la correspondance campagne → file configurée est unique ; sinon la valeur reste indisponible."]}
