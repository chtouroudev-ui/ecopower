"""HTTP route bridge for the modular supervision services."""
import hmac, io, sqlite3, threading, zipfile
from pathlib import Path
import details_store
from error_log import log_unexpected_error
import supervision_context as ctx
from supervision_db import config, save_config
from export_import import import_export
from auto_import import auto_import_status
from live_capture import ingest
from calls import calls_view
from support_views import view, support_view, diagnostic_incidents_view, add_note
from report_data import weekly_report_preview, weekly_report_details, weekly_report_pdf
from analytics import analytics_view
from support_filters import TECH_LABELS

_ROUTE_IMPORT_LOCK = threading.Lock()
_UPLOAD_SLOTS = threading.BoundedSemaphore(2)


def _quality_only_upload(raw, filename):
    """Return True when the manual upload is a configuration-only Quality source.

    Daily SIMPLIFY2 packages containing Stats.AGENT/ODCalls keep using the durable
    import workflow. Stand-alone Agents/Queues/Lines/Priority CSVs (or a ZIP that
    contains only those configuration files) are applied directly to the Quality
    catalogue so Group -> File -> ACTIVE Agent projection can be refreshed.
    """
    name=Path(str(filename or '').replace('\\','/')).name.lower()
    if name.endswith('.csv'):
        if name.endswith('.stats.agent.csv') or name.endswith('.odcalls.csv'):
            return False
        return any(token in name for token in ('agents.csv','agents.','agentlines.','agentqueues.','lines.','queues.','campaigns.','priorit'))
    if not name.endswith('.zip'):
        return False
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            names=[x.filename.lower() for x in z.infolist() if not x.is_dir()]
    except zipfile.BadZipFile:
        return False
    if any(x.endswith('.stats.agent.csv') or x.endswith('.odcalls.csv') for x in names):
        return False
    return any(x.endswith('.csv') and any(token in x for token in ('agents.','agentlines.','agentqueues.','lines.','queues.','campaigns.','priorit')) for x in names)


def _delegated_read(kind, qs, local):
    """Run expensive read-only views in the isolated Analytics worker in prod."""
    from service_mode import external_services_enabled
    if external_services_enabled():
        from analytics_rpc import delegated_view_remote
        # V60: heavy Support/Diagnostic reads never fall back into the Web
        # process. Keep authentication/navigation responsive under failure.
        return delegated_view_remote(kind, qs)
    return local(qs)

def _access(user,module,write=False):
    if not user:return False
    if user.get('role')=='admin':return True
    needed=2 if write else 1
    try:return int((user.get('permissions') or {}).get(module,0))>=needed
    except Exception:return False

def _iface(user,key,write=False):
    from access_control import has_interface
    return has_interface(user,key,write=write)

def _scoped(qs,user,multi=False):
    from access_control import scope_query,scope_multi_query
    return (scope_multi_query if multi else scope_query)(user, qs or {}, param='group')

def _catalog_scoped(payload,user):
    from access_control import filter_group_catalog_payload
    return filter_group_catalog_payload(user,payload)

def get_route(handler,path,qs,user):
    try:
        if path=='/api/supervision/support':
            if not _iface(user,'support'):return handler.send_json({'error':'Accès Support technique refusé'},403)
            return handler.send_json(_catalog_scoped(_delegated_read('support_view',_scoped(qs,user),support_view),user))
        if path=='/api/supervision/analytics':
            if not _iface(user,'analytics'):return handler.send_json({'error':'Accès Tendances techniques refusé'},403)
            from service_mode import external_services_enabled
            if external_services_enabled():
                from analytics_rpc import analytics_view_remote
                return handler.send_json(_catalog_scoped(analytics_view_remote(_scoped(qs,user)),user))
            return handler.send_json(_catalog_scoped(analytics_view(_scoped(qs,user)),user))
        if path=='/api/supervision/details':
            if not _iface(user,'details'):return handler.send_json({'error':'Accès Journal détaillé refusé'},403)
            return handler.send_json(_catalog_scoped(_delegated_read('details_view',_scoped(qs,user),details_view),user))
        if path=='/api/supervision/diagnostic-incidents':
            if not _iface(user,'disconnect_details'):return handler.send_json({'error':'Accès Détails des coupures refusé'},403)
            return handler.send_json(_catalog_scoped(_delegated_read('diagnostic_incidents',_scoped(qs,user),diagnostic_incidents_view),user))
        if path=='/api/supervision/incident-evidence':
            if not _iface(user,'disconnect_details'):return handler.send_json({'error':'Accès Détails des coupures refusé'},403)
            return handler.send_json(details_store.incident_evidence(_scoped(qs,user),ctx.db_path(),ctx.admin_db_path(),config()['display_offset'],TECH_LABELS))
        if path=='/api/supervision/calls':
            if not _iface(user,'calls'):return handler.send_json({'error':'Accès Recherche d’appels refusé'},403)
            if qs.get('phone') and not _access(user,'ani'):
                return handler.send_json({'error':'Droit Voir ANI complet requis pour rechercher un numéro appelant.'},403)
            scoped=dict(qs);scoped['_show_ani']=['1' if _access(user,'ani') else '0']
            from access_control import allowed_agent_ids
            allowed_agents=allowed_agent_ids(user)
            if allowed_agents is not None: scoped['_allowed_agents']=sorted(allowed_agents)
            return handler.send_json(_delegated_read('calls_view',scoped,ctx.facade_attr('calls_view',calls_view)))
        if path=='/api/supervision/view':
            if not _iface(user,'support'):return handler.send_json({'error':'Accès Support technique refusé'},403)
            return handler.send_json(_catalog_scoped(_delegated_read('supervision_view',_scoped(qs,user),view),user))
        if path=='/api/supervision/report-preview':
            if not _iface(user,'reports'):return handler.send_json({'error':'Accès Rapports refusé'},403)
            return handler.send_json(weekly_report_preview(_scoped(qs,user,multi=True),user))
        if path=='/api/supervision/report-details':
            if not _iface(user,'reports'):return handler.send_json({'error':'Accès Rapports refusé'},403)
            return handler.send_json(weekly_report_details(_scoped(qs,user,multi=True),user))
        if path=='/api/supervision/report.pdf':
            if not _iface(user,'reports'):return handler.send_json({'error':'Accès Rapports refusé'},403)
            payload,filename=weekly_report_pdf(_scoped(qs,user,multi=True),user)
            return handler.send_bytes(payload,'application/pdf',extra={'Content-Disposition':f'attachment; filename="{filename}"'})
        if path=='/api/supervision/auto-import':
            if not (_iface(user,'support') or _iface(user,'calls')):return handler.send_json({'error':'Accès Support ou Recherche d’appels requis'},403)
            if qs.get('job_id'):
                from import_workflow import job_status
                return handler.send_json(job_status(qs['job_id'][0]))
            return handler.send_json(auto_import_status())
        if path=='/api/supervision/config':
            if not _iface(user,'support',True):return handler.send_json({'error':'Droit de modification Support requis'},403)
            return handler.send_json(config(True))
        return handler.send_json({'error':'not found'},404)
    except __import__('access_control').ScopeDenied as e:return handler.send_json({'error':str(e)},403)
    except RuntimeError as e:return handler.send_json({'error':str(e)},503)
    except (ValueError,sqlite3.Error) as e:
        if isinstance(e, sqlite3.Error): log_unexpected_error('supervision.get_route.L904')
        return handler.send_json({'error':str(e)},400)

def post_route(handler,path,qs,user):
    try:
        if path=='/api/supervision/import':
            if not (_iface(user,'support',True) or _iface(user,'calls',True)):
                return handler.send_json({'error':'Droit de modification Support ou Recherche d’appels requis'},403)
            action=qs.get('action',['upload'])[0]
            if action in ('retry','reference'):
                d=handler.read_json()
                if not isinstance(d,dict):raise ValueError('Objet JSON invalide')
                from import_workflow import enqueue_retry, activate_reference
                if action=='retry':return handler.send_json(enqueue_retry(str(d.get('job_id','')),user['username']),202)
                return handler.send_json(activate_reference(int(d.get('import_id',0)),user['username']))
            if action!='upload':raise ValueError('Action d’import inconnue.')
            from service_mode import external_services_enabled
            if external_services_enabled():
                return handler.send_json({
                    'error':'V60 : les imports lourds sont separes du serveur Web. Lancez OPEN_NELYIO_IMPORTER.bat sur le serveur Nelyio.'
                },409)
            n=int(handler.headers.get('Content-Length','0'))
            if not 0<n<=100*1024*1024:raise ValueError('Fichier limité à 100 Mo.')
            if not _UPLOAD_SLOTS.acquire(blocking=False):
                handler.close_connection=True
                return handler.send_json({'error':'Deux transferts sont déjà en cours. Réessayez dans quelques instants.'},503)
            try:
                raw=handler.rfile.read(n)
                if len(raw)!=n:raise ValueError('Fichier incomplet : import annulé.')
                filename=qs.get('filename',[''])[0]
                if _quality_only_upload(raw,filename):
                    from quality_service import update_quality_from_export
                    result=update_quality_from_export(raw,filename)
                    result.update(status='completed',quality_only=True,rows=0,calls=0,skipped=0,days=[])
                else:
                    from import_workflow import enqueue_import
                    result=enqueue_import(raw,filename,qs.get('offset',[''])[0],user['username'])
            finally:
                _UPLOAD_SLOTS.release()
            return handler.send_json(result,202)
        d=handler.read_json()
        if not isinstance(d,dict):return handler.send_json({'error':'Objet JSON invalide'},400)
        if path=='/api/supervision/config':
            if not _iface(user,'support',True):return handler.send_json({'error':'Droit de modification Support requis'},403)
            return handler.send_json(save_config(d,user['username']))
        if path=='/api/supervision/note':
            module='calls' if str(d.get('key','')).startswith('call:') else 'support'
            iface='calls' if module=='calls' else 'support'
            if not _iface(user,iface,True):return handler.send_json({'error':'Droit de modification requis pour cette interface'},403)
            return handler.send_json(add_note(d,user['username']))
        return handler.send_json({'error':'not found'},404)
    except __import__('access_control').ScopeDenied as e:return handler.send_json({'error':str(e)},403)
    except RuntimeError as e:return handler.send_json({'error':str(e)},503)
    except (ValueError,KeyError,TypeError,UnicodeError,zipfile.BadZipFile,sqlite3.Error) as e:
        if isinstance(e, sqlite3.Error): log_unexpected_error('supervision.post_route.L926')
        return handler.send_json({'error':str(e)},400)

def bridge_route(handler):
    supplied=handler.headers.get('X-Nelyio-Capture-Key','')
    if not supplied or not hmac.compare_digest(supplied,config(True)['bridge_key']):
        return handler.send_json({'error':'Clé de capture invalide'},403)
    try:
        d=handler.read_json()
        if not isinstance(d,dict):return handler.send_json({'error':'Objet JSON invalide'},400)
        return handler.send_json(ingest(d))
    except (ValueError,KeyError,TypeError,sqlite3.Error) as e:
        if isinstance(e, sqlite3.Error): log_unexpected_error('supervision.bridge_route.L936')
        return handler.send_json({'error':str(e)},400)

def details_view(qs):
    # Dedicated archive: the Details interface reads Nelyio_Details.db only.
    cfg=config()
    return details_store.details_view(qs,ctx.db_path(),ctx.admin_db_path(),cfg['display_offset'],TECH_LABELS,cfg)

