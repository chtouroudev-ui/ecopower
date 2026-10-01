"""Optional fictitious records, never an import of customer data.

Refuses any nonempty business table. Does not delete records, create a login,
activate collection, or set include_phone for future real collection.
"""
from __future__ import annotations
import argparse
from datetime import date, timedelta
import hashlib
import json
from pathlib import Path
import socket
import db_compat as sqlite3
import time

DB_NAMES = ('TECHIN_Stock_Manager.db', 'NELYIO_Supervision.db', 'Nelyio_Details.db', 'Nelyio_Live.db')
SYSTEM_TABLES = {
    'admin': {'settings', 'site_policies', 'support_priority_policies', 'access_groups',
              'access_group_permissions', 'users', 'sessions', 'auth_audit', 'access_group_members'},
    'main': {'settings'},
    'details': {'detail_meta', 'sync_state', 'sync_runs', 'detail_read_revision'},
    'live': {'collection_settings'},
}


def require_stopped():
    for port in (5000, 9051):
        with socket.socket() as sock:
            sock.settimeout(0.2)
            if sock.connect_ex(('127.0.0.1', port)) == 0:
                raise RuntimeError(f'Le port {port} est actif. Arretez Nelyio et les imports avant les exemples.')


def _insert(c, schema, table, **values):
    names = ','.join('"' + k + '"' for k in values)
    c.execute(f'INSERT INTO {schema}."{table}" ({names}) VALUES ({",".join("?" for _ in values)})', tuple(values.values()))


def populate(day=None):
    import app_config as cfg
    import app_db
    import supervision as sv
    import details_store
    import collection_store as store
    from collection_parser import Decoder
    from collection_service import validate_settings
    from nelyio_time import local_day, local_wall_timestamp, france_offset_for_day

    day = day or local_day(time.time())
    date.fromisoformat(day)
    previous = (date.fromisoformat(day) - timedelta(days=1)).isoformat()
    app_db.ensure_schema(); sv.init(); store.init()
    quality_path = cfg.BASE / 'data' / 'quality_priorities.json'
    quality = json.loads(quality_path.read_text('utf-8')) if quality_path.exists() else {}
    if any(quality.get(k) for k in ('agents', 'queues', 'campaigns')):
        raise RuntimeError('Le catalogue contient deja des donnees. Aucun exemple ajoute.')
    when = lambda d, h, m=0, sec=0: local_wall_timestamp(d, h, m, sec)
    actors = [('99001', 'Alpha', 9901), ('99002', 'Beta', 9902)]
    # Construct synthetic callbacks in memory. No HAR, HTTP or browser session.
    sid, source = 'DEMO-SESSION-V564', 'DEMO-SOURCE-V564'
    settings = validate_settings(dict(day=day, start_time='08:00', end_time='19:00', include_phone=True))
    dec = Decoder(True); packets = []
    for i, (agent, hour, minute) in enumerate([('99001', 10, 0), ('99002', 12, 15), ('99001', 13, 15)]):
        for delta, state in [(0, 'En ligne (appel entrant)'), (5, 'En ligne (appel entrant)'),
                             (15, 'En ligne (appel entrant)'), (30, 'Post travail (appel entrant)')]:
            args = [0, int(agent), -1, 100, state, delta, 1, '', '', 1, 9901+i%2,
                    'DEMO - Client '+str(1+i%2), '000000000'+str(i+1), '', 1, 0, 0, i]
            body = 'UpAgtTState('+','.join(json.dumps(v) for v in args)+');'
            stamp = when(day, hour, minute) + delta
            decoded = dec.decode(body)
            decoded['events'].append(dict(type='heartbeat', entity='', payload={}))
            packets.append((stamp, decoded))
    conn = sqlite3.connect(sv.DB, timeout=2)
    conn.row_factory = sqlite3.Row
    try:
        for name, path in [('admin', cfg.APP_DB), ('details', details_store.DETAILS_DB), ('live', store.db_path())]:
            conn.execute(f'ATTACH DATABASE ? AS {name}', (str(path),))
        conn.execute('PRAGMA foreign_keys=ON')
        conn.execute('BEGIN IMMEDIATE')
        for schema, allowed in SYSTEM_TABLES.items():
            for row in conn.execute(f"SELECT name FROM {schema}.sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall():
                name = row[0]
                if name not in allowed and conn.execute(f'SELECT COUNT(*) FROM {schema}."{name}"').fetchone()[0]:
                    raise RuntimeError(f'{schema}.{name} contient deja des donnees. Aucun exemple ajoute.')
        if conn.execute("SELECT 1 FROM admin.settings WHERE key='demo_dataset_v564'").fetchone():
            raise RuntimeError('Exemples deja presents : aucun doublon ajoute.')
        for agent, first, group in actors:
            _insert(conn,'admin','user_groups',id=group,name='DEMO - Equipe '+first,description='Exemple entierement fictif',created_by='DEMO',updated_by='DEMO')
            _insert(conn,'admin','user_directory',user_key=agent,user_identifier=agent,first_name=first,last_name='DEMO')
            _insert(conn,'admin','user_group_members',user_key=agent,user_identifier=agent,group_id=group,created_by='DEMO')
        for i, status in enumerate(['EN_SERVICE','STOCK','REPARATION'],1):
            pc=f'DEMO-PC-{i:02}'
            _insert(conn,'admin','asset_management',ordinateur=pc,asset_tag='DEMO-'+str(i),statut=status,
                    affectation='DEMO',notes='Materiel fictif, pas un poste reel.',created_manually=1,
                    created_by='DEMO',updated_by='DEMO',manual_domaine='demo.invalid',manual_utilisateur='99001' if i==1 else '')
            _insert(conn,'admin','diagnostic',event_uuid=f'DEMO-DIAG-{i}',date_evenement=day+' 09:00:00',
                    action='DEMO',utilisateur='99001' if i==1 else '',ordinateur=pc,
                    adresse_ip='192.0.2.'+str(10+i),collecteur='DC1',domaine='demo.invalid',source_path='DEMO')
        _insert(conn,'admin','consumables',id=9901,name='DEMO - Coussinet casque',category='Exemple',unit='unite',created_by='DEMO',updated_by='DEMO')
        _insert(conn,'admin','consumable_balances',consumable_id=9901,condition='NEUF',quantity=5)
        _insert(conn,'admin','consumable_movements',consumable_id=9901,direction='ENTREE',condition='NEUF',quantity=5,
                comment='Stock fictif de demonstration',username='DEMO')
        _insert(conn,'main','imports',id=9901,digest='DEMO-V564-'+previous,name=f'DEMO_SIMPLIFY2.{previous}.export.zip',
                imported_at=day+' 08:00:00',imported_by='DEMO',rows_count=8,offset_minutes=france_offset_for_day(previous),reference_day=previous)
        _insert(conn,'main','coverage',day=previous,import_id=9901)
        _insert(conn,'main','call_coverage',day=previous,import_id=9901)
        _insert(conn,'main','call_imports',import_id=9901,rows_count=4)
        for i,(agent,h,m,dur,talk,wait,abandon) in enumerate([
                ('99001',10,0,180,150,25,0),('99002',12,15,90,60,25,0),
                ('99001',13,15,45,0,45,1),('99002',14,0,120,100,15,0)],1):
            start=when(previous,h,m)
            _insert(conn,'main','phone_calls',import_id=9901,call_id=f'DEMO-CALL-{i}',indice=f'DEMO-I-{i}',start=start,
                    call_type='IN',duration=dur,conversation=talk,wait=wait,ani='000000000'+str(i),dnis='0000000099',
                    outtel='',outdialed='',first_agent=agent,last_agent=agent,campaign='DEMO - Client '+str(1+i%2),
                    end_reason='0',no_agent=0,abandon=abandon,closed=1,end_by_agent=1)
            _insert(conn,'main','activities',import_id=9901,agent=agent,name=('Alpha' if agent=='99001' else 'Beta')+' DEMO',
                    start=start,end=start+dur,state='En appel',kind='call',campaign='DEMO - Client '+str(1+i%2),session='DEMO')
        for agent,h,m,dur,kind in [('99001',10,5,20,'offline'),('99002',11,0,30,'offline'),('99001',12,0,900,'pause'),('99002',15,0,120,'ready')]:
            start=when(previous,h,m)
            _insert(conn,'main','activities',import_id=9901,agent=agent,name=('Alpha' if agent=='99001' else 'Beta')+' DEMO',
                    start=start,end=start+dur,state=kind,kind=kind,campaign='DEMO',session='DEMO')
        _insert(conn,'live','collection_sessions',id=sid,day=day,start_ts=settings['start_ts'],end_ts=settings['end_ts'],
                settings_json=json.dumps(settings),actor='DEMO',created_at=when(day,8),status='completed',connection_state='closed',
                stop_requested=1,first_response=packets[0][0],last_response=packets[-1][0],finished_at=packets[-1][0],
                response_count=len(packets),event_count=sum(len(p['events']) for _,p in packets))
        for i,(stamp,decoded) in enumerate(packets):
            key=hashlib.sha256(f'{sid}|{i}'.encode()).hexdigest()
            _insert(conn,'live','collection_responses',response_key=key,session_id=sid,source=source,stamp=stamp,digest='DEMO',recognized=1,rejected=0)
            for j,event in enumerate(decoded['events']):
                ek=hashlib.sha256(f'{key}|{j}'.encode()).hexdigest()
                _insert(conn,'live','collection_events',event_key=ek,session_id=sid,source=source,stamp=stamp,
                        event_type=event['type'],entity_id=event['entity'],payload_json=json.dumps(event['payload'],ensure_ascii=False),published=1)
        summary=dict(version='56.4',synthetic=True,export_day=previous,live_day=day,agents=2,groups=2,pcs=3,consumables=1,exported_calls=4,live_observations=3)
        _insert(conn,'admin','settings',key='demo_dataset_v564',value=json.dumps(summary),updated_by='DEMO')
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()
    # Derived views can always be rebuilt from the committed source records.
    store.init()
    details_store.sync_from_sources(sv.DB, cfg.APP_DB, sv.TECH_LABELS, force=True)
    return summary


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-stopped',action='store_true')
    parser.add_argument('--day',help='Date des exemples live (AAAA-MM-JJ); hier pour les appels exportes')
    args=parser.parse_args()
    if not args.confirm_stopped:
        raise SystemExit('Arretez Nelyio puis confirmez avec --confirm-stopped. Aucun fichier efface.')
    require_stopped()
    try:
        result=populate(args.day)
    except (RuntimeError,ValueError,sqlite3.Error) as exc:
        raise SystemExit('Exemples non ajoutes : '+str(exc)) from exc
    print('EXEMPLES FICTIFS AJOUTES. Aucun compte ni collecte active cree.')
    print('Appels exportes / Diagnostic : '+result['export_day'])
    print('Appels LIVE / Details : '+result['live_day'])


if __name__=='__main__':
    main()
