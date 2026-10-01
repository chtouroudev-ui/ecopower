"""Quality read and configuration-import endpoints; authorization is in Handler."""
from pathlib import Path
import zipfile
from quality_service import load_quality_priorities, update_quality_from_export
from quality_importer import MAX_BYTES

class QualityRoutesMixin:
    def _quality_read(self, kind, query, local):
        """Keep CPU/SQL-heavy Quality reads out of the Web process in prod."""
        from service_mode import external_services_enabled
        if external_services_enabled():
            from analytics_rpc import delegated_view_remote
            # V60: never execute a heavy analytical query in the Web process.
            # A fast service error is safer than starving login/navigation.
            return delegated_view_remote(kind, query)
        return local(query)

    def _scoped_quality_query(self, query, user):
        if user is None:
            return dict(query or {})
        from access_control import scope_query
        return scope_query(user, query or {}, param='group')

    def _scoped_quality_payload(self, payload, user):
        if user is None:
            return payload
        from access_control import filter_group_catalog_payload
        return filter_group_catalog_payload(user, payload)

    def api_quality_distributions(self, query, user=None):
        from quality_distributions import view
        try:
            scoped=self._scoped_quality_query(query,user)
            return self.send_json(self._scoped_quality_payload(self._quality_read('quality_distributions', scoped, view),user))
        except __import__('access_control').ScopeDenied as exc:
            return self.send_json({'error':str(exc)},403)
        except (ValueError, TypeError) as exc:
            return self.send_json({'error':str(exc)},400)
        except Exception:
            from error_log import log_unexpected_error
            log_unexpected_error('quality.distributions')
            return self.send_json({'error':'Distributions indisponibles ; consulter le journal serveur.'},500)

    def api_quality_agents(self, query, user=None):
        from quality_agents import view
        try:
            scoped=self._scoped_quality_query(query,user)
            return self.send_json(self._scoped_quality_payload(self._quality_read('quality_agents', scoped, view),user))
        except __import__('access_control').ScopeDenied as exc:
            return self.send_json({'error':str(exc)},403)
        except (ValueError, TypeError) as exc:
            return self.send_json({"error": str(exc)}, 400)
        except Exception:
            from error_log import log_unexpected_error
            log_unexpected_error("quality.agents")
            return self.send_json({"error": "Activité Qualité indisponible ; consulter le journal serveur."}, 500)

    def api_quality_overview(self, query, user=None):
        from quality_metrics import overview
        try:
            scoped=self._scoped_quality_query(query,user)
            return self.send_json(self._scoped_quality_payload(self._quality_read('quality_overview', scoped, overview),user))
        except __import__('access_control').ScopeDenied as exc:
            return self.send_json({'error':str(exc)},403)
        except (ValueError, TypeError) as exc:
            return self.send_json({"error": str(exc)}, 400)
        except Exception:
            from error_log import log_unexpected_error
            log_unexpected_error("quality.overview")
            return self.send_json({"error": "Données Qualité indisponibles ; consulter le journal serveur."}, 500)



    def api_quality_pilotage(self, query, user=None):
        from pilotage_quality import view
        try:
            scoped=self._scoped_quality_query(query,user)
            return self.send_json(self._scoped_quality_payload(self._quality_read('quality_pilotage', scoped, view),user))
        except __import__('access_control').ScopeDenied as exc:
            return self.send_json({'error':str(exc)},403)
        except (ValueError, TypeError) as exc:
            return self.send_json({"error":str(exc)},400)
        except Exception:
            from error_log import log_unexpected_error
            log_unexpected_error("quality.pilotage")
            return self.send_json({"error":"Pilotage Qualité indisponible ; consulter le journal serveur."},500)

    def api_quality_actions(self, user=None):
        from pilotage_quality import list_actions
        try:
            payload=list_actions()
            if user is not None:
                from access_control import effective_group_ids
                allowed=effective_group_ids(user)
                if allowed is not None:
                    payload=dict(payload);payload['rows']=[r for r in payload.get('rows') or [] if str(r.get('group_id') or '') in allowed]
            return self.send_json(payload)
        except Exception:
            from error_log import log_unexpected_error
            log_unexpected_error("quality.actions")
            return self.send_json({"error":"Actions Qualité indisponibles."},500)

    def api_quality_action_compare(self, query, user=None):
        from pilotage_quality import compare_action, list_actions
        try:
            if user is not None:
                from access_control import effective_group_ids
                allowed=effective_group_ids(user)
                if allowed is not None:
                    aid=int(str((query or {}).get('id',['0'])[0]) or 0)
                    action=next((r for r in list_actions().get('rows') or [] if int(r.get('id') or 0)==aid),None)
                    if not action or str(action.get('group_id') or '') not in allowed:
                        return self.send_json({'error':'Accès refusé à cette action Qualité.'},403)
            return self.send_json(self._quality_read('quality_action_compare', query, compare_action))
        except (ValueError, TypeError) as exc:return self.send_json({"error":str(exc)},400)
        except Exception:
            from error_log import log_unexpected_error
            log_unexpected_error("quality.action_compare")
            return self.send_json({"error":"Comparaison avant/après indisponible."},500)

    def api_quality_action_save(self, user):
        from pilotage_quality import save_action
        data=self.read_json() or {}
        try:
            from access_control import effective_group_ids, scope_policy
            allowed=effective_group_ids(user); policy=scope_policy(user)
            if allowed is not None:
                gid=str(data.get('group_id') or '').strip()
                if policy.get('filter_locked'):
                    gid=str(policy.get('default_group_id') or '')
                    data=dict(data);data['group_id']=gid
                if not gid or gid not in allowed:
                    return self.send_json({'error':'Action Qualité hors du périmètre métier autorisé.'},403)
            return self.send_json(save_action(data,str(user.get('username') or user.get('name') or 'Utilisateur')))
        except (ValueError,TypeError) as exc:return self.send_json({"error":str(exc)},400)
        except Exception:
            from error_log import log_unexpected_error
            log_unexpected_error("quality.action_save")
            return self.send_json({"error":"Enregistrement de l’action impossible."},500)

    def api_suspicious_calls(self, query, user=None):
        from suspicious_calls import view
        try:
            scoped=self._scoped_quality_query(query,user)
            return self.send_json(self._scoped_quality_payload(self._quality_read('suspicious_calls', scoped, view),user))
        except __import__('access_control').ScopeDenied as exc:
            return self.send_json({'error':str(exc)},403)
        except (ValueError, TypeError) as exc:
            return self.send_json({"error": str(exc)}, 400)
        except Exception:
            from error_log import log_unexpected_error
            log_unexpected_error("quality.suspicious_calls")
            return self.send_json({"error": "Appels suspects indisponibles ; consulter le journal serveur."}, 500)

    def api_quality_priorities(self, user=None):
        try:
            payload=load_quality_priorities()
            if user is not None:
                from access_control import filter_quality_priority_payload
                payload=filter_quality_priority_payload(user,payload)
            self.send_json(payload)
        except Exception as exc:
            self.send_json({"error": f"Source Qualite illisible : {exc}"}, 500)

    def api_quality_import(self, query):
        from service_mode import external_services_enabled
        if external_services_enabled():
            return self.send_json({'error':'V60 : import Qualite separe du Web. Lancez OPEN_NELYIO_IMPORTER.bat sur le serveur Nelyio.'},409)
        # Raw bytes avoid Base64 overhead and preserve the original CSV encoding.
        try:
            size = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return self.send_json({"error": "Taille de fichier invalide"}, 400)
        if size <= 0 or size > MAX_BYTES:
            return self.send_json({"error": "Importer un fichier non vide, de 100 Mo maximum"}, 413)
        filename = Path(str(query.get("filename", [""])[0]).replace("\\", "/")).name
        if not filename.lower().endswith((".zip", ".csv")):
            return self.send_json({"error": "Format attendu : ZIP SIMPLIFY2 ou CSV de configuration"}, 400)
        raw = self.rfile.read(size)
        if len(raw) != size:
            return self.send_json({"error": "Fichier incomplet : import annule"}, 400)
        try:
            result = update_quality_from_export(raw, filename)
        except (ValueError, TypeError, zipfile.BadZipFile) as exc:
            return self.send_json({"error": "Import refuse, donnees precedentes conservees : " + str(exc)}, 400)
        except Exception:
            return self.send_json({"error": "Echec de l'import Qualite ; consulter les journaux du serveur"}, 500)
        return self.send_json(result)
