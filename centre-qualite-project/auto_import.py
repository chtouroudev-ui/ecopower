"""Background import-folder scanner for Support Nelyio."""
from pathlib import Path
import threading, time, zipfile, hashlib
import db_compat as sqlite3
from error_log import log_unexpected_error
from nelyio_time import DISPLAY_TIMEZONE, france_offset_for_day
import supervision_context as state
from supervision_db import connect, config, now, _reference_day_from_name
from export_import import import_export

_DEFAULT_LOCK = threading.Lock()
_DEFAULT_STOP = threading.Event()
_DEFAULT_ERRORS = {}

def automatic_import_offset(filename=None):
    """Choose the source offset, using the dated filename when possible."""
    ref=_reference_day_from_name(filename) if filename else ''
    if ref:
        return france_offset_for_day(ref)
    with connect() as c:
        row=c.execute('SELECT offset_minutes FROM imports WHERE offset_minutes IS NOT NULL ORDER BY id DESC LIMIT 1').fetchone()
    return int(row[0]) if row else int(config()['export_offset'])

def _auto_import_log(filename,status,offset=0,activities=0,calls=0,detail=''):
    with connect() as c:
        c.execute('''INSERT INTO auto_import_log(filename,processed_at,status,offset_minutes,activities,calls,detail)
                     VALUES(?,?,?,?,?,?,?)''',(filename,now(),status,int(offset or 0),int(activities or 0),int(calls or 0),str(detail)[:2000]))

def auto_import_status():
    from service_mode import external_services_enabled
    if external_services_enabled():
        # V60 production: never scan/hash/import from a Web GET. The operator
        # uses the standalone local importer instead. Keep this endpoint cheap
        # so Support/Calls pages cannot be slowed by the import folder.
        return dict(mode='manual-v60',manual_importer=True,folder='import',
                    absolute_path=str(state.import_dir_path()),pending=[],recent=[],
                    job_counts={},active=[],retry_due=[],
                    message='Import separe du Web : utiliser OPEN_NELYIO_IMPORTER.bat sur le serveur.')
    state.import_dir_path().mkdir(parents=True,exist_ok=True)
    pending=[]
    try:
        pending=[p.name for p in sorted(state.import_dir_path().iterdir()) if p.is_file() and _is_auto_import_file(p)]
    except OSError:
        log_unexpected_error('supervision.auto_import_status.L557')
        pass
    with connect() as c:
        logs=[dict(r) for r in c.execute('SELECT * FROM auto_import_log ORDER BY id DESC LIMIT 10')]
    from import_workflow import workflow_status
    workflow=workflow_status()
    return dict(**workflow,folder='import',absolute_path=str(state.import_dir_path()),offset_minutes=automatic_import_offset(),offset_mode='filename_date',display_timezone=DISPLAY_TIMEZONE,pending=pending,recent=logs)

def _is_auto_import_file(path):
    name=path.name.lower()
    return name in ('group','group.har') or name.endswith('.zip') or name.endswith('.stats.agent.csv')

def process_auto_import_file(path):
    """Import one stable file and delete it only after a successful DB commit."""
    path=Path(path)
    if not _is_auto_import_file(path):return None
    stat_before=path.stat()
    if stat_before.st_size<=0:raise ValueError('Fichier vide.')
    if stat_before.st_size>100*1024*1024:raise ValueError('Fichier supérieur à 100 Mo.')
    if time.time()-stat_before.st_mtime<int(state.facade_attr('AUTO_IMPORT_MIN_AGE_SECONDS',3)):return None
    raw=path.read_bytes()
    stat_after=path.stat()
    if (stat_before.st_size,stat_before.st_mtime_ns)!=(stat_after.st_size,stat_after.st_mtime_ns):return None
    if path.name.lower() in ('group','group.har'):
        from group_har_import import ingest
        with state.facade_attr('IMPORT_LOCK',_DEFAULT_LOCK):
            result=ingest(raw)
        _auto_import_log(path.name,'IMPORTED',detail=result['message'])
        current=path.stat()
        if (current.st_size,current.st_mtime_ns)==(stat_after.st_size,stat_after.st_mtime_ns):path.unlink()
        state.facade_attr('_AUTO_IMPORT_ERROR_SIGNATURES',_DEFAULT_ERRORS).pop(str(path),None)
        return result
    offset=automatic_import_offset(path.name)
    from import_workflow import ensure_schema
    digest=hashlib.sha256(raw+str(offset).encode()).hexdigest()
    with connect() as c:
        ensure_schema(c)
        job=c.execute('SELECT status,next_retry FROM import_jobs WHERE digest=?',(digest,)).fetchone()
    if job and job['status'] in ('queued','partial','running') and job['next_retry']>time.time():return None
    with state.facade_attr('IMPORT_LOCK',_DEFAULT_LOCK):
        result=import_export(raw,path.name,offset,'AUTO_IMPORT')
    status={'partial':'PARTIAL','review':'REVIEW','purged':'PURGED'}.get(result.get('status')) or ('DUPLICATE' if result.get('duplicate') else 'IMPORTED')
    _auto_import_log(path.name,status,offset,result.get('rows',0),result.get('calls',0),f"Jours: {', '.join(result.get('days',[]))}. {result.get('message','')}")
    # A source copied over the incoming file during import must not be deleted.
    if result.get('status') in ('completed','review','purged') and result.get('source_saved'):
        current=path.stat()
        if (current.st_size,current.st_mtime_ns)==(stat_after.st_size,stat_after.st_mtime_ns):path.unlink()
    state.facade_attr('_AUTO_IMPORT_ERROR_SIGNATURES',_DEFAULT_ERRORS).pop(str(path),None)
    return result

def _queue_auto_import_file(path):
    """Discover a stable SIMPLIFY2 source without blocking the folder scanner.

    The old scanner called import_export() synchronously. One large/slow export
    could therefore prevent every later .export.zip in the folder from even
    being discovered. The durable import queue already archives the bytes before
    acknowledging the job, so folder discovery should only enqueue here; the
    Import Service (or its fallback worker) performs the heavy import.
    """
    path=Path(path)
    if not _is_auto_import_file(path) or path.name.lower() in ('group','group.har'):
        return None
    stat_before=path.stat()
    if stat_before.st_size<=0:raise ValueError('Fichier vide.')
    if stat_before.st_size>100*1024*1024:raise ValueError('Fichier supérieur à 100 Mo.')
    if time.time()-stat_before.st_mtime<int(state.facade_attr('AUTO_IMPORT_MIN_AGE_SECONDS',3)):return None
    raw=path.read_bytes()
    stat_after=path.stat()
    if (stat_before.st_size,stat_before.st_mtime_ns)!=(stat_after.st_size,stat_after.st_mtime_ns):return None
    offset=automatic_import_offset(path.name)
    digest=hashlib.sha256(raw+str(offset).encode()).hexdigest()
    with connect() as c:
        from import_workflow import ensure_schema
        ensure_schema(c)
        previous=c.execute('SELECT status FROM import_jobs WHERE digest=?',(digest,)).fetchone()
    from import_workflow import enqueue_import
    result=enqueue_import(raw,path.name,offset,'AUTO_IMPORT')
    status=str(result.get('status') or '').lower()

    # Only remove the watched-folder copy after a terminal success. Queued,
    # running, partial or failed sources remain visible to the operator; the
    # durable archive is still used for processing/retry.
    if status in ('completed','review','purged') and result.get('source_saved'):
        current=path.stat()
        if (current.st_size,current.st_mtime_ns)==(stat_after.st_size,stat_after.st_mtime_ns):path.unlink()

    if previous is None:
        label={'queued':'QUEUED','running':'RUNNING','completed':'IMPORTED','review':'REVIEW','purged':'PURGED','partial':'PARTIAL','failed':'ERROR'}.get(status,status.upper() or 'QUEUED')
        _auto_import_log(path.name,label,offset,result.get('rows',0),result.get('calls',0),result.get('message','Import placé dans la file durable.'))
    state.facade_attr('_AUTO_IMPORT_ERROR_SIGNATURES',_DEFAULT_ERRORS).pop(str(path),None)
    return result


def scan_auto_import_folder():
    """Scan the import folder once without running heavy SIMPLIFY2 parsing inline."""
    state.import_dir_path().mkdir(parents=True,exist_ok=True)
    results=[]
    for path in sorted(state.import_dir_path().iterdir()):
        if not path.is_file() or not _is_auto_import_file(path):continue
        try:
            if path.name.lower() in ('group','group.har'):
                result=process_auto_import_file(path)
            else:
                result=_queue_auto_import_file(path)
            if result is not None:results.append((path.name,result))
        except (OSError,ValueError,KeyError,UnicodeError,zipfile.BadZipFile,sqlite3.Error,RuntimeError) as exc:
            try:
                st=path.stat();signature=(st.st_size,st.st_mtime_ns,str(exc))
            except OSError:
                signature=('missing',str(exc))
            key=str(path)
            if state.facade_attr('_AUTO_IMPORT_ERROR_SIGNATURES',_DEFAULT_ERRORS).get(key)!=signature:
                state.facade_attr('_AUTO_IMPORT_ERROR_SIGNATURES',_DEFAULT_ERRORS)[key]=signature
                _auto_import_log(path.name,'ERROR',automatic_import_offset(path.name),0,0,str(exc))
    return results

def _auto_import_loop():
    while not state.facade_attr('AUTO_IMPORT_STOP',_DEFAULT_STOP).wait(float(state.facade_attr('AUTO_IMPORT_SCAN_SECONDS',10))):
        try:
            for filename,result in scan_auto_import_folder():
                print(f"Import auto SIMPLIFY2 : {filename} -> {result.get('rows',0)} activité(s), {result.get('calls',0)} appel(s)")
        except Exception as exc:
            log_unexpected_error('supervision._auto_import_loop.L612')
            print('Import auto SIMPLIFY2 :',exc)

def start_auto_importer():
    from service_mode import external_services_enabled
    if external_services_enabled():
        return None
    state.import_dir_path().mkdir(parents=True,exist_ok=True)
    # Startup must not wait for a backlog of large exports.
    current=state.facade_attr('AUTO_IMPORT_THREAD',None)
    if current and current.is_alive():return current
    state.facade_attr('AUTO_IMPORT_STOP',_DEFAULT_STOP).clear()
    thread=threading.Thread(target=_auto_import_loop,name='nelyio-support-auto-import',daemon=True)
    state.set_facade_attr('AUTO_IMPORT_THREAD',thread)
    thread.start()
    return thread

def stop_auto_importer():
    state.facade_attr('AUTO_IMPORT_STOP',_DEFAULT_STOP).set()

