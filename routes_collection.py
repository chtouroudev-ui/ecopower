"""Authenticated one-day collector controls. No remote CDP endpoint is accepted."""
from datetime import datetime, timedelta
import collection_service as service
import collection_store as store


def _incident_period(qs, *, default_days=7, max_days=90):
    from nelyio_time import today, day_bounds
    get=lambda key,default='': str(qs.get(key,[default])[0]).strip()
    end_text=get('to') or today()
    try:end_day=datetime.strptime(end_text,'%Y-%m-%d').date()
    except ValueError as exc:raise ValueError('Date de fin incidents invalide.') from exc
    start_text=get('from')
    if start_text:
        try:start_day=datetime.strptime(start_text,'%Y-%m-%d').date()
        except ValueError as exc:raise ValueError('Date de début incidents invalide.') from exc
    else:start_day=end_day-timedelta(days=max(0,int(default_days)-1))
    if start_day>end_day:raise ValueError('La date de début doit précéder la date de fin.')
    if (end_day-start_day).days>=int(max_days):raise ValueError(f'Intervalle incidents limité à {int(max_days)} jours.')
    start_text=start_day.isoformat();end_text=end_day.isoformat()
    start_ts=day_bounds(start_text)[0];end_ts=day_bounds(end_text)[1]
    return start_text,end_text,start_ts,end_ts


class CollectionRoutesMixin:
    def api_collection_status(self):
        return self.send_json(service.status())

    def api_collection_live(self, qs):
        get=lambda key,default='': qs.get(key,[default])[0]
        return self.send_json(store.live_snapshot(
            day=get('day') or None, page=get('page','0'), page_size=get('page_size','100')))

    def api_live_supervision(self, qs, user=None, show_phone=False):
        get=lambda key,default='': qs.get(key,[default])[0]
        try:
            snap=store.live_supervision_snapshot(day=get('day') or None, show_phone=show_phone)
            if user is not None:
                from access_control import filter_live_snapshot
                snap=filter_live_snapshot(user,snap,get('group'))
            return self.send_json(snap)
        except __import__('access_control').ScopeDenied as exc:
            return self.send_json({'error':str(exc)},403)
        except (ValueError,TypeError) as exc:
            return self.send_json({'error':str(exc)},400)

    def api_live_scope_quality(self, qs, user=None):
        try:
            scoped=qs
            if user is not None:
                from access_control import scope_query
                scoped=scope_query(user,qs,param='group')
            import live_scope_quality
            return self.send_json(live_scope_quality.view(scoped))
        except __import__('access_control').ScopeDenied as exc:
            return self.send_json({'error':str(exc)},403)
        except (ValueError,TypeError) as exc:
            return self.send_json({'error':str(exc)},400)

    def api_live_search(self, qs, show_phone=False, user=None):
        try:
            payload=store.live_call_search(qs,show_phone=show_phone)
            if user is not None:
                from access_control import filter_live_search_payload
                payload=filter_live_search_payload(user,payload)
            return self.send_json(payload)
        except __import__('access_control').ScopeDenied as exc:
            return self.send_json({'error':str(exc)},403)
        except (ValueError,TypeError) as exc:
            return self.send_json({'error':str(exc)},400)

    def api_live_campaigns(self, qs, user=None, include_history=True):
        import live_campaigns
        from nelyio_time import local_day
        import time
        get=lambda key,default='': str(qs.get(key,[default])[0]).strip()
        clock=time.time();day=get('day') or local_day(clock)
        try:
            if include_history:
                try:
                    from service_mode import external_services_enabled
                    if external_services_enabled():
                        from analytics_rpc import delegated_view_remote
                        history=delegated_view_remote('live_campaigns_history',qs,timeout=30.0)
                    else:
                        history=live_campaigns.historical_view(qs,clock=clock)
                except (ValueError,TypeError):
                    raise
                except Exception:
                    # Le cockpit Live doit rester utilisable meme si Analytics/PostgreSQL
                    # est momentanement indisponible. L historique devient explicitement
                    # indisponible au lieu de faire tomber toute la vue Live.
                    from error_log import log_unexpected_error
                    log_unexpected_error('live.campaigns.history')
                    history=live_campaigns.empty_history(day,clock=clock,reason='analytics_unavailable')
            else:
                history=live_campaigns.empty_history(day,clock=clock,reason='permission_unavailable')
            snapshot=store.live_supervision_snapshot(day=day,clock=clock)
            include_inactive=get('include_inactive','0').lower() in {'1','true','yes','on'}
            payload=live_campaigns.combine(snapshot,history,clock=clock,include_inactive=include_inactive)
            if user is not None:
                from access_control import filter_live_campaign_payload
                payload=filter_live_campaign_payload(user,payload)
            return self.send_json(payload)
        except __import__('access_control').ScopeDenied as exc:
            return self.send_json({'error':str(exc)},403)
        except (ValueError,TypeError) as exc:
            return self.send_json({'error':str(exc)},400)
        except Exception:
            from error_log import log_unexpected_error
            log_unexpected_error('live.campaigns')
            return self.send_json({'error':'Campagnes Live indisponibles ; consulter le journal serveur.'},500)

    def api_live_campaign_detail(self, campaign_id, qs, include_history=True, include_calls=True, show_phone=False, user=None):
        import live_campaigns
        from nelyio_time import local_day
        import time
        get=lambda key,default='': str(qs.get(key,[default])[0]).strip()
        clock=time.time();day=get('day') or local_day(clock)
        try:
            history_qs=dict(qs or {});history_qs['_campaign_id']=[str(campaign_id)]
            if include_history:
                try:
                    from service_mode import external_services_enabled
                    if external_services_enabled():
                        from analytics_rpc import delegated_view_remote
                        bundle=delegated_view_remote('live_campaign_drilldown_history',history_qs,timeout=30.0)
                    else:
                        bundle=live_campaigns.historical_drilldown_view(history_qs,campaign_id,clock=clock)
                except (ValueError,TypeError):
                    raise
                except Exception:
                    from error_log import log_unexpected_error
                    log_unexpected_error('live.campaign.detail.history')
                    bundle={'history':live_campaigns.empty_history(day,clock=clock,reason='analytics_unavailable'),
                            'agent_metrics':{'source':'Stats.AGENT importé','quality':'unavailable','reason':'analytics_unavailable','agents':{}}}
            else:
                bundle={'history':live_campaigns.empty_history(day,clock=clock,reason='permission_unavailable'),
                        'agent_metrics':{'source':'Stats.AGENT importé','quality':'unavailable','reason':'permission_unavailable','agents':{}}}
            snapshot=store.live_supervision_snapshot(day=day,clock=clock)
            calls={'day':day,'window':'30m','count':0,'rows':[],'source':'Hermes Live','quality':'unavailable','reason':'calls_permission_required','truncated':False}
            if include_calls:
                resolve,_=live_campaigns._resolver()
                target_id,target_label,_identity=resolve(campaign_id,campaign_id)
                values={str(campaign_id),str(target_label)}
                for agent in snapshot.get('agents') or []:
                    raw=str(agent.get('campaign') or (agent.get('current_call') or {}).get('campaign') or '').strip()
                    if not raw:continue
                    rid,_label,_q=resolve(raw,raw)
                    if rid==target_id:values.add(raw)
                calls=store.live_campaign_call_preview(day=day,campaign_values=values,clock=clock,show_phone=show_phone,limit=100,window=get('call_window','30m') or '30m')
            payload=live_campaigns.drilldown(snapshot,bundle,campaign_id,calls_preview=calls,clock=clock)
            if user is not None:
                from access_control import filter_live_campaign_detail
                payload=filter_live_campaign_detail(user,payload)
            return self.send_json(payload)
        except KeyError as exc:
            return self.send_json({'error':str(exc).strip("\'")},404)
        except __import__('access_control').ScopeDenied as exc:
            return self.send_json({'error':str(exc)},403)
        except (ValueError,TypeError) as exc:
            return self.send_json({'error':str(exc)},400)
        except Exception:
            from error_log import log_unexpected_error
            log_unexpected_error('live.campaign.detail')
            return self.send_json({'error':'Drill-down campagne indisponible ; consulter le journal serveur.'},500)

    def api_live_diagnostic(self):
        return self.send_json(store.live_admin_diagnostic())


    def api_live_quality_config(self):
        import live_quality
        return self.send_json(live_quality.config_snapshot())

    def api_live_incidents(self, qs, user=None):
        import live_quality
        get=lambda key,default='': str(qs.get(key,[default])[0]).strip()
        active_only=get('active','0').lower() not in {'0','false','no','off'}
        try:
            limit=int(get('limit','2000') or 2000)
            start_text,end_text,start_ts,end_ts=_incident_period(qs)
        except (ValueError,TypeError) as exc:
            return self.send_json({'error':str(exc)},400)
        incidents=live_quality.incident_snapshot(active_only=active_only,limit=limit,start_ts=start_ts,end_ts=end_ts)
        if user is not None:
            from access_control import filter_live_incidents
            incidents=filter_live_incidents(user,incidents)
        return self.send_json({'incidents':incidents,'retention_days':live_quality.INCIDENT_HISTORY_RETENTION_DAYS,
                               'period':{'from':start_text,'to':end_text},'count':len(incidents)})

    def api_live_incident_stats(self, qs, user=None):
        import live_quality
        try:
            start_text,end_text,start_ts,end_ts=_incident_period(qs)
            incidents=live_quality.incident_snapshot(active_only=False,limit=10000,start_ts=start_ts,end_ts=end_ts)
        except (ValueError,TypeError) as exc:
            return self.send_json({'error':str(exc)},400)
        if user is not None:
            from access_control import filter_live_incidents
            incidents=filter_live_incidents(user,incidents)
        out=live_quality.incident_stats(incidents)
        out['period']={'from':start_text,'to':end_text}
        return self.send_json(out)

    def api_live_incident_detail(self, incident_id, user=None):
        import live_quality
        try:
            detail=live_quality.incident_detail(incident_id)
            if user is not None:
                from access_control import incident_allowed
                incident=(detail.get('incident') or detail) if isinstance(detail,dict) else {}
                if not incident_allowed(user,incident):
                    return self.send_json({'error':'Accès refusé à cet incident pour votre périmètre métier.'},403)
            return self.send_json(detail)
        except KeyError as exc:
            return self.send_json({'error':str(exc).strip("\'")},404)
        except __import__('access_control').ScopeDenied as exc:
            return self.send_json({'error':str(exc)},403)
        except (ValueError,TypeError) as exc:
            return self.send_json({'error':str(exc)},400)

    def api_live_incident_action(self, incident_id, user):
        import live_quality
        from app_db import db_connect
        from access_control import incident_allowed
        try:
            detail=live_quality.incident_detail(incident_id)
            incident=(detail.get('incident') or detail) if isinstance(detail,dict) else {}
            if not incident_allowed(user,incident):
                return self.send_json({'error':'Accès refusé à cet incident pour votre périmètre métier.'},403)
        except KeyError as exc:
            return self.send_json({'error':str(exc).strip("\'")},404)
        data=self.read_json() or {}
        if not isinstance(data,dict):
            return self.send_json({'error':'Objet JSON requis.'},400)
        try:
            result=live_quality.incident_action(
                incident_id,
                action=data.get('action') or 'transition',
                actor=user['username'],
                target_status=data.get('target_status'),
                comment=data.get('comment') or '',
                action_text=data.get('action_text') or '',
            )
            try:
                with db_connect() as con:
                    con.execute('INSERT INTO auth_audit(username,action,details,source_ip) VALUES(?,?,?,?)',
                                (user['username'],'LIVE_INCIDENT_UPDATED',str(incident_id),self.client_ip()))
                    con.commit()
            except Exception:
                pass
            return self.send_json({'ok':True,**result})
        except KeyError as exc:
            return self.send_json({'error':str(exc).strip("\'")},404)
        except __import__('access_control').ScopeDenied as exc:
            return self.send_json({'error':str(exc)},403)
        except (ValueError,TypeError) as exc:
            return self.send_json({'error':str(exc)},400)

    def api_live_incident_create(self, user):
        import live_quality
        from app_db import db_connect
        data=self.read_json() or {}
        if not isinstance(data,dict):
            return self.send_json({'error':'Objet JSON requis.'},400)
        try:
            required=['scope_key','scope_type','rule_name','level_key']
            missing=[f for f in required if not data.get(f)]
            if missing:
                return self.send_json({'error':f'Champs requis: {", ".join(missing)}.'},400)
            result=live_quality.create_incident_manual(
                scope_key=str(data.get('scope_key','')),
                scope_type=str(data.get('scope_type','')).upper(),
                scope_label=str(data.get('scope_label',data.get('scope_key',''))),
                rule_name=str(data.get('rule_name','')),
                level_key=str(data.get('level_key','')),
                detail=str(data.get('detail','')),
                actor=user['username']
            )
            try:
                with db_connect() as con:
                    con.execute('INSERT INTO auth_audit(username,action,details,source_ip) VALUES(?,?,?,?)',
                                (user['username'],'LIVE_INCIDENT_MANUAL_CREATED',
                                 f"{result.get('id')}:{data.get('rule_name')}",self.client_ip()))
                    con.commit()
            except Exception:
                pass
            return self.send_json({'ok':True,'incident_id':result.get('id'),**result})
        except KeyError as exc:
            return self.send_json({'error':str(exc).strip("\'")},404)
        except __import__('access_control').ScopeDenied as exc:
            return self.send_json({'error':str(exc)},403)
        except (ValueError,TypeError) as exc:
            return self.send_json({'error':str(exc)},400)

    def api_live_quality_action(self, action, user):
        import live_quality
        from app_db import db_connect
        data=self.read_json() or {}
        if not isinstance(data,dict):
            return self.send_json({'error':'Objet JSON requis.'},400)
        try:
            if action=='level':
                result=live_quality.save_level(data,user['username'])
                audit_action='LIVE_QUALITY_LEVEL_SAVED'
                detail=result.get('level_key','')
            elif action=='level-delete':
                key=str(data.get('level_key') or '')
                live_quality.delete_level(key,user['username'])
                result={'level_key':key}
                audit_action='LIVE_QUALITY_LEVEL_DELETED'
                detail=key
            elif action=='rule':
                # RC27: targeted Live-quality rules must stay inside the
                # authenticated user's business scope. UI filtering is not a
                # security boundary, so enforce GROUP/AGENT/QUEUE server-side.
                scope_type=str(data.get('scope_type') or 'GLOBAL').strip().upper()
                targets=live_quality._normalize_target_keys(data)
                if user.get('role')!='admin' and targets:
                    import access_control as ac
                    if scope_type=='GROUP' and any(not ac.allowed_group(user,t) for t in targets):
                        raise ac.ScopeDenied('Une cible Groupe est hors de votre périmètre autorisé.')
                    if scope_type=='AGENT':
                        allowed=ac.allowed_agent_ids(user)
                        if allowed is not None and any(str(t) not in allowed for t in targets):
                            raise ac.ScopeDenied('Une cible Agent est hors de votre périmètre autorisé.')
                    if scope_type=='QUEUE':
                        allowed=ac.allowed_line_ids(user)
                        if allowed is not None and any(str(t) not in allowed for t in targets):
                            raise ac.ScopeDenied('Une cible File est hors de votre périmètre autorisé.')
                result=live_quality.save_rule(data,user['username'])
                audit_action='LIVE_QUALITY_RULE_SAVED'
                detail=f"{result.get('id')}:{result.get('name')}"
            elif action=='rule-delete':
                rid=data.get('id')
                live_quality.delete_rule(rid)
                result={'id':int(rid)}
                audit_action='LIVE_QUALITY_RULE_DELETED'
                detail=str(rid)
            else:
                return self.send_json({'error':'Action Qualité Live inconnue.'},404)
            try:
                with db_connect() as con:
                    con.execute('INSERT INTO auth_audit(username,action,details,source_ip) VALUES(?,?,?,?)',
                                (user['username'],audit_action,detail,self.client_ip()))
                    con.commit()
            except Exception:
                pass
            return self.send_json({'ok':True,'result':result,'config':live_quality.config_snapshot()})
        except KeyError as exc:
            return self.send_json({'error':str(exc).strip("\'")},404)
        except __import__('access_control').ScopeDenied as exc:
            return self.send_json({'error':str(exc)},403)
        except (ValueError,TypeError) as exc:
            return self.send_json({'error':str(exc)},400)

    def api_collection_action(self, action, user):
        data = self.read_json()
        if not isinstance(data, dict): return self.send_json({'error': 'Objet JSON requis.'}, 400)
        try:
            if action in {'hermes-scan-status','hermes-scan-start','hermes-scan-stop','hermes-scan-schedule'}:
                if user.get('role') != 'admin':
                    return self.send_json({'error': 'Action réservée aux administrateurs système.'}, 403)
                import hermes_diagnostic as hd
                if action == 'hermes-scan-status':
                    return self.send_json({'ok': True, **hd.status()})
                if action == 'hermes-scan-start':
                    result = hd.start_scan(duration=data.get('duration',60), debug_port=data.get('debug_port') or (service.status().get('config') or {}).get('debug_port') or 9222, open_if_missing=data.get('open_if_missing',False), actor=user['username'])
                    audit_action='HERMES_DIAGNOSTIC_STARTED'
                    detail=f"duration={result.get('duration')};port={result.get('debug_port')};open_if_missing={int(bool(result.get('open_if_missing')))}"
                elif action == 'hermes-scan-stop':
                    result = hd.request_stop()
                    audit_action='HERMES_DIAGNOSTIC_STOP_REQUEST'
                    detail=f"status={result.get('status','')}"
                else:
                    payload=data.get('schedule') if isinstance(data.get('schedule'),dict) else data
                    result=hd.save_schedule(payload,user['username'])
                    audit_action='HERMES_DIAGNOSTIC_SCHEDULE_CHANGED'
                    detail=f"enabled={int(bool(result.get('enabled')))};time={result.get('time')};duration={result.get('duration')};open_if_missing={int(bool(result.get('open_if_missing')))}"
                try:
                    from app_db import db_connect
                    with db_connect() as con:
                        con.execute('INSERT INTO auth_audit(username,action,details,source_ip) VALUES(?,?,?,?)',
                                    (user['username'],audit_action,detail,self.client_ip()))
                        con.commit()
                except Exception:
                    pass
                return self.send_json({'ok': True, 'result': result, **hd.status()})
            if action in {'hermes-credentials-status','hermes-credentials','hermes-credentials-delete','hermes-auto-login'}:
                if user.get('role') != 'admin':
                    return self.send_json({'error': 'Action réservée aux administrateurs système.'}, 403)
                import hermes_credentials as hc
                if action == 'hermes-credentials-status':
                    return self.send_json({'ok': True, **hc.status(check_decrypt=False)})
                if self.client_ip() not in {'127.0.0.1','::1'}:
                    return self.send_json({'error': 'La configuration des identifiants Hermes est autorisée uniquement depuis le serveur Nelyio.'}, 403)
                if action == 'hermes-credentials':
                    result = hc.save_credentials(data.get('username'), data.get('password'), auto_login=data.get('auto_login', True))
                    audit_action = 'HERMES_CREDENTIALS_SAVED'
                elif action == 'hermes-credentials-delete':
                    result = hc.delete_credentials()
                    audit_action = 'HERMES_CREDENTIALS_DELETED'
                else:
                    result = hc.set_auto_login(data.get('enabled'))
                    audit_action = 'HERMES_AUTO_LOGIN_CHANGED'
                try:
                    from app_db import db_connect
                    with db_connect() as con:
                        con.execute('INSERT INTO auth_audit(username,action,details,source_ip) VALUES(?,?,?,?)',
                                    (user['username'],audit_action,'secret=never_logged',self.client_ip()))
                        con.commit()
                except Exception:
                    pass
                return self.send_json({'ok': True, **result})
            if action == 'hermes-supervision-status':
                if user.get('role') != 'admin':
                    return self.send_json({'error': 'Action réservée aux administrateurs système.'}, 403)
                from hermes_supervision_launcher import status as supervision_status
                return self.send_json({'ok': True, **supervision_status()})
            if action == 'open-supervision':
                if user.get('role') != 'admin':
                    return self.send_json({'error': 'Action réservée aux administrateurs système.'}, 403)
                from hermes_supervision_launcher import launch_supervision
                result = launch_supervision(data.get('debug_port') or data.get('port') or (service.status().get('config') or {}).get('debug_port') or 9222)
                try:
                    from app_db import db_connect
                    with db_connect() as con:
                        con.execute('INSERT INTO auth_audit(username,action,details,source_ip) VALUES(?,?,?,?)',
                                    (user['username'],'HERMES_SUPERVISION_OPEN_REQUEST',f"port={result.get('port')};auto_login={int(bool(result.get('auto_login')))}",self.client_ip()))
                        con.commit()
                except Exception:
                    pass
                return self.send_json({'ok': True, **result})
            if action == 'probe':
                settings = service.validate_settings(data)
                return self.send_json(service.probe(settings))
            if action == 'configure':
                if store.unfinished():
                    return self.send_json({'error': 'Arretez la collecte avant de changer ses options.'}, 409)
                settings = service.validate_settings(service.with_persisted_auto_config(data))
                store.save_config(settings, user['username'])
                return self.send_json(service.status())
            if action == 'auto':
                return self.send_json(service.set_auto_capture(data.get('enabled'), user['username']))
            if action == 'start':
                from service_mode import external_services_enabled
                if external_services_enabled():
                    return self.send_json(service.arm(data, user['username']))
                return self.send_json(service.manager().start(data, user['username']))
            if action == 'stop':
                store.request_stop(user['username'])
                return self.send_json(service.status())
            return self.send_json({'error': 'Action inconnue.'}, 404)
        except RuntimeError as exc:
            return self.send_json({'error': str(exc)}, 409)
        except (ValueError, TypeError, KeyError) as exc:
            return self.send_json({'error': str(exc)}, 400)
