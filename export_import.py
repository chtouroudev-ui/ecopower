"""Daily SIMPLIFY2 export and phone-call ingestion."""
from pathlib import Path
from datetime import datetime, timedelta
from collections import Counter
import csv, io, zipfile, hashlib, html, math, sqlite3, time
import import_bundle
import details_store
from error_log import log_unexpected_error
from nelyio_time import local_day as france_local_day
import supervision_context as ctx
from supervision_db import (connect, config, now, audit, init as init_supervision, _reference_day_from_name,
    _local_day_from_stamp, repair_reference_coverage)
from agent_directory import (canonical_admin_key, sync_admin_directory_from_support,
    sync_admin_groups_from_export)
from supervision_utils import kind, stamp, display, archive_csv
from support_filters import TECH_LABELS
from quality_service import update_quality_from_export

def read_export(raw,filename,allow_calls_only=False):
    if filename.lower().endswith('.zip'):
        bundle=import_bundle.current(raw,filename)
        if bundle is not None:
            infos=bundle.infos()
            matches=[x for x in infos if x.filename.lower().endswith('.stats.agent.csv')]
            if not matches and allow_calls_only and any(x.filename.lower().endswith('.odcalls.csv') for x in infos):
                return b'',filename,iter(())
            if len(matches)!=1:raise ValueError('Le ZIP doit contenir exactement un Stats.AGENT.csv.')
            if matches[0].file_size>80*1024*1024:raise ValueError('CSV trop volumineux (80 Mo maximum).')
            raw=bundle.read(matches[0]);filename=matches[0].filename
        else:
            with zipfile.ZipFile(io.BytesIO(raw)) as z:
                matches=[x for x in z.infolist() if x.filename.lower().endswith('.stats.agent.csv')]
                if not matches and allow_calls_only and any(x.filename.lower().endswith('.odcalls.csv') for x in z.infolist()):
                    return b'',filename,iter(())
                if len(matches)!=1:raise ValueError('Le ZIP doit contenir exactement un Stats.AGENT.csv.')
                if matches[0].file_size>80*1024*1024:raise ValueError('CSV trop volumineux (80 Mo maximum).')
                raw=z.read(matches[0]);filename=matches[0].filename
    if not filename.lower().endswith('.stats.agent.csv'):
        raise ValueError('Choisissez le ZIP SIMPLIFY2 ou son fichier Stats.AGENT.csv.')
    text=raw.decode('utf-8-sig')
    reader=csv.DictReader(io.StringIO(text),delimiter=';')
    required={'AgentId','ActionDate','ActionDuration','ActionName','IsSubAction','IsSubPart'}
    if not required.issubset(reader.fieldnames or []):raise ValueError('Colonnes Stats.AGENT manquantes.')
    return raw,filename,reader

def import_export(raw, filename, offset, actor):
    # An explicit import must be able to bootstrap an older/empty database on
    # its own.  Do not rely on the Web process having run supervision.init()
    # first: the dedicated Importer is intentionally a separate process in
    # Nelyio-ARCH.
    init_supervision()
    from import_workflow import run_import
    return run_import(raw, filename, offset, actor, _import_export)


def _import_export(raw, filename, offset, actor):
    # Step 8 destructive retention holds this shared lock while it archives and
    # purges. Refuse a simultaneous import rather than risking a moving source.
    retention_lock=ctx.admin_db_path().parent / "logs" / "retention.lock"
    if retention_lock.exists():
        raise RuntimeError("Archivage/rétention en cours : réessayez l'import après sa fin.")
    offset=int(offset)
    if not -720<=offset<=840:raise ValueError('Décalage UTC invalide.')
    original=raw
    archive_name=filename
    core_perf={}
    _t=time.perf_counter();raw,filename,reader=read_export(raw,filename,allow_calls_only=True);core_perf['read_extract_seconds']=round(time.perf_counter()-_t,4)
    digest=hashlib.sha256(original+str(offset).encode()).hexdigest()
    cfg=config();items=[];days=set();seen=set();skipped=0;distribution_groups={}
    _t=time.perf_counter()
    for i,r in enumerate(reader,2):
        try:
            if r['IsSubAction'] not in ('0','') or r['IsSubPart'] not in ('0',''):
                skipped+=1;continue
            start=stamp(r['ActionDate'],offset);duration=float(r['ActionDuration'])
            if not math.isfinite(duration) or not 0<=duration<=7*86400:raise ValueError('durée invalide')
            agent=r['AgentId'].strip()
            if not agent:raise ValueError('agent vide')
            distribution_group=' '.join(str(r.get('DistributionGroup','') or '').split()).strip()
            if distribution_group:
                distribution_groups.setdefault(canonical_admin_key(agent),set()).add(distribution_group[:60])
            state=html.unescape(r['ActionName'] or ('État '+r.get('ActionType','?')))
            row=(agent,(' '.join([r.get('AgentFirstName',''),r.get('AgentLastName','')])).strip(),start,start+duration,state,kind(state),r.get('CampaignName',''),r.get('SessionID',''))
            if row in seen:skipped+=1;continue
            seen.add(row);items.append(row)
            d=datetime.strptime(display(start,cfg['display_offset'])[:10],'%Y-%m-%d')
            last=display(max(start,start+duration-0.001),cfg['display_offset'])[:10]
            while d.strftime('%Y-%m-%d')<=last:
                days.add(d.strftime('%Y-%m-%d'));d+=timedelta(days=1)
        except (ValueError,KeyError) as exc:raise ValueError(f'Ligne {i}: {exc}') from exc
    core_perf['stats_parse_normalize_dedup_seconds']=round(time.perf_counter()-_t,4)
    _t=time.perf_counter();call_rows,call_details=parse_phone_calls_bundle(original,archive_name);core_perf['odcalls_parse_dedup_seconds']=round(time.perf_counter()-_t,4)
    _t=time.perf_counter();call_relations=parse_phone_relations_bundle(original,archive_name);core_perf['odrelations_parse_seconds']=round(time.perf_counter()-_t,4)
    if not items and not call_rows:raise ValueError('Aucune activité principale ni appel dans cet export.')
    # The filename is the authoritative business day for a daily SIMPLIFY2
    # export. Do not let a few timezone/boundary rows claim an adjacent day.
    reference_day=_reference_day_from_name(archive_name)
    if not reference_day:
        counts=Counter(_local_day_from_stamp(r[2],offset) for r in (items or call_rows))
        reference_day=counts.most_common(1)[0][0]
    reference_days=[reference_day]
    touched_days=sorted(days)
    # Global login/logout markers are explicitly UTC. Pair logout with the next
    # observed login; never extend a final logout to end-of-shift.
    _t=time.perf_counter()
    if items and archive_name.lower().endswith('.zip'):
        bundle=import_bundle.current(original,archive_name)
        if bundle is not None:
            ods=bundle.matching('.odactions.csv')
            read_member=bundle.read
        else:
            z=zipfile.ZipFile(io.BytesIO(original))
            ods=[x for x in z.infolist() if x.filename.lower().endswith('.odactions.csv')]
            read_member=z.read
        try:
            if len(ods)>1:raise ValueError('Plusieurs ODActions : export ambigu.')
            if ods:
                if ods[0].file_size>80*1024*1024:raise ValueError('ODActions trop volumineux.')
                rdr=csv.DictReader(io.StringIO(read_member(ods[0]).decode('utf-8-sig')),delimiter=';')
                transitions={}
                for r in rdr:
                    if r['Context']=='0' and r['State']=='0' and r['StateDetail'] in ('0','-1'):
                        transitions.setdefault(r['AgentId'],set()).add((stamp(r['DateUTC'],0),r['StateDetail']))
                names={r[0]:r[1] for r in items}
                for ag,events in transitions.items():
                    offline=None
                    for ts,detail in sorted(events):
                        if detail=='-1':offline=ts
                        elif offline is not None:
                            if ts>=offline and display(offline,cfg['display_offset'])[:10] in reference_days:
                                items.append((ag,names.get(ag,''),offline,ts,'Déconnecté (entre deux connexions)','offline','',''))
                            offline=None
                    if offline is not None and display(offline,cfg['display_offset'])[:10] in reference_days:
                        items.append((ag,names.get(ag,''),offline,offline,'Départ / déconnexion finale (durée inconnue)','departure','',''))
        finally:
            if bundle is None:z.close()
    core_perf['odactions_enrichment_seconds']=round(time.perf_counter()-_t,4)

    _t=time.perf_counter()
    with connect() as c:
        # A purged import must never be resurrected by the automatic importer.
        tombstone = None
        try:
            tombstone=c.execute('SELECT original_import_id,reference_day,archive_path FROM retention_import_tombstones WHERE digest=?',(digest,)).fetchone()
        except sqlite3.OperationalError:
            # Backward-compatible with a database not yet initialized by Step 8.
            tombstone=None
        if tombstone:
            audit(c,actor,'IMPORT_TOMBSTONE_BLOCKED',f'{Path(filename).name}: {reference_day}')
            core_perf['db_stage_transaction_seconds']=round(time.perf_counter()-_t,4)
            return dict(duplicate=True,purged=True,import_id=tombstone[0],rows=0,days=[tombstone[1] or reference_day],
                        touched_days=touched_days,skipped=skipped,calls=0,archive_path=tombstone[2] or '',_core_performance=core_perf)
        old=c.execute('SELECT id FROM imports WHERE digest=?',(digest,)).fetchone()
        if old:
            # Reimport same file is a true no-op; never silently roll a day back.
            added=store_phone_calls(c,old[0],call_rows,cfg,reference_days,activate=False)
            enriched=store_phone_call_details(c,old[0],call_details)
            related=store_phone_call_relations(c,old[0],call_relations)
            repair_reference_coverage(c)
            audit(c,actor,'CALL_IMPORT_RETRY',str(added))
            result=dict(duplicate=True,import_id=old[0],rows=0,days=reference_days,touched_days=touched_days,skipped=skipped,calls=added,call_details=enriched,call_relations=related)
            c.commit()  # Make any newly recovered ODCalls visible to the Details archive.
            result['_groups']=distribution_groups
            from import_workflow import reference_status
            result['reference']=reference_status(c,old[0])
            core_perf['db_stage_transaction_seconds']=round(time.perf_counter()-_t,4);result['_core_performance']=core_perf
            return result
        from import_workflow import allocate_ids
        ident=allocate_ids(c,'imports')
        c.execute('INSERT INTO imports(id,digest,name,imported_at,imported_by,rows_count,offset_minutes,reference_day) VALUES(?,?,?,?,?,?,?,?)',
                      (ident,digest,Path(filename).name,now(),actor,len(items),offset,reference_day))
        first_activity=allocate_ids(c,'activities',len(items))
        c.executemany('INSERT INTO activities(id,import_id,agent,name,start,end,state,kind,campaign,session) VALUES(?,?,?,?,?,?,?,?,?,?)',((first_activity+i,ident,*r) for i,r in enumerate(items)))
        from import_workflow import assess_reference
        reference=assess_reference(c,ident,reference_day,items,call_rows,activate=False)
        added=store_phone_calls(c,ident,call_rows,cfg,reference_days,activate=False)
        enriched=store_phone_call_details(c,ident,call_details)
        related=store_phone_call_relations(c,ident,call_relations)
        # V60.2 snapshot import: the previous coverage remains authoritative
        # until every staging/enrichment step succeeds. The final switch is a
        # short transaction in import_workflow.run_import().
        audit(c,actor,'IMPORT_STAGED',f'{Path(filename).name}: {len(items)} activités; UTC {offset}; jour de référence {reference_day}; jours touchés {touched_days}')
    core_perf['db_stage_transaction_seconds']=round(time.perf_counter()-_t,4)
    return dict(duplicate=False,import_id=ident,rows=len(items),days=reference_days,touched_days=touched_days,skipped=skipped,calls=added,call_details=enriched,call_relations=related,reference=reference,_groups=distribution_groups,_core_performance=core_perf)


def parse_phone_calls(raw,filename):
    rows,_details=parse_phone_calls_bundle(raw,filename)
    return rows

def parse_phone_call_details(raw,filename):
    _rows,details=parse_phone_calls_bundle(raw,filename)
    return details

def parse_phone_relations_bundle(raw,filename):
    """Return exact ODRelations edges with their source dictionary labels.

    CallID/RefCallID are kept verbatim.  No temporal inference is used.  An
    empty list means the ZIP was parsed successfully but did not contain
    ODRelations; None means this input type cannot carry relations.
    """
    if not filename.lower().endswith('.zip'):
        return None
    bundle=import_bundle.current(raw,filename)
    if bundle is not None:
        rels=bundle.matching('.odrelations.csv')
        meanings=bundle.matching('.callrelationmeaning.csv')
        if len(rels)>1 or len(meanings)>1:raise ValueError('Plusieurs tables de relations : export ambigu.')
        if not rels:return []
        if rels[0].file_size>20*1024*1024:raise ValueError('ODRelations trop volumineux.')
        rel_reader=csv.DictReader(io.StringIO(bundle.read(rels[0]).decode('utf-8-sig')),delimiter=';')
        meaning_reader=csv.DictReader(io.StringIO(bundle.read(meanings[0]).decode('utf-8-sig')),delimiter=';') if meanings else []
    else:
        z=zipfile.ZipFile(io.BytesIO(raw))
        rels=[x for x in z.infolist() if x.filename.lower().endswith('.odrelations.csv')]
        meanings=[x for x in z.infolist() if x.filename.lower().endswith('.callrelationmeaning.csv')]
        if len(rels)>1 or len(meanings)>1:
            z.close();raise ValueError('Plusieurs tables de relations : export ambigu.')
        if not rels:
            z.close();return []
        if rels[0].file_size>20*1024*1024:
            z.close();raise ValueError('ODRelations trop volumineux.')
        rel_reader=csv.DictReader(io.StringIO(z.read(rels[0]).decode('utf-8-sig')),delimiter=';')
        meaning_reader=csv.DictReader(io.StringIO(z.read(meanings[0]).decode('utf-8-sig')),delimiter=';') if meanings else []
    try:
        labels={}
        for r in meaning_reader:
            code=str(r.get('ReasonID','') or '').strip()
            if code:labels[code]=str(r.get('Description','') or '').strip()
        required={'CallID','RefCallID','Reason'}
        if not required.issubset(rel_reader.fieldnames or []):raise ValueError('Colonnes ODRelations manquantes.')
        out={}
        for line,r in enumerate(rel_reader,2):
            call_id=str(r.get('CallID','') or '').strip();ref=str(r.get('RefCallID','') or '').strip();reason=str(r.get('Reason','') or '').strip()
            if not call_id or not ref or not reason:raise ValueError(f'ODRelations ligne {line} : relation incomplète')
            key=(call_id,ref,reason)
            out[key]=(call_id,ref,reason,labels.get(reason,''))
        return list(out.values())
    finally:
        if bundle is None:z.close()

def parse_phone_calls_bundle(raw,filename):
    if not filename.lower().endswith('.zip'):return None,None
    bundle=import_bundle.current(raw,filename)
    if bundle is not None:
        matches=bundle.matching('.odcalls.csv')
        if not matches:return None,None
        if len(matches)!=1:raise ValueError('Plusieurs ODCalls : export ambigu.')
        if matches[0].file_size>80*1024*1024:raise ValueError('ODCalls trop volumineux.')
        text=bundle.read(matches[0]).decode('utf-8-sig')
        reader=csv.DictReader(io.StringIO(text),delimiter=';')
    else:
        z=zipfile.ZipFile(io.BytesIO(raw))
        reader=archive_csv(z,'.odcalls.csv')
        if reader is None:
            z.close();return None,None
    try:
        required={'ID','DateUTC','Indice','ANI','DNIS','ConvDuration','EndReason'}
        if not required.issubset(reader.fieldnames or []):raise ValueError('Colonnes ODCalls manquantes.')
        out={};details={}
        for line,r in enumerate(reader,2):
            try:
                ident=r['ID'].strip()
                if not ident:raise ValueError('ID vide')
                def number(k):
                    v=float(r.get(k,'0') or '0')
                    if not math.isfinite(v) or not -7*86400<=v<=7*86400:raise ValueError('Durée invalide : '+k)
                    return v
                row=(ident,r['Indice'],stamp(r['DateUTC'],0),r.get('CallType',''),number('Duration'),number('ConvDuration'),number('TotalWaitDuration'),
                     r['ANI'],r['DNIS'],r.get('OutTel',''),r.get('OutDialed',''),r.get('FirstAgent',''),r.get('LastAgent',''),
                     r.get('LastCampaign','') or r.get('FirstCampaign',''),r['EndReason'],int(r.get('NoAgent','0') or 0),
                     int(r.get('Abandon','0') or 0),int(r.get('Closed','0') or 0),int(r.get('EndByAgent','0') or 0))
                detail=(ident,number('CallDuration'),number('WaitDuration'),number('TotalWaitDuration'),
                        str(r.get('FirstQueue','') or '').strip(),str(r.get('LastQueue','') or '').strip(),
                        str(r.get('FirstCampaign','') or '').strip(),str(r.get('LastCampaign','') or '').strip(),
                        str(r.get('LastTransfer','') or '').strip())
                if ident in out and out[ident]!=row:raise ValueError('ID répété avec des données différentes')
                if ident in details and details[ident]!=detail:raise ValueError('ID répété avec des détails différents')
                out[ident]=row;details[ident]=detail
            except (ValueError,KeyError,TypeError) as exc:raise ValueError(f'ODCalls ligne {line}: {exc}') from exc
        return list(out.values()),list(details.values())
    finally:
        if bundle is None:z.close()

def store_phone_call_details(c,ident,rows):
    if rows is None:return 0
    c.executemany('''INSERT INTO phone_call_details(import_id,call_id,call_duration,wait_initial,total_wait,first_queue,last_queue,first_campaign,last_campaign,last_transfer)
                     VALUES(?,?,?,?,?,?,?,?,?,?)
                     ON CONFLICT(import_id,call_id) DO UPDATE SET
                       call_duration=excluded.call_duration,wait_initial=excluded.wait_initial,total_wait=excluded.total_wait,
                       first_queue=excluded.first_queue,last_queue=excluded.last_queue,first_campaign=excluded.first_campaign,
                       last_campaign=excluded.last_campaign,last_transfer=excluded.last_transfer''',((ident,*r) for r in rows))
    return len(rows)


def store_phone_call_relations(c,ident,rows):
    if rows is None:return 0
    c.execute('DELETE FROM phone_call_relations WHERE import_id=?',(ident,))
    if rows:
        c.executemany('''INSERT INTO phone_call_relations(import_id,call_id,ref_call_id,reason_code,reason_label)
          VALUES(?,?,?,?,?)''',((ident,*r) for r in rows))
    c.execute('''INSERT INTO phone_call_relation_imports(import_id,rows_count) VALUES(?,?)
      ON CONFLICT(import_id) DO UPDATE SET rows_count=excluded.rows_count''',(ident,len(rows)))
    return len(rows)


def store_phone_calls(c,ident,rows,cfg,reference_days=None,activate=True):
    if rows is None or c.execute('SELECT 1 FROM call_imports WHERE import_id=?',(ident,)).fetchone():return 0
    c.executemany('INSERT INTO phone_calls VALUES('+','.join('?' for _ in range(20))+')',((ident,*r) for r in rows))
    c.execute('INSERT INTO call_imports VALUES(?,?)',(ident,len(rows)))
    days=set(reference_days or ()) or {france_local_day(r[2]) for r in rows}
    for day in (days if activate else []):
        # Calls belong to the same business-day reference as Stats.AGENT.
        # Boundary timestamps must not replace an adjacent day's ODCalls mapping.
        c.execute('''INSERT INTO call_coverage VALUES(?,?) ON CONFLICT(day)
          DO UPDATE SET import_id=CASE WHEN call_coverage.import_id>excluded.import_id THEN call_coverage.import_id ELSE excluded.import_id END''',(day,ident))
    return len(rows)

