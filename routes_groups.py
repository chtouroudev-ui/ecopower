"""The handler authorizes classification reads/writes and validates CSRF first."""
import db_compat as sqlite3
from group_workspace import workspace, status, save_group, add_capture_groups, GroupConflict, invalidate_group_workspace_cache
from error_log import log_unexpected_error

class GroupWorkspaceRoutesMixin:
    def api_group_status(self, user=None):
        try:
            payload = status()
            if user is not None:
                from access_control import effective_group_ids
                allowed = effective_group_ids(user)
                if allowed is not None:
                    # Restricted supervisors must not receive the global count of
                    # agents/groups. Their status is projected to the analytical
                    # groups the administrator explicitly authorized.
                    from analysis_groups import catalog, selected_group_scope
                    visible = [g for g in catalog(include_unassigned=False) if str(g.get('id') or '') in allowed]
                    scope = selected_group_scope(sorted(allowed))
                    member_count = len({str(x) for x in scope.get('member_agent_ids') or [] if str(x)})
                    out = dict(payload)
                    out['stats'] = dict(out.get('stats') or {}, agents=member_count)
                    summary = dict(out.get('group_summary') or {})
                    summary.update(saved=len(visible), scoped_agents=member_count,
                                   unclassified_agent_count=0, restricted_scope=True)
                    out['group_summary'] = summary
                    payload = out
            return self.send_json(payload)
        except Exception:
            log_unexpected_error('groups.status')
            return self.send_json({'error': 'Etat des groupes indisponible.'}, 500)

    def api_group_workspace(self, user=None):
        try:
            payload=workspace()
            if user is not None:
                from access_control import effective_group_ids
                allowed=effective_group_ids(user)
                if allowed is not None:
                    out=dict(payload);groups=[g for g in payload.get('groups') or [] if str(g.get('id') or '') in allowed];out['groups']=groups
                    line_ids={int(x) for g in groups for x in g.get('line_ids') or [] if str(x).isdigit()}
                    agent_ids={str(x) for g in groups for x in (g.get('effective_agent_ids') or g.get('automatic_agent_ids') or [])}
                    campaign_keys={str((c or {}).get('key') or '') for g in groups for c in g.get('campaigns') or []}
                    campaign_keys.update(str((c or {}).get('key') or '') for g in groups for c in g.get('derived_campaigns') or [])
                    out['agents']=[a for a in payload.get('agents') or [] if str(a.get('key') or a.get('agent_id') or '') in agent_ids]
                    out['lines']=[q for q in payload.get('lines') or [] if int(q.get('id') or 0) in line_ids]
                    out['campaigns']=[c for c in payload.get('campaigns') or [] if str(c.get('key') or '') in campaign_keys]
                    out['templates']=[];out['pending_templates']=[]
                    payload=out
            return self.send_json(payload)
        except Exception:
            log_unexpected_error('groups.workspace')
            return self.send_json({'error': 'Impossible de charger les groupes. Consulter le journal du serveur.'}, 500)

    def api_group_workspace_save(self, user):
        try:
            data = self.read_json()
            if data is None: return  # read_json already sent the validation error
            from access_control import effective_group_ids
            allowed=effective_group_ids(user)
            if allowed is not None:
                gid=str(data.get('id') or '').strip()
                if not gid or gid not in allowed:
                    return self.send_json({'error':'Modification hors du périmètre métier autorisé.'},403)
            result = save_group(data, user['username'], self.client_ip())
            from quality_scope import invalidate_quality_scope_cache
            from quality_service import invalidate_quality_priorities_cache
            invalidate_quality_scope_cache(); invalidate_quality_priorities_cache(); invalidate_group_workspace_cache()
        except GroupConflict as exc:
            return self.send_json({'error': str(exc)}, 409)
        except (ValueError, TypeError) as exc:
            return self.send_json({'error': str(exc)}, 400)
        except sqlite3.Error:
            log_unexpected_error('groups.save')
            return self.send_json({'error': 'Enregistrement refuse. Les groupes precedents sont conserves.'}, 500)
        return self.send_json(result)

    def api_group_capture_add(self, user):
        try:
            data = self.read_json()
            if data is None:
                return
            from access_control import effective_group_ids
            if effective_group_ids(user) is not None:
                return self.send_json({'error':'La création de nouveaux groupes nécessite un périmètre métier global.'},403)
            result = add_capture_groups(data, user['username'], self.client_ip())
            from quality_scope import invalidate_quality_scope_cache
            from quality_service import invalidate_quality_priorities_cache
            invalidate_quality_scope_cache(); invalidate_quality_priorities_cache(); invalidate_group_workspace_cache()
        except GroupConflict as exc:
            return self.send_json({'error': str(exc)}, 409)
        except (ValueError, TypeError) as exc:
            return self.send_json({'error': str(exc)}, 400)
        except sqlite3.Error:
            log_unexpected_error('groups.capture_add')
            return self.send_json({'error': 'Ajout refuse. Les groupes precedents sont conserves.'}, 500)
        return self.send_json(result)
