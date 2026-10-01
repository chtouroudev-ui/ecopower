"""Internal consistency gate for Nelyio Quality interfaces.

The check validates that both Quality views are calculated from a complete,
compatible accepted reference and that their own reconciliation rules pass.
It does not force a Vocalcom production-report total onto Stats.INBOUND or
Stats.AGENT when the source perimeter differs.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

ROOT=Path(__file__).resolve().parent
os.environ.setdefault('NELYIO_SKIP_STARTUP_DETAILS_SYNC','1')


def latest_day() -> str:
    from supervision_db import connect
    with connect() as con:
        row=con.execute("SELECT MAX(day) FROM call_coverage").fetchone()
    return str(row[0]) if row and row[0] else ''


def run(day: str) -> dict:
    from quality_metrics import overview
    from quality_agents import view
    agents=view({'date_from':[day],'date_to':[day]})
    scope={'date_from':[day],'date_to':[day],'time_from':[agents['time_from']],'time_to':[agents['time_to']]}
    service=overview(scope)
    from quality_distributions import view as distribution_view
    distribution=distribution_view(scope)
    checks=[]
    checks.append({'name':'service_coverage','ok':service.get('available_days')==1,
                   'detail':f"{service.get('available_days',0)}/1 jour disponible"})
    checks.append({'name':'service_integrity','ok':service.get('integrity',{}).get('ok') is True,
                   'detail':service.get('integrity')})
    checks.append({'name':'agent_coverage','ok':agents.get('available_days')==1,
                   'detail':f"{agents.get('available_days',0)}/1 jour disponible"})
    checks.append({'name':'agent_calls_compatible','ok':agents.get('calls_compatible') is True,
                   'detail':'même référence activités/appels' if agents.get('calls_compatible') else 'références incompatibles'})
    checks.append({'name':'agent_integrity','ok':agents.get('integrity',{}).get('ok') is True,
                   'detail':agents.get('integrity')})
    total=service.get('total') or {}
    checks.append({'name':'service_agents_handled','ok':total.get('treated_agent') is not None and total.get('treated_agent')==agents.get('summary',{}).get('handled'),'detail':'Traités AgentId > 0 identiques sur les mêmes heures et agents'})
    comparisons=(('received','received'),('treated_agent','treated'),('answered','answered'),('abandoned','abandoned'))
    for service_key,distribution_key in comparisons:
        checks.append({'name':'distribution_'+distribution_key,
                       'ok':total.get(service_key) is not None and total.get(service_key)==distribution['total'].get(distribution_key),
                       'detail':{'service':total.get(service_key),'distribution':distribution['total'].get(distribution_key)}})
    denominator=None;numerator=None
    if total.get('received') is not None:
        numerator=int(total.get('treated_agent') or 0)
        denominator=int(total.get('received') or 0)-int(total.get('closed') or 0)-int(total.get('hangup_before_queue') or 0)
        checks.append({'name':'qos_numerator','ok':numerator==int(total.get('qos_numerator') or 0),
                       'detail':f"{total.get('treated_agent',0)} = {numerator}"})
        checks.append({'name':'qos_denominator','ok':denominator==int(total.get('qos_denominator') or 0),
                       'detail':f"{total.get('received',0)} - {total.get('closed',0)} - {total.get('hangup_before_queue',0)} = {denominator}"})
        checks.append({'name':'business_coherence','ok':total.get('coherence_ok') is True,
                       'detail':{'delta':total.get('coherence_delta'),'double_classified':total.get('double_classified')}})
    return {
        'date':day,
        'ok':all(c['ok'] for c in checks),
        'formula':'QoS = traités / (reçus - clôturés - raccrochés avant file)',
        'service':{
            'source':service.get('source'),'received':total.get('received'),'treated':total.get('treated_agent'),
            'handled':total.get('treated_agent'),
            'answered':total.get('answered'),'abandoned':total.get('abandoned'),'closed':total.get('closed'),
            'hangup_before_queue':total.get('hangup_before_queue'),'rerouted_no_agent':total.get('rerouted_no_agent'),
            'numerator':numerator,'denominator':denominator,'qos_percent':total.get('qos_percent'),
            'asa_seconds':total.get('asa_seconds'),'invalid_durations':total.get('invalid_durations'),
            'coherence_delta':total.get('coherence_delta'),
        },
        'agents':agents.get('summary'),
        'checks':checks,
        'reference_note':('Le rapport Vocalcom du 18/09/2026 indique 893 appels, 63h15m32 de travail et '
                          '71h53m11 de présence. Ces valeurs sont une référence externe à comparer seulement '
                          'si le même périmètre agents/horaires/sources est sélectionné.' if day=='2026-09-18' else ''),
    }



def main() -> int:
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--date',default='')
    ap.add_argument('--json',type=Path)
    args=ap.parse_args()
    day=args.date.strip() or latest_day()
    if not day:
        print('ECHEC - aucune journée Qualité importée.')
        return 2
    try: date.fromisoformat(day)
    except ValueError:
        print('ECHEC - date invalide:',day);return 2
    try:
        result=run(day)
    except Exception as exc:
        result={'date':day,'ok':False,'error':f'{type(exc).__name__}: {exc}'}
    if args.json:
        args.json.parent.mkdir(parents=True,exist_ok=True)
        args.json.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    if result.get('error'):
        print('ECHEC -',result['error']);return 1
    print('Date :',result['date'])
    print('Formule :',result['formula'])
    s=result['service']
    print('Service : recus={received} traites={treated} repondus={answered} abandonnes={abandoned} qos={qos_percent} asa={asa_seconds}s'.format(**s))
    a=result.get('agents') or {}
    print('Agents : nb={agent_count} traites={handled} travail={work_seconds}s presence={presence_seconds}s deconnecte={disconnected_seconds}s'.format(**{k:a.get(k) for k in ('agent_count','handled','work_seconds','presence_seconds','disconnected_seconds')}))
    for c in result['checks']:
        print(('OK' if c['ok'] else 'ECHEC')+' - '+c['name']+' : '+str(c['detail']))
    if result.get('reference_note'): print('REFERENCE - '+result['reference_note'])
    return 0 if result['ok'] else 1

if __name__=='__main__':
    raise SystemExit(main())
