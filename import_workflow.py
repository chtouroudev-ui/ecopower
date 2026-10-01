"""Durable imports and explicit daily references. No worker starts on import."""
from pathlib import Path
from collections import Counter
import hashlib
import json
import os
import tempfile
import db_compat as sqlite3
import threading
import time
import import_bundle
import supervision_context as ctx
from supervision_db import connect, now, audit

_RUN_LOCK = threading.RLock()
_QUEUE_LOCK = threading.Lock()
_WORKER_LOCK = threading.Lock()
_WORKER = None
_MAX_PENDING = 8


def enqueue_import(raw, filename, offset, actor):
    """Archive before acknowledging; only the single worker loads queued bytes."""
    offset = int(offset)
    if not -720 <= offset <= 840: raise ValueError('Décalage UTC invalide.')
    if not 0 < len(raw) <= 100*1024*1024: raise ValueError('Fichier vide ou supérieur à 100 Mo.')
    if not filename.lower().endswith(('.zip', '.stats.agent.csv')):
        raise ValueError('Choisir un ZIP SIMPLIFY2 ou Stats.AGENT.csv.')
    digest = hashlib.sha256(raw + str(offset).encode()).hexdigest()
    with _QUEUE_LOCK:
        with connect() as c:
            old = c.execute('SELECT status FROM import_jobs WHERE digest=?', (digest,)).fetchone()
            count = c.execute("SELECT COUNT(*) FROM import_jobs WHERE status IN ('queued','running','partial')").fetchone()[0]
        if not old:
            if count >= _MAX_PENDING:
                raise RuntimeError('File d’import pleine (8 fichiers). Attendez la fin d’un import.')
            source = _archive(raw, digest, filename)
            with connect() as c:
                c.execute("""INSERT OR IGNORE INTO import_jobs
                    (digest,filename,source_file,offset_minutes,actor,status,updated_at)
                    VALUES(?,?,?,?,?,'queued',?)""",
                    (digest,Path(filename).name,source,offset,actor,now()))
    _ensure_import_processing()
    return job_status(digest)


def enqueue_retry(digest, actor):
    with _QUEUE_LOCK:
        with connect() as c:
            row=c.execute('SELECT status FROM import_jobs WHERE digest=?',(str(digest),)).fetchone()
            if not row:raise ValueError('Import introuvable.')
            if row['status'] in ('failed','partial'):
                count=c.execute("SELECT COUNT(*) FROM import_jobs WHERE status IN ('queued','running')").fetchone()[0]
                if count>=_MAX_PENDING:raise RuntimeError('File d’import pleine. Réessayez après un import.')
                c.execute("UPDATE import_jobs SET status='queued',actor=?,next_retry=0,error='',updated_at=? WHERE digest=?",
                          (actor,now(),str(digest)))
    _ensure_import_processing()
    return job_status(digest)


def job_status(digest):
    with connect() as c:
        row = c.execute('SELECT status,result_json,steps_json,error FROM import_jobs WHERE digest=?',
                        (str(digest),)).fetchone()
    if not row: raise ValueError('Import introuvable.')
    result = json.loads(row['result_json']) if row['status'] not in ('queued','running') else {}
    result.pop('_groups', None)
    result.update(job_id=digest, status=row['status'], steps=json.loads(row['steps_json']),
                  error=row['error'], source_saved=True)
    return result


def _external_import_service_healthy():
    """Return True only when the dedicated Import service has a fresh heartbeat."""
    from service_mode import external_services_enabled
    if not external_services_enabled():
        return False
    try:
        import service_state
        state=service_state.public_status()
        for row in state.get('services',()):
            if row.get('service')=='import':
                return bool(row.get('healthy'))
    except Exception:
        return False
    return False


def _ensure_import_processing():
    """V60: heavy imports never execute inside the Web/API process.

    In production service mode an upload can only be processed by the explicit
    local Importer.  The monolithic fallback is preserved for tests/manual
    development starts where NELYIO_EXTERNAL_SERVICES is not enabled.
    """
    from service_mode import external_services_enabled
    if external_services_enabled():
        return
    if not _external_import_service_healthy():
        start_import_worker()


def start_import_worker():
    global _WORKER
    with _WORKER_LOCK:
        if _WORKER is not None and _WORKER.is_alive(): return
        def drain():
            # Finite worker; startup/scanner resumes anything left after shutdown.
            while True:
                with connect() as c:
                    pending = c.execute("SELECT 1 FROM import_jobs WHERE status='queued' LIMIT 1").fetchone()
                if not pending: return
                retry_pending_jobs(limit=1)
                time.sleep(0.1)
        _WORKER = threading.Thread(target=drain, name='nelyio-import-worker', daemon=True)
        _WORKER.start()


def ensure_schema(c):
    # execute, not executescript: never commit the caller's transaction.
    c.execute('CREATE TABLE IF NOT EXISTS ingestion_sequences(name TEXT PRIMARY KEY,next_id INTEGER NOT NULL)')
    c.execute('''CREATE TABLE IF NOT EXISTS import_jobs(
        digest TEXT PRIMARY KEY, filename TEXT NOT NULL, source_file TEXT NOT NULL,
        offset_minutes INTEGER NOT NULL, actor TEXT NOT NULL, status TEXT NOT NULL,
        import_id INTEGER, attempts INTEGER NOT NULL DEFAULT 0, next_retry REAL NOT NULL DEFAULT 0,
        steps_json TEXT NOT NULL DEFAULT '{}', result_json TEXT NOT NULL DEFAULT '{}',
        error TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS import_reference_states(
        import_id INTEGER PRIMARY KEY, state TEXT NOT NULL, has_activities INTEGER NOT NULL,
        reasons_json TEXT NOT NULL, reviewed_by TEXT, reviewed_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS import_reference_choices(
        day TEXT PRIMARY KEY, activity_import_id INTEGER, call_import_id INTEGER)''')

def allocate_ids(c, table, count=1):
    """Never reuse IDs still present in the Details archive after a retention purge."""
    if table not in ('imports','activities'):raise ValueError('Séquence inconnue.')
    row=c.execute('SELECT next_id FROM ingestion_sequences WHERE name=?',(table,)).fetchone()
    if not row:
        highest=c.execute('SELECT COALESCE(MAX(id),0) FROM '+table).fetchone()[0]
        if table=='imports':highest=max(highest,c.execute('SELECT COALESCE(MAX(original_import_id),0) FROM retention_import_tombstones').fetchone()[0])
        import details_store
        # The Details backend is authoritative.  In PostgreSQL mode the local
        # Nelyio_Details.db file is only a migration/rollback copy and can be
        # stale; never derive future import IDs from that file.
        try:
            with details_store.connect_details() as source:
                if source.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='detail_events'").fetchone():
                    column='source_import_id' if table=='imports' else 'CAST(source_record_id AS INTEGER)'
                    archived=source.execute("SELECT COALESCE(MAX("+column+"),0) FROM detail_events WHERE event_source='export'").fetchone()[0]
                    highest=max(highest,int(archived or 0))
        except (sqlite3.Error, OSError):
            # Details can legitimately be unavailable during first schema
            # initialization; the operational sequence still remains safe.
            pass
        c.execute('INSERT INTO ingestion_sequences VALUES(?,?)',(table,highest+1))
    # Include explicit IDs added by supported legacy maintenance/import scripts.
    minimum=c.execute('SELECT COALESCE(MAX(id),0)+1 FROM '+table).fetchone()[0]
    first=max(minimum,c.execute('SELECT next_id FROM ingestion_sequences WHERE name=?',(table,)).fetchone()[0])
    c.execute('UPDATE ingestion_sequences SET next_id=? WHERE name=?',(first+count,table))
    return first


def reference_status(c, ident):
    row=c.execute('SELECT * FROM import_reference_states WHERE import_id=?',(ident,)).fetchone()
    if not row:return dict(state='accepted',has_activities=True,reasons=[])
    return dict(state=row['state'],has_activities=bool(row['has_activities']),reasons=json.loads(row['reasons_json']))

def _choose(c, ident, day, has_activities, has_calls):
    previous=c.execute('SELECT * FROM import_reference_choices WHERE day=?',(day,)).fetchone()
    def current(table):
        row=c.execute('SELECT import_id FROM '+table+' WHERE day=?',(day,)).fetchone()
        return row[0] if row else None
    activity=ident if has_activities else (previous['activity_import_id'] if previous else current('coverage'))
    calls=ident if has_calls else (previous['call_import_id'] if previous else current('call_coverage'))
    c.execute('INSERT OR REPLACE INTO import_reference_choices VALUES(?,?,?)',(day,activity,calls))

def assess_reference(c, ident, day, items, calls, *, activate=True):
    """A smaller/narrower export is stored, never silently made authoritative."""
    reasons=[]
    old=c.execute('SELECT import_id FROM coverage WHERE day=?',(day,)).fetchone()
    if old and items:
        rows=c.execute('SELECT agent,start,end FROM activities WHERE import_id=?',(old[0],)).fetchall()
        if len(items)<len(rows):reasons.append('Moins d’activités que la référence actuelle.')
        if {r['agent'] for r in rows}-{r[0] for r in items}:reasons.append('Des agents de la référence actuelle sont absents.')
        if rows and (min(r[2] for r in items)>min(r['start'] for r in rows) or max(r[3] for r in items)<max(r['end'] for r in rows)):
            reasons.append('La plage d’activité est plus courte.')
    old_calls=c.execute('SELECT import_id FROM call_coverage WHERE day=?',(day,)).fetchone()
    if old_calls:
        count=c.execute('SELECT COUNT(*) FROM phone_calls WHERE import_id=?',(old_calls[0],)).fetchone()[0]
        if calls is None and items:reasons.append('Les appels de la référence actuelle ne sont pas fournis.')
        elif calls is not None:
            if len(calls)<count:reasons.append('Moins d’appels que la référence actuelle.')
            previous_ids={r[0] for r in c.execute('SELECT call_id FROM phone_calls WHERE import_id=?',(old_calls[0],))}
            if previous_ids-{r[0] for r in calls}:reasons.append('Des appels de la référence actuelle sont absents.')
    state='review' if reasons else ('accepted' if activate else 'staged')
    c.execute('INSERT INTO import_reference_states VALUES(?,?,?,?,NULL,NULL)',(ident,state,int(bool(items)),json.dumps(reasons,ensure_ascii=False)))
    if not reasons and activate:_choose(c,ident,day,bool(items),calls is not None)
    return dict(state=state,has_activities=bool(items),has_calls=calls is not None,reasons=reasons)

def _archive(raw, digest, filename):
    folder=ctx.db_path().parent/'import_archive';folder.mkdir(parents=True,exist_ok=True)
    suffix='.zip' if filename.lower().endswith('.zip') else '.csv'
    target=folder/(digest+suffix)
    if target.exists():
        if hashlib.sha256(target.read_bytes()).digest()==hashlib.sha256(raw).digest():return target.name
        raise ValueError('Archive source différente de son empreinte : intervention requise.')
    fd, temp=tempfile.mkstemp(prefix='.pending-',dir=folder)
    try:
        with os.fdopen(fd,'wb') as stream:
            stream.write(raw);stream.flush();os.fsync(stream.fileno())
        os.replace(temp,target)
    finally:
        if os.path.exists(temp):os.unlink(temp)
    return target.name

def _save_step(digest, steps, name, value):
    steps[name]=value
    with connect() as c:c.execute('UPDATE import_jobs SET steps_json=?,updated_at=? WHERE digest=?',(json.dumps(steps,ensure_ascii=False),now(),digest))

def _activate_staged_reference(ident, actor):
    """Atomically expose a fully prepared import to readers."""
    ident=int(ident)
    with connect() as c:
        row=c.execute('SELECT id,reference_day FROM imports WHERE id=?',(ident,)).fetchone()
        if not row: raise ValueError('Import staged introuvable.')
        ref=reference_status(c,ident)
        if ref.get('state')=='review':
            return dict(activated=False,reason='review',day=row['reference_day'])
        has_activities=bool(c.execute('SELECT 1 FROM activities WHERE import_id=? LIMIT 1',(ident,)).fetchone())
        has_calls=bool(c.execute('SELECT 1 FROM call_imports WHERE import_id=?',(ident,)).fetchone())
        if not has_activities and not has_calls:
            raise RuntimeError('Import staged sans donnée utilisable.')
        c.execute("UPDATE import_reference_states SET state='accepted' WHERE import_id=?",(ident,))
        _choose(c,ident,row['reference_day'],has_activities,has_calls)
        from supervision_db import repair_reference_coverage
        coverage=repair_reference_coverage(c)
        audit(c,actor,'REFERENCE_STAGED_COMMIT',str(ident)+' / '+str(row['reference_day']))
        return dict(activated=True,day=row['reference_day'],has_activities=has_activities,has_calls=has_calls,coverage=coverage)


def run_import(raw, filename, offset, actor, core, *, retry=False):
    offset=int(offset)
    if not -720<=offset<=840:raise ValueError('Décalage UTC invalide.')
    if not 0<len(raw)<=100*1024*1024:raise ValueError('Fichier vide ou supérieur à 100 Mo.')
    if not filename.lower().endswith(('.zip','.stats.agent.csv')):raise ValueError('Choisir un ZIP SIMPLIFY2 ou Stats.AGENT.csv.')
    if (ctx.admin_db_path().parent/'logs'/'retention.lock').exists():raise RuntimeError('Archivage/rétention en cours : réessayer après sa fin.')
    digest=hashlib.sha256(raw+str(offset).encode()).hexdigest()
    total_started=time.perf_counter()
    from process_lock import named_lock
    with named_lock('support-write', timeout=30.0):
      with _RUN_LOCK:
          source=_archive(raw,digest,filename)
          needs_call_detail_enrichment=False
          needs_call_relation_enrichment=False
          with connect() as c:
              ensure_schema(c)
              c.execute('''INSERT OR IGNORE INTO import_jobs(digest,filename,source_file,offset_minutes,actor,status,updated_at)
                           VALUES(?,?,?,?,?,'running',?)''',(digest,Path(filename).name,source,offset,actor,now()))
              job=dict(c.execute('SELECT * FROM import_jobs WHERE digest=?',(digest,)).fetchone())
              cached=json.loads(job['result_json'] or '{}')
              stored=c.execute('SELECT id FROM imports WHERE digest=?',(digest,)).fetchone()
              if stored:
                  expected=c.execute('SELECT rows_count FROM call_imports WHERE import_id=?',(stored[0],)).fetchone()
                  if expected and int(expected[0] or 0)>0:
                      # V60.4 ARCH suspect-call enrichment: old databases may
                      # already contain phone_calls but not the new Call-ID
                      # extension rows. A duplicate import must replay ODCalls
                      # once in that situation instead of returning the cached
                      # result and falsely reporting enrichment.
                      try:
                          actual=int(c.execute('SELECT COUNT(*) FROM phone_call_details WHERE import_id=?',(stored[0],)).fetchone()[0] or 0)
                      except Exception:
                          actual=0
                      needs_call_detail_enrichment=actual<int(expected[0] or 0)
                      try:
                          rel_marker=c.execute('SELECT 1 FROM phone_call_relation_imports WHERE import_id=?',(stored[0],)).fetchone()
                      except Exception:
                          rel_marker=None
                      needs_call_relation_enrichment=not bool(rel_marker)
              if job['status']=='completed' and not retry and not needs_call_detail_enrichment and not needs_call_relation_enrichment:
                  if stored and cached.get('import_id')==stored[0]:
                      cached.pop('_groups',None)
                      cached.update(duplicate=True,rows=0,calls=0,reference=reference_status(c,stored[0]))
                      return cached
              c.execute("UPDATE import_jobs SET status='running',attempts=attempts+1,updated_at=? WHERE digest=?",(now(),digest))
          steps={};step_times={}
          bundle_state=import_bundle.begin(raw,filename);bundle=bundle_state[1]
          try:
              cached=json.loads(job['result_json'] or '{}')
              with connect() as c:
                  stored=c.execute('SELECT id FROM imports WHERE digest=?',(digest,)).fetchone()
              if stored and cached.get('import_id')==stored[0] and job['status'] in ('completed','partial') and not needs_call_detail_enrichment and not needs_call_relation_enrichment:
                  result=cached
                  result.update(duplicate=True,rows=0,calls=0)
                  with connect() as c:result['reference']=reference_status(c,stored[0])
                  step_times['core']=0.0
              else:
                  started=time.perf_counter()
                  result=core(raw,filename,offset,actor)
                  step_times['core']=round(time.perf_counter()-started,4)
              groups=result.pop('_groups',{})
              core_performance=result.pop('_core_performance',{})
              ident=result.get('import_id')
              _save_step(digest,steps,'source',dict(state='ok'))
              _save_step(digest,steps,'support',dict(state='ok'))
              result['snapshot_mode']='stable_reference_until_commit'
              if result.get('purged'):
                  status='purged'
              elif result.get('reference',{}).get('state')=='review':
                  status='review'
              else:
                  import export_import as ei
                  previous_steps=json.loads(job['steps_json'] or '{}')

                  def run_step(name, action, *, reuse=True):
                      if reuse and previous_steps.get(name,{}).get('state')=='ok' and job['status'] in ('completed','partial'):
                          step_times[name]=0.0
                          _save_step(digest,steps,name,dict(state='ok',reused=True))
                          return True
                      started=time.perf_counter()
                      try:
                          value=action()
                          if isinstance(value,dict) and (value.get('ok') is False or value.get('available') is False or value.get('error')):
                              raise RuntimeError(value.get('error') or 'Étape indisponible.')
                          result[name]=value
                          _save_step(digest,steps,name,dict(state='ok'))
                          return True
                      except Exception as exc:
                          from error_log import log_unexpected_error
                          log_unexpected_error('import_workflow.'+name)
                          result[name]={'ok':False,'error':str(exc)}
                          _save_step(digest,steps,name,dict(state='error',message=str(exc)))
                          return False
                      finally:
                          step_times[name]=round(time.perf_counter()-started,4)

                  # Phase 1 - critical staging. Readers still see the previous
                  # coverage while Call/Quality facts are prepared. Details is
                  # deliberately not critical: it has its own active-reference
                  # projection and can finish after the atomic KPI/call switch.
                  staging=[
                      ('quality_metrics',lambda:__import__('quality_metrics').ingest_inbound(raw,filename,ident,offset)),
                      ('quality_agents',lambda:__import__('quality_agents').ingest(raw,filename,ident,offset)),
                  ]
                  staging_ok=True
                  for name,action in staging:
                      staging_ok=run_step(name,action) and staging_ok

                  # Phase 2 - one short atomic pointer switch. No partially
                  # imported day ever becomes authoritative.
                  if staging_ok:
                      staging_ok=run_step('snapshot_commit',lambda:_activate_staged_reference(ident,actor),reuse=False) and staging_ok
                  else:
                      result['snapshot_commit']=dict(activated=False,reason='staging_error')
                      _save_step(digest,steps,'snapshot_commit',dict(state='skipped',reason='staging_error'))

                  # Phase 3 - noncritical enrichment after the switch. The Web
                  # already reads the new authoritative Call/Quality snapshot.
                  # A slow Details archive cannot hold production readers.
                  if staging_ok:
                      details_ok=run_step('details_sync',lambda:ei.details_store.sync_from_sources(
                          ctx.db_path(),ctx.admin_db_path(),ei.TECH_LABELS,force=True,import_ids=[ident]))
                      if details_ok:
                          run_step('details_active_refs',lambda:ei.details_store.sync_active_references(ctx.db_path()))
                      else:
                          result['details_active_refs']=dict(updated=False,reason='details_sync_failed')
                          _save_step(digest,steps,'details_active_refs',dict(state='skipped',reason='details_sync_failed'))
                      post=[
                          ('directory',lambda:ei.sync_admin_directory_from_support('SUPPORT_SYNC')),
                          ('quality_import',lambda:ei.update_quality_from_export(raw,filename)),
                          ('group_import',lambda:ei.sync_admin_groups_from_export(groups,'SUPPORT_GROUP_SYNC')),
                      ]
                      for name,action in post:
                          run_step(name,action)
                  else:
                      for name in ('details_sync','details_active_refs','directory','quality_import','group_import'):
                          result[name]=dict(updated=False,reason='snapshot_not_committed')
                          _save_step(digest,steps,name,dict(state='skipped',reason='snapshot_not_committed'))

                  status='partial' if any(v.get('state')=='error' for v in steps.values()) or not staging_ok else 'completed'
              result.update(status=status,job_id=digest,steps=steps,source_saved=True)
              result['performance']={
                  'total_seconds':round(time.perf_counter()-total_started,4),
                  'core_seconds':core_performance,
                  'steps_seconds':step_times,
                  'zip_cache':bundle.stats(),
              }
              if status=='review':result['message']='Export conservé à vérifier. La référence précédente reste active.'
              elif status=='partial':
                  if result.get('snapshot_commit',{}).get('activated'):
                      result['message']='Import principal actif. Un enrichissement secondaire (par ex. Détails) reste à terminer ; le fichier source est conservé pour reprise.'
                  else:
                      result['message']='Import partiel : la référence précédente reste active car la bascule snapshot n a pas été validée. Le fichier source est conservé.'
              elif status=='purged':result['message']='Export déjà archivé par la rétention ; aucune donnée réintroduite.'
              else:result['message']='Import terminé : snapshot validé puis bascule atomique vers la nouvelle référence.'
              with connect() as c:
                  c.execute('''UPDATE import_jobs SET status=?,import_id=?,result_json=?,error='',next_retry=?,updated_at=? WHERE digest=?''',
                      (status,ident,json.dumps(dict(result,_groups={k:sorted(v) for k,v in groups.items()}),ensure_ascii=False),time.time()+min(300,10*2**min(job['attempts'],5)),now(),digest))
              return result
          except Exception as exc:
              with connect() as c:c.execute("UPDATE import_jobs SET status='failed',error=?,updated_at=? WHERE digest=?",(str(exc),now(),digest))
              raise
          finally:
              import_bundle.end(bundle_state)

def retry_import_job(digest, actor, *, skip_terminal=False):
    with _RUN_LOCK:
        with connect() as c:
            ensure_schema(c)
            row=c.execute('SELECT * FROM import_jobs WHERE digest=?',(str(digest),)).fetchone()
            if not row:raise ValueError('Import introuvable.')
            job=dict(row)
            # A background queue consumer may have selected this job just before
            # another process completed it. Explicit operator retry/reference
            # actions still need the normal retry path.
            if skip_terminal and job['status'] in ('completed','review','purged'):
                return job_status(digest)
        folder=(ctx.db_path().parent/'import_archive').resolve()
        source=(folder/job['source_file']).resolve()
        try:
            if source.parent!=folder or not source.is_file():raise ValueError('Source archivée introuvable.')
            raw=source.read_bytes()
            if hashlib.sha256(raw+str(job['offset_minutes']).encode()).hexdigest()!=job['digest']:raise ValueError('Empreinte de la source incorrecte.')
        except (ValueError,OSError) as exc:
            with connect() as c:c.execute("UPDATE import_jobs SET status='failed',error=?,updated_at=? WHERE digest=?",(str(exc),now(),digest))
            raise
        from export_import import _import_export
        return run_import(raw,job['filename'],job['offset_minutes'],actor,_import_export,retry=True)

def retry_pending_jobs(limit=2):
    # Never hold an HTTP reader behind a running import, nor replay a stale
    # selection after another worker already completed it.
    if not _RUN_LOCK.acquire(blocking=False): return
    try:
        with connect() as c:
            jobs=[(r[0], r[1]) for r in c.execute("SELECT digest,actor FROM import_jobs WHERE status IN ('queued','partial','running') AND next_retry<=? ORDER BY CASE status WHEN 'queued' THEN 0 ELSE 1 END,updated_at LIMIT ?",(time.time(),limit))]
        for digest, actor in jobs:
            try:retry_import_job(digest,actor,skip_terminal=True)
            except Exception:
                from error_log import log_unexpected_error
                log_unexpected_error('import_workflow.retry')
    finally:
        _RUN_LOCK.release()


def activate_reference(ident, actor):
    """Explicit write action. Older references may be restored without data deletion."""
    ident=int(ident)
    with _RUN_LOCK:
        with connect() as c:
            ensure_schema(c)
            row=c.execute('SELECT * FROM imports WHERE id=?',(ident,)).fetchone()
            if not row:raise ValueError('Import introuvable ou purgé.')
            source_job=c.execute('SELECT * FROM import_jobs WHERE import_id=?',(ident,)).fetchone()
            if source_job:
                folder=(ctx.db_path().parent/'import_archive').resolve()
                source=(folder/source_job['source_file']).resolve()
                if source.parent!=folder or not source.is_file():raise ValueError('Source archivée introuvable ; référence inchangée.')
                if hashlib.sha256(source.read_bytes()+str(source_job['offset_minutes']).encode()).hexdigest()!=source_job['digest']:
                    raise ValueError('Empreinte de la source incorrecte ; référence inchangée.')
            has_activities=bool(c.execute('SELECT 1 FROM activities WHERE import_id=? LIMIT 1',(ident,)).fetchone())
            has_calls=bool(c.execute('SELECT 1 FROM call_imports WHERE import_id=?',(ident,)).fetchone())
            if not has_activities and not has_calls:raise ValueError('Import sans données utilisables.')
            c.execute("INSERT OR REPLACE INTO import_reference_states VALUES(?,'accepted',?,'[]',?,?)",(ident,int(has_activities),actor,now()))
            _choose(c,ident,row['reference_day'],has_activities,has_calls)
            from supervision_db import repair_reference_coverage
            repair_reference_coverage(c)
            audit(c,actor,'REFERENCE_SELECTED',str(ident)+' / '+str(row['reference_day']))
            job=c.execute('SELECT digest FROM import_jobs WHERE import_id=?',(ident,)).fetchone()
        if job:return retry_import_job(job[0],actor)
        import details_store
        details_store.sync_from_sources(ctx.db_path(),ctx.admin_db_path(),ctx.tech_labels(),force=True)
        return dict(status='completed',import_id=ident,message='Référence sélectionnée.')

def workflow_status():
    with connect() as c:
        ensure_schema(c)
        jobs=[]
        for row in c.execute('SELECT digest,filename,status,import_id,attempts,steps_json,error,updated_at FROM import_jobs ORDER BY updated_at DESC LIMIT 10'):
            r=dict(row);r['steps']=json.loads(r.pop('steps_json'));jobs.append(r)
        counts=dict(c.execute('SELECT status,COUNT(*) FROM import_jobs GROUP BY status'))
        references=[]
        for row in c.execute('''SELECT i.id,i.reference_day,i.rows_count,coalesce(ci.rows_count,0) calls,ci.import_id IS NOT NULL has_calls,
                EXISTS(SELECT 1 FROM coverage WHERE import_id=i.id) activity_active,
                EXISTS(SELECT 1 FROM call_coverage WHERE import_id=i.id) calls_active
                FROM imports i LEFT JOIN call_imports ci ON ci.import_id=i.id ORDER BY i.id DESC LIMIT 20'''):
            r=dict(row);r.update(reference_status(c,r['id']));references.append(r)
    try:
        from service_state import BUILD as runtime_build
    except Exception:
        runtime_build = 'unknown'
    return dict(jobs=jobs,job_counts=counts,references=references,build=runtime_build)
