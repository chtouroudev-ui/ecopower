/* RC29.4 Phase 3: automatic collector control with manual fallbacks. */
let collectionGeneration=0, collectionTimer=null, collectionActionBusy=false, hermesScanBusy=false, collectionHermesAdminBound=false, hermesScanWatchTimer=null, hermesBrowserWatchTimer=null, collectionLivePage=0, collectionLiveDay='';
const collectionStatusNames={armed:'Programm\u00e9e',running:'Journ\u00e9e en cours',stopped:'Arr\u00eat\u00e9e',completed:'Journ\u00e9e termin\u00e9e',interrupted:'Interrompue',waiting_restart:'En attente de reprise'};
const collectionConnectionNames={waiting:'En attente de la plage horaire',connecting:'Connexion au navigateur',connected_waiting_data:'Onglet d\u00e9tect\u00e9 - en attente de donn\u00e9es',receiving:'Donn\u00e9es re\u00e7ues',waiting_browser:'En attente d\u2019Edge / de l\u2019onglet de supervision',unrecognized:'Format re\u00e7u non reconnu',closed:'Capture ferm\u00e9e'};
const collectionDayLabels={1:'Lun',2:'Mar',3:'Mer',4:'Jeu',5:'Ven',6:'Sam',7:'Dim'};
function collectionFormData(){
  const f=document.querySelector('#collection-form');
  const activeDays=[...f.querySelectorAll('[name=active_days]:checked')].map(x=>Number(x.value));
  return {day:f.elements.day.value,start_time:f.elements.start_time.value,end_time:f.elements.end_time.value,debug_port:Number(f.elements.debug_port.value),page_match:f.elements.page_match.value,target_id:f.elements.target_id.value,response_path:f.elements.response_path.value,include_phone:f.elements.include_phone.checked,timezone:'Europe/Paris',active_days:activeDays};
}
function collectionAgeText(stamp){
  if(stamp===null||stamp===undefined||!Number.isFinite(Number(stamp)))return '';
  const age=Math.max(0,Math.round(Date.now()/1000-Number(stamp)));
  if(age<60)return `il y a ${age} s`;
  const mins=Math.floor(age/60);if(mins<60)return `il y a ${mins} min`;
  return `il y a ${Math.floor(mins/60)} h ${mins%60} min`;
}
function collectionConnectionText(s,d){
  if(!s)return 'Aucune session manuelle n\u00e9cessaire';
  if(s.connection_state!=='waiting')return collectionConnectionNames[s.connection_state]||s.connection_state||'\u2014';
  const w=d?.auto_window||{};
  const start=s.settings?.start_time||w.start_time||d?.config?.start_time||'\u2014';
  const end=s.settings?.end_time||w.end_time||d?.config?.end_time||'\u2014';
  if(w.phase==='active_window'||w.eligible_now)return `Plage active ${start}-${end} \u00b7 d\u00e9marrage automatique en cours`;
  if(w.phase==='inactive_day')return 'Jour non actif pour la d\u00e9tection automatique';
  if(w.phase==='after_window')return `Plage termin\u00e9e ${start}-${end}`;
  return `En attente de la plage horaire ${start}-${end}`;
}
function collectionOperationalState(d){
  const s=d.current||null;
  if(d.auto_capture_blocked_today)return {key:'stopped',title:'Arrêtée manuellement — réactiver',detail:'La détection automatique ne redémarrera pas aujourd’hui sans réactivation explicite.'};
  if(!d.config?.auto_capture)return {key:'off',title:'Détection automatique désactivée',detail:'Les commandes Tester / Démarrer restent disponibles en secours manuel.'};
  if(s&&s.status&&!['stopped','completed','interrupted'].includes(s.status)){
    if(s.connection_state==='waiting_browser')return {key:'waiting',title:'En attente d’Edge',detail:'Nelyio recherche automatiquement l’unique onglet de supervision correspondant.'};
    if(s.connection_state==='connecting')return {key:'detected',title:'Onglet détecté',detail:'Connexion au navigateur de collecte en cours.'};
    if(s.connection_state==='connected_waiting_data')return {key:'detected',title:'Onglet détecté',detail:'Connecté à la supervision, en attente des premières données Hermes.'};
    if(s.connection_state==='receiving'||s.fresh)return {key:'running',title:'Capture en cours',detail:s.last_response?`Dernière donnée ${collectionAgeText(s.last_response)}.`:'Réception Live active.'};
    if(s.connection_state==='waiting'){
      const w=d.auto_window||{};
      if(w.phase==='active_window'||w.eligible_now)return {key:'waiting',title:'Plage active — démarrage automatique',detail:`La session est armée dans la plage ${s.settings?.start_time||d.config?.start_time||'—'}–${s.settings?.end_time||d.config?.end_time||'—'}. Si elle reste ici plus de 12 s, le worker Live tente une reprise automatique.`};
      if(w.phase==='inactive_day')return {key:'scheduled',title:'Détection automatique active',detail:'Aujourd’hui n’est pas coché dans les jours actifs.'};
      return {key:'scheduled',title:'Détection automatique active',detail:`Session du jour armée · plage ${s.settings?.start_time||d.config?.start_time||'—'}–${s.settings?.end_time||d.config?.end_time||'—'}.`};
    }
  }
  return {key:'ready',title:'Détection automatique active',detail:`Nelyio démarrera seul pendant la plage ${d.config?.start_time||'—'}–${d.config?.end_time||'—'} les jours sélectionnés.`};
}
function collectionUpdateStatus(d){
  const s=d.current, terminal=!s||['stopped','completed','interrupted'].includes(s.status), host=document.querySelector('#collection-status');
  const liveReady=!d.live_service||d.live_service.healthy,op=collectionOperationalState(d);
  if(!host)return;
  host.innerHTML=`<div class="collection-auto-banner ${esc(op.key)}"><span class="collection-auto-indicator" aria-hidden="true"></span><div><strong>${esc(op.title)}</strong><span>${esc(op.detail)}</span></div>${d.auto_capture_blocked_today&&canWrite('collection')?'<button type="button" class="button ghost" id="collection-reactivate">Réactiver aujourd’hui</button>':''}</div>
    <div class="collection-status-line"><span class="collection-dot ${s?.fresh?'fresh':''}"></span><strong>${esc(s?collectionStatusNames[s.status]||s.status:'Prête à configurer')}</strong><span>${esc(collectionConnectionText(s,d))}</span></div>
    <div class="collection-facts"><div><span>Journ&#233;e</span><b>${esc(s?.day||d.server_day||'—')}</b></div><div><span>Heure serveur</span><b>${esc(d.auto_window?.server_clock||d.server_clock||'—')}</b></div><div><span>Plage auto</span><b>${esc((d.auto_window?.start_time||d.config?.start_time||'—')+' - '+(d.auto_window?.end_time||d.config?.end_time||'—'))}</b></div><div><span>Premi&#232;re r&#233;ception</span><b>${esc(s?.first_response_text||'Aucune')}</b></div><div><span>Derni&#232;re r&#233;ponse</span><b>${esc(s?.last_response_text||'Aucune')}</b></div><div><span>&#201;v&#233;nements re&#231;us</span><b>${Number(s?.event_count||0)}</b></div></div>
    ${s?.error?`<p class="collection-warning" role="status">${esc(s.error)}</p>`:''}
    ${!liveReady?`<p class="collection-warning" role="status">Service Live indisponible : redémarrez les services Nelyio avant de démarrer une capture.</p>`:''}
    ${d.pending?`<p class="collection-warning">${Number(d.pending)} &#233;v&#233;nement(s) en cours de finalisation locale dans la base Live.</p>`:''}`;
  const toggle=document.querySelector('#collection-auto-toggle');if(toggle){toggle.checked=!!d.config?.auto_capture;toggle.disabled=collectionActionBusy||!canWrite('collection');}
  document.querySelectorAll('#collection-form input,#collection-form select').forEach(i=>i.disabled=!terminal||!canWrite('collection'));
  const start=document.querySelector('#collection-start'),stop=document.querySelector('#collection-stop'),probe=document.querySelector('#collection-probe'),save=document.querySelector('#collection-save');
  if(start)start.disabled=!terminal||collectionActionBusy||!canWrite('collection')||!d.dependency_ready||!liveReady;
  if(stop)stop.disabled=terminal||collectionActionBusy||!canWrite('collection');
  if(probe)probe.disabled=!terminal||collectionActionBusy||!canWrite('collection');
  if(save)save.disabled=!terminal||collectionActionBusy||!canWrite('collection');
  const reactivate=document.querySelector('#collection-reactivate');if(reactivate)reactivate.onclick=()=>collectionSetAuto(true,true);
  const history=document.querySelector('#collection-history');if(history)history.innerHTML=(d.history||[]).map(s=>`<tr><td>${esc(s.day)}</td><td>${esc(s.settings.start_time)} - ${esc(s.settings.end_time)}</td><td>${esc(collectionStatusNames[s.status]||s.status)}</td><td>${esc(s.last_response_text||'Aucune r\u00e9ception')}</td><td>${Number(s.event_count||0)}</td><td><button type="button" class="button ghost" data-live-day="${esc(s.day)}">Voir la journ&#233;e</button></td></tr>`).join('')||'<tr><td colspan="6" class="empty">Aucune journ&#233;e captur&#233;e.</td></tr>';
  document.querySelectorAll('[data-live-day]').forEach(b=>{b.hidden=false;b.onclick=()=>{collectionLiveDay=b.dataset.liveDay;collectionLivePage=0;collectionLoadLive(collectionGeneration,collectionLiveDay);document.querySelector('#collection-live-data')?.scrollIntoView({behavior:'smooth',block:'start'});};});
}
async function collectionSetAuto(enabled,explicit=false){
  if(collectionActionBusy||!canWrite('collection'))return;collectionActionBusy=true;
  const h=document.querySelector('#collection-message');if(h)h.textContent=enabled?(explicit?'Réactivation de la détection automatique...':'Activation de la détection automatique...'):'Désactivation de la détection automatique...';
  try{
    const result=await api('/api/collection/auto',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({enabled:!!enabled})});
    if(location.hash==='#collection'){collectionUpdateStatus(result);if(h)h.textContent=enabled?'Détection automatique activée.':'Détection automatique désactivée.';}
  }catch(e){const toggle=document.querySelector('#collection-auto-toggle');if(toggle)toggle.checked=!enabled;if(h)h.textContent=e.message;}
  finally{collectionActionBusy=false;}
}

function collectionLiveRender(d){
  const host=document.querySelector('#collection-live-data');if(!host)return;
  const types=d.events_by_type||{},rows=d.rows||[],cat=d.catalog||{};
  host.innerHTML=`<section class="card panel"><div class="panel-head"><div><h2>Données Live · ${esc(d.day||'')}</h2><p>Lecture directe de Nelyio_Live.db. Aucun passage par Analytics ou PostgreSQL.</p></div><span>${Number(d.count||0)} événement(s)</span></div>
    <div class="sup-metrics"><div><span>Appels observés</span><strong>${Number(d.calls||0)}</strong></div><div><span>Agents détectés</span><strong>${Number(cat.agent||0)}</strong></div><div><span>Files détectées</span><strong>${Number(cat.queue||0)}</strong></div><div><span>Campagnes</span><strong>${Number(cat.campaign||0)}</strong></div></div>
    <details open><summary>Derniers événements Live</summary><div class="table-wrap"><table><thead><tr><th>Heure</th><th>Type</th><th>Agent</th><th>File / campagne</th><th>Numéro</th><th>État</th><th>Source</th></tr></thead><tbody>${rows.map(r=>`<tr><td>${esc(r.stamp_text||'')}</td><td>${esc(r.event_label||r.event_type||'')}</td><td>${esc(r.agent||'—')}</td><td>${esc(r.line_name||r.line_id||r.campaign||'—')}</td><td>${esc(r.phone||'—')}</td><td>${esc(r.state||'—')}</td><td>${esc(r.source||'')}</td></tr>`).join('')||'<tr><td colspan="7" class="empty">Aucun événement Live pour cette journée.</td></tr>'}</tbody></table></div>
    <div class="sup-pager"><button class="button ghost" id="collection-live-prev" ${d.page<=0?'disabled':''}>Précédent</button><span>Page ${Number(d.page||0)+1}${d.count?` / ${Math.max(1,Math.ceil(d.count/d.page_size))}`:''}</span><button class="button ghost" id="collection-live-next" ${(Number(d.page||0)+1)*Number(d.page_size||100)>=Number(d.count||0)?'disabled':''}>Suivant</button></div></details>
    <details><summary>Catalogue détecté</summary><div class="collection-grid"><div><h3>Agents</h3><p>${(d.agents||[]).slice(0,60).map(x=>esc(x.name||x.id)).join(' · ')||'Aucun'}</p></div><div><h3>Files</h3><p>${(d.queues||[]).slice(0,60).map(x=>esc(x.name||x.id)).join(' · ')||'Aucune'}</p></div></div></details></section>`;
  const prev=document.querySelector('#collection-live-prev'),next=document.querySelector('#collection-live-next');
  if(prev)prev.onclick=()=>{collectionLivePage=Math.max(0,collectionLivePage-1);collectionLoadLive(collectionGeneration,collectionLiveDay||d.day);};
  if(next)next.onclick=()=>{collectionLivePage++;collectionLoadLive(collectionGeneration,collectionLiveDay||d.day);};
}
async function collectionLoadLive(ticket,day){
  if(ticket!==collectionGeneration||location.hash!=='#collection')return;
  const chosen=day||collectionLiveDay||document.querySelector('#collection-form')?.elements?.day?.value||'';
  try{const d=await api('/api/collection/live?day='+encodeURIComponent(chosen)+'&page='+collectionLivePage+'&page_size=100');if(ticket===collectionGeneration&&location.hash==='#collection')collectionLiveRender(d);}
  catch(e){const h=document.querySelector('#collection-live-data');if(h)h.innerHTML=`<p class="collection-warning">${esc(e.message)}</p>`;}
}
function collectionDiagnosticRender(d){
  const host=document.querySelector('#collection-live-diagnostic');if(!host)return;
  const yn=v=>v===true?'OK':v===false?'KO':'Non mesuré';
  const age=v=>v===null||v===undefined?'—':`${Number(v).toFixed(1)} s`;
  host.innerHTML=`<div class="panel-head"><div><h3>Diagnostic administrateur Live</h3><p>État technique mesuré, sans déduire de clients ou de KPI non observés.</p></div><span>${esc(d.server_clock||'')}</span></div>
    <div class="sup-metrics">
      <div><span>Collecteur</span><strong>${esc(d.collector?.label||'—')}</strong></div>
      <div><span>Hermes</span><strong>${yn(d.hermes?.ok)}</strong><small>${esc(d.hermes?.connection_state||'—')} · ${age(d.hermes?.age_seconds)}</small></div>
      <div><span>Worker Live</span><strong>${yn(d.worker?.ok)}</strong><small>${esc(d.worker?.state||'—')} · ${age(d.worker?.age_seconds)}</small></div>
      <div><span>${esc(d.database?.engine||'Base historique')}</span><strong>${yn(d.database?.ok)}</strong></div>
    </div>
    <div class="collection-facts"><div><span>Dernier heartbeat</span><b>${esc(d.events?.last_heartbeat_text||'Aucun')}</b></div><div><span>Dernier événement</span><b>${esc(d.events?.last_event_text||'Aucun')}</b></div><div><span>Événements en attente</span><b>${Number(d.events?.pending||0)}</b></div><div><span>Historique Live à synchroniser</span><b>${d.history_persistence?.pending_finalized===null||d.history_persistence?.pending_finalized===undefined?'—':Number(d.history_persistence.pending_finalized)}</b></div><div><span>Clients Live connectés</span><b>Non mesuré</b></div></div>
    ${d.database?.error?`<p class="collection-warning">Base historique : ${esc(d.database.error)}</p>`:''}
    <p class="sub">${esc((d.limitations||[]).join(' '))}</p>`;
}
async function collectionLoadDiagnostic(ticket){
  if(ticket!==collectionGeneration||location.hash!=='#collection'||!canWrite('collection'))return;
  try{const d=await api('/api/live/diagnostic');if(ticket===collectionGeneration&&location.hash==='#collection')collectionDiagnosticRender(d);}
  catch(e){const h=document.querySelector('#collection-live-diagnostic');if(h)h.innerHTML=`<p class="collection-warning">Diagnostic Live : ${esc(e.message)}</p>`;}
}
async function collectionPoll(ticket){
  if(ticket!==collectionGeneration||location.hash!=='#collection')return;
  try{const d=await api('/api/collection/status');if(ticket===collectionGeneration&&location.hash==='#collection'){collectionUpdateStatus(d);await Promise.all([collectionLoadLive(ticket,collectionLiveDay||d.server_day),collectionLoadDiagnostic(ticket),collectionHermesScanLoad(ticket)]);}}
  catch(e){const h=document.querySelector('#collection-message');if(h)h.textContent=e.message;}
  finally{if(ticket===collectionGeneration&&location.hash==='#collection')collectionTimer=setTimeout(()=>collectionPoll(ticket),5000);}
}
function collectionHermesCredentialRender(d){
  const host=document.querySelector('#hermes-credential-status'),toggle=document.querySelector('#hermes-auto-login');if(!host)return;
  const configured=!!d?.configured,auto=!!d?.auto_login;
  host.className='collection-secret-status '+(configured?'configured':'missing');
  let text=configured?`Identifiants chiffrés configurés pour le compte Windows ${d.windows_account||'Nelyio'}.`:'Aucun identifiant Hermes enregistré.';
  if(configured&&d.cooldown_active)text+=' Auto-login temporairement suspendu après un échec; réessayez après le cooldown ou remplacez les identifiants.';
  host.textContent=text;
  if(toggle){toggle.checked=configured?auto:true;toggle.disabled=collectionActionBusy;toggle.dataset.configured=configured?'1':'0';toggle.parentElement.querySelector('b').textContent=configured?(auto?'Activé':'Désactivé'):'Activé après enregistrement';}
  const del=document.querySelector('#hermes-credentials-delete');if(del)del.disabled=!configured||collectionActionBusy;
}
async function collectionHermesCredentialAction(action,payload={}){
  if(collectionActionBusy||currentUser?.role!=='admin')return;collectionActionBusy=true;
  const msg=document.querySelector('#hermes-credential-message');if(msg)msg.textContent=action==='hermes-credentials'?'Chiffrement et enregistrement des identifiants...':action==='hermes-credentials-delete'?'Suppression des identifiants...':'Mise à jour...';
  try{
    const result=await api('/api/collection/'+action,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    collectionHermesCredentialRender(result);
    if(msg)msg.textContent=action==='hermes-credentials'?'Identifiants Hermes enregistrés avec Windows DPAPI.':action==='hermes-credentials-delete'?'Identifiants Hermes supprimés.':'Réglage auto-login mis à jour.';
    const password=document.querySelector('#hermes-password');if(password)password.value='';
  }catch(e){if(msg)msg.textContent=e.message;}
  finally{collectionActionBusy=false;}
}
async function collectionHermesCredentialLoad(){
  if(currentUser?.role!=='admin')return;
  try{const d=await api('/api/collection/hermes-credentials-status',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});collectionHermesCredentialRender(d);}
  catch(e){const h=document.querySelector('#hermes-credential-status');if(h)h.textContent=e.message;}
}
function collectionHermesScanDays(days){const set=new Set((days||[]).map(Number));return Object.entries(collectionDayLabels).map(([v,l])=>`<label><input type="checkbox" name="hermes_scan_days" value="${v}" ${set.has(Number(v))?'checked':''}><span>${l}</span></label>`).join('');}
function collectionHermesScanRender(d){
  const host=document.querySelector('#hermes-scan-card');if(!host)return;const state=d?.state||{},cfg=d?.schedule||{},last=d?.last_report||null;
  const active=['preparing','checking_browser','opening_browser','waiting_browser','running'].includes(String(state.status||''));
  const stageLabels={preparing:'PRÉPARATION',checking_browser:'VÉRIFICATION EDGE',opening_browser:'OUVERTURE EDGE',waiting_browser:'ATTENTE HERMES',running:'ANALYSE EN COURS',completed:'TERMINÉ',error:'ERREUR'};
  const coverage=last?.coverage||{},missing=coverage.missing_upquh||[],sourceCount=Number(last?.source_count||0),candidateCount=Number(last?.candidate_count||0);
  const stateMessage=state.message||(active?`Diagnostic Hermes : ${stageLabels[state.status]||state.status}.`:(state.error?`Dernière analyse en erreur : ${state.error}`:'Scanner prêt.'));
  host.innerHTML=`<div class="panel-head"><div><h3>Diagnostic Hermes</h3><p>Analyse passive, sur demande, des échanges réseau de la page Supervision. Aucun nouveau flux n’est activé automatiquement.</p></div><span class="live-health-badge ${active?'warn':state.status==='error'?'bad':'ok'}">${esc(stageLabels[state.status]||'ADMIN')}</span></div>
    <div class="hermes-scan-actions"><label>Durée<select id="hermes-scan-duration">${(d.allowed_durations||[30,60,120]).map(x=>`<option value="${Number(x)}" ${Number(state.duration||60)===Number(x)?'selected':''}>${Number(x)} s</option>`).join('')}</select></label><label class="collection-checkbox"><input id="hermes-scan-open" type="checkbox" ${(state.open_if_missing??true)?'checked':''}> Ouvrir / connecter Hermes si absent</label><button type="button" class="button" id="hermes-scan-start" ${active||hermesScanBusy?'disabled':''}>Analyser la supervision Hermes</button><button type="button" class="button ghost" id="hermes-scan-stop" ${!active||hermesScanBusy?'disabled':''}>Arrêter l’analyse</button></div>
    <p id="hermes-scan-message" role="status">${esc(stateMessage)}</p>
    ${last?`<div class="hermes-scan-summary"><div><span>Sources réseau</span><strong>${sourceCount}</strong></div><div><span>Sources candidates</span><strong>${candidateCount}</strong></div><div><span>Files catalogue</span><strong>${Number(coverage.catalog_lines||0)}</strong></div><div><span>UpQuH couvertes</span><strong>${Number(coverage.upquh_lines||0)}/${Number(coverage.catalog_lines||0)}</strong></div><div><span>UpQuR couvertes</span><strong>${Number(coverage.upqur_lines||0)}/${Number(coverage.catalog_lines||0)}</strong></div></div><details class="hermes-scan-missing"><summary>Files sans UpQuH (${missing.length})</summary><div class="hermes-scan-missing-list">${missing.slice(0,100).map(x=>`<span><b>${esc(x.line_id)}</b> ${esc(x.name)}</span>`).join('')||'<span>Aucune file manquante dans le dernier rapport.</span>'}</div>${missing.length>100?`<small>${missing.length-100} autre(s) file(s) restent dans le rapport normalisé.</small>`:''}</details>`:'<p class="sub">Aucun rapport de diagnostic Hermes enregistré pour le moment.</p>'}
    <details class="hermes-scan-schedule"><summary>Planification optionnelle</summary><p>OFF par défaut. Un scan planifié reste passif et n’intègre jamais automatiquement une nouvelle source.</p><div class="collection-secret-grid"><label>Heure<input id="hermes-scan-time" type="time" value="${esc(cfg.time||'10:30')}"></label><label>Durée<select id="hermes-scan-schedule-duration">${(d.allowed_durations||[30,60,120]).map(x=>`<option value="${Number(x)}" ${Number(cfg.duration||60)===Number(x)?'selected':''}>${Number(x)} s</option>`).join('')}</select></label></div><fieldset class="collection-days"><legend>Jours</legend>${collectionHermesScanDays(cfg.active_days||[1,2,3,4,5,6,7])}</fieldset><label class="collection-switch collection-secret-switch"><input id="hermes-scan-enabled" type="checkbox" ${cfg.enabled?'checked':''}><span aria-hidden="true"></span><b>${cfg.enabled?'Activée':'Désactivée'}</b></label><label class="collection-checkbox"><input id="hermes-scan-schedule-open" type="checkbox" ${cfg.open_if_missing?'checked':''}> Ouvrir / auto-login Hermes si absent avant le scan</label><div class="collection-actions"><button type="button" class="button ghost" id="hermes-scan-save">Enregistrer la planification</button></div></details>`;
  document.querySelector('#hermes-scan-enabled')?.addEventListener('change',e=>{const b=e.target.parentElement.querySelector('b');if(b)b.textContent=e.target.checked?'Activée':'Désactivée';});
}
async function collectionHermesScanAction(action,payload){
  if(hermesScanBusy||currentUser?.role!=='admin')return;
  hermesScanBusy=true;const msg=document.querySelector('#hermes-scan-message');
  if(msg)msg.textContent=action==='hermes-scan-start'?'Préparation du diagnostic Hermes…':action==='hermes-scan-stop'?'Demande d’arrêt…':'Enregistrement de la planification…';
  try{
    const d=await api('/api/collection/'+action,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload||{})});
    collectionHermesScanRender(d);
    if(action==='hermes-scan-start')collectionHermesScanWatch();
  }catch(e){const target=document.querySelector('#hermes-scan-message');if(target)target.textContent='Diagnostic Hermes : '+e.message;}
  finally{hermesScanBusy=false;}
}
async function collectionHermesScanLoad(ticket){
  if(currentUser?.role!=='admin'||!document.querySelector('#hermes-scan-card'))return;
  try{const d=await api('/api/collection/hermes-scan-status',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});if((ticket===undefined||ticket===collectionGeneration)&&location.hash==='#collection')collectionHermesScanRender(d);return d;}
  catch(e){const h=document.querySelector('#hermes-scan-card');if(h)h.innerHTML=`<p class="collection-warning">Diagnostic Hermes : ${esc(e.message)}</p>`;return null;}
}
async function collectionHermesScanWatch(){
  clearTimeout(hermesScanWatchTimer);
  if(location.hash!=='#collection'||currentUser?.role!=='admin')return;
  const d=await collectionHermesScanLoad();if(!d)return;
  const active=['preparing','checking_browser','opening_browser','waiting_browser','running'].includes(String(d.state?.status||''));
  if(active)hermesScanWatchTimer=setTimeout(collectionHermesScanWatch,1000);
}
async function collectionHermesBrowserWatch(){
  clearTimeout(hermesBrowserWatchTimer);
  if(location.hash!=='#collection'||currentUser?.role!=='admin')return;
  const h=document.querySelector('#collection-message');
  try{
    const d=await api('/api/collection/hermes-supervision-status',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
    if(h&&d.message)h.textContent='Hermes : '+d.message;
    if(['opening_browser','browser_ready','auto_login','starting'].includes(String(d.stage||'')))hermesBrowserWatchTimer=setTimeout(collectionHermesBrowserWatch,1000);
  }catch(e){if(h)h.textContent='Hermes : '+e.message;}
}
async function collectionOpenSupervisionAction(){
  if(collectionActionBusy||currentUser?.role!=='admin')return;collectionActionBusy=true;
  const h=document.querySelector('#collection-message');if(h)h.textContent='Ouverture et vérification de la supervision Hermes…';
  try{
    const port=Number(document.querySelector('[name=debug_port]')?.value||9222);
    const result=await api('/api/collection/open-supervision',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({debug_port:port})});
    if(h)h.textContent='Hermes : '+(result.message||'Ouverture démarrée.');
    collectionHermesBrowserWatch();
  }catch(e){if(h)h.textContent='Hermes : '+e.message;}
  finally{collectionActionBusy=false;}
}
function collectionBindHermesAdminEvents(){
  if(collectionHermesAdminBound)return;collectionHermesAdminBound=true;
  document.addEventListener('click',e=>{
    if(location.hash!=='#collection'||currentUser?.role!=='admin')return;
    const b=e.target?.closest?.('button');if(!b)return;
    if(b.id==='collection-open-supervision'){e.preventDefault();collectionOpenSupervisionAction();return;}
    if(b.id==='hermes-scan-start'){e.preventDefault();collectionHermesScanAction('hermes-scan-start',{duration:Number(document.querySelector('#hermes-scan-duration')?.value||60),open_if_missing:!!document.querySelector('#hermes-scan-open')?.checked,debug_port:Number(document.querySelector('[name=debug_port]')?.value||9222)});return;}
    if(b.id==='hermes-scan-stop'){e.preventDefault();collectionHermesScanAction('hermes-scan-stop',{});return;}
    if(b.id==='hermes-scan-save'){e.preventDefault();const days=[...document.querySelectorAll('[name=hermes_scan_days]:checked')].map(x=>Number(x.value));collectionHermesScanAction('hermes-scan-schedule',{enabled:!!document.querySelector('#hermes-scan-enabled')?.checked,time:document.querySelector('#hermes-scan-time')?.value||'10:30',active_days:days,duration:Number(document.querySelector('#hermes-scan-schedule-duration')?.value||60),open_if_missing:!!document.querySelector('#hermes-scan-schedule-open')?.checked,debug_port:Number(document.querySelector('[name=debug_port]')?.value||9222)});}
  });
}
async function collectionView(){
  const ticket=++collectionGeneration;clearTimeout(collectionTimer);activate('collection');setHead('Collecteur Live','Détection automatique du navigateur Hermes · données du jour uniquement.');
  const d=await api('/api/collection/status');if(ticket!==collectionGeneration||location.hash!=='#collection')return;
  const c={...d.config};if(c.day<d.server_day)c.day=d.server_day;const activeDays=new Set((c.active_days||[]).map(Number));
  app.innerHTML=`<section class="collection-workspace"><div class="card panel collection-main">
    <div class="panel-head"><div><h2>Collecteur Live</h2><p>Nelyio détecte automatiquement le navigateur de collecte et arme la session du jour dans la plage configurée. Tester / Démarrer / Arrêter restent disponibles comme secours.</p></div></div>
    <div class="collection-auto-control"><div><strong>Détection automatique</strong><span>Démarre la capture du jour sans clic dès qu’Edge de collecte et l’onglet de supervision sont disponibles.</span></div><label class="collection-switch"><input id="collection-auto-toggle" type="checkbox" ${c.auto_capture?'checked':''}><span aria-hidden="true"></span><b>${c.auto_capture?'Activée':'Désactivée'}</b></label></div>
    <div class="collection-scope">Base : Nelyio_Live.db &middot; Europe/Paris &middot; une session par jour &middot; purge automatique au changement de date.</div><div id="collection-status" aria-live="polite"></div>
    <form id="collection-form"><div class="collection-date-row"><label>Jour manuel<input type="date" name="day" value="${esc(c.day)}" min="${esc(d.server_day)}" required></label><label>Début<input type="time" name="start_time" value="${esc(c.start_time)}" required></label><label>Fin<input type="time" name="end_time" value="${esc(c.end_time)}" required></label></div>
    <fieldset class="collection-days"><legend>Jours actifs pour la détection automatique</legend>${Object.entries(collectionDayLabels).map(([value,label])=>`<label><input type="checkbox" name="active_days" value="${value}" ${activeDays.has(Number(value))?'checked':''}><span>${label}</span></label>`).join('')}</fieldset>
    <details class="collection-options"><summary>Options avancées · connexion CDP et confidentialité</summary><p>Le navigateur doit être sur le <strong>même PC que le serveur Nelyio</strong>. Le port de diagnostic reste exclusivement local (127.0.0.1).</p>
    <div class="collection-option-grid"><label>Port local<input type="number" name="debug_port" min="1024" max="65535" value="${Number(c.debug_port)}"></label><label>Filtre de l'onglet<input name="page_match" value="${esc(c.page_match)}" maxlength="160"></label><label>Réponse suivie<input name="response_path" value="${esc(c.response_path)}" maxlength="100"></label><label>Onglet à suivre<select name="target_id" id="collection-target"><option value="">Automatique si un seul onglet</option>${c.target_id?`<option value="${esc(c.target_id)}">Ancien onglet enregistré — sélection manuelle uniquement</option>`:''}</select></label></div>
    <label class="collection-checkbox"><input type="checkbox" name="include_phone" ${c.include_phone?'checked':''}> Collecter les numéros visibles pour la recherche d'appels</label><small>Facultatif. Aucun audio, cookie, mot de passe, JavaScript injecté ou corps HTTP brut n'est enregistré par le flux Live. Les identifiants Hermes éventuels sont stockés séparément, chiffrés par Windows DPAPI et jamais inclus dans les données Live.</small></details>
    <div class="collection-actions"><button id="collection-save" class="button ghost" type="button">Enregistrer les réglages</button><button id="collection-probe" class="button ghost" type="button">Tester le navigateur</button>${currentUser?.role==='admin'?'<button id="collection-open-supervision" class="button ghost" type="button">Ouvrir la supervision Hermes</button>':''}<button id="collection-start" class="button" type="submit">Démarrer manuellement</button><button id="collection-stop" class="button ghost" type="button">Arrêter</button></div></form>
    ${currentUser?.role==='admin'?`<section class="collection-secret-card"><div><h3>Connexion Hermes automatique</h3><p>Configuration locale au serveur uniquement. Le mot de passe est chiffré par Windows DPAPI avec le compte qui exécute Nelyio; il n’est jamais renvoyé au navigateur après enregistrement.</p></div><div id="hermes-credential-status" class="collection-secret-status">Vérification du coffre sécurisé…</div><div class="collection-secret-grid"><label>Identifiant Hermes<input id="hermes-username" autocomplete="off" maxlength="256" placeholder="Utilisateur Hermes"></label><label>Mot de passe Hermes<input id="hermes-password" type="password" autocomplete="new-password" maxlength="1024" placeholder="Nouveau mot de passe"></label></div><label class="collection-switch collection-secret-switch"><input id="hermes-auto-login" type="checkbox" disabled><span aria-hidden="true"></span><b>Désactivé</b></label><div class="collection-actions"><button id="hermes-credentials-save" class="button" type="button">Enregistrer / remplacer</button><button id="hermes-credentials-delete" class="button ghost" type="button" disabled>Supprimer les identifiants</button></div><p id="hermes-credential-message" role="status"></p><small>En cas d’échec d’authentification, Nelyio suspend les nouvelles tentatives pendant 15 minutes pour limiter le risque de verrouillage du compte.</small></section>`:''}
    ${currentUser?.role==='admin'?'<section id="hermes-scan-card" class="collection-secret-card hermes-scan-card"><p class="empty">Chargement du diagnostic Hermes…</p></section>':''}
    <p id="collection-message" role="status"></p>${!d.dependency_ready?'<p class="collection-warning">Composant manquant : exécuter INSTALL_CAPTURE_DEPENDENCIES.bat puis redémarrer Nelyio.</p>':''}</div>
    <div class="collection-grid"><section class="card panel"><h3>Utilisation quotidienne</h3><p>Avec l’auto-login Hermes configuré, Nelyio peut ouvrir le profil Edge dédié, se connecter puis atteindre la supervision sans intervention quotidienne. La session existante est toujours réutilisée en priorité.</p><p>Si Edge ou l'onglet est fermé, la session reste en attente et reprendra automatiquement dès qu'un unique onglet correspondant sera de nouveau disponible.</p></section>
    <section class="card panel"><h3>Secours manuel</h3><p><strong>Tester</strong> liste les onglets disponibles sans épingler automatiquement leur identifiant. ${currentUser?.role==='admin'?'<strong>Ouvrir la supervision Hermes</strong> réutilise le profil Edge dédié et utilise l’auto-login DPAPI seulement s’il a été explicitement configuré. Aucune exécution JavaScript dans la page n’est utilisée. ':''}<strong>Démarrer manuellement</strong> et <strong>Arrêter</strong> restent disponibles pour l'administration.</p><p>Après un arrêt manuel, l'automatisme reste suspendu jusqu'au lendemain ou jusqu'à « Réactiver aujourd'hui ».</p></section></div>
    ${canWrite('collection')?'<section id="collection-live-diagnostic" class="card panel"><p class="empty">Chargement du diagnostic Live…</p></section>':''}
    <section id="collection-live-data"><p class="empty">Chargement des données Live…</p></section>
    <details class="card panel collection-history"><summary>Sessions Live du jour</summary><div class="table-wrap"><table><thead><tr><th>Jour</th><th>Plage demandée</th><th>État</th><th>Dernière réception</th><th>Événements</th><th></th></tr></thead><tbody id="collection-history"></tbody></table></div></details></section>`;
  const act=async(action)=>{
    if(collectionActionBusy)return;collectionActionBusy=true;const h=document.querySelector('#collection-message');h.textContent=action==='probe'?'Vérification du navigateur...':action==='configure'?'Enregistrement des réglages...':action==='open-supervision'?'Ouverture de la supervision Hermes...':'Traitement...';
    try{
      const result=await api('/api/collection/'+action,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(action==='stop'?{}:collectionFormData())});
      if(location.hash!=='#collection')return;
      if(action==='probe'){
        const select=document.querySelector('#collection-target'),previous=select.value;select.innerHTML='<option value="">Automatique si un seul onglet</option>'+result.targets.map(t=>`<option value="${esc(t.id)}">${esc(t.url)}</option>`).join('');
        if(previous&&[...select.options].some(o=>o.value===previous))select.value=previous;else select.value='';h.textContent=result.message;
      }else if(action==='configure'){h.textContent='Réglages enregistrés. La détection automatique utilisera cette plage et ces jours.';collectionUpdateStatus(result);}
      else if(action==='open-supervision'){h.textContent=result.message||'Ouverture de la supervision Hermes demandée.';setTimeout(()=>collectionHermesCredentialLoad(),1200);}
      else{h.textContent=action==='stop'?'Live arrêté. Le redémarrage automatique est suspendu pour aujourd’hui.':'Collecte manuelle armée pour cette journée uniquement.';collectionUpdateStatus({...result,dependency_ready:true});}
    }catch(e){if(h.isConnected)h.textContent=e.message;}
    finally{collectionActionBusy=false;}
  };
  const toggle=document.querySelector('#collection-auto-toggle');toggle.onchange=()=>{toggle.parentElement.querySelector('b').textContent=toggle.checked?'Activée':'Désactivée';collectionSetAuto(toggle.checked);};
  document.querySelector('#collection-form').onsubmit=e=>{e.preventDefault();act('start');};document.querySelector('#collection-save').onclick=()=>act('configure');document.querySelector('#collection-probe').onclick=()=>act('probe');document.querySelector('#collection-stop').onclick=()=>act('stop');collectionBindHermesAdminEvents();
  if(currentUser?.role==='admin'){
    document.querySelector('#hermes-credentials-save')?.addEventListener('click',()=>{const username=document.querySelector('#hermes-username')?.value||'',password=document.querySelector('#hermes-password')?.value||'',enabled=!!document.querySelector('#hermes-auto-login')?.checked;if(!username||!password){document.querySelector('#hermes-credential-message').textContent='Saisissez l’identifiant et le mot de passe Hermes pour enregistrer ou remplacer le coffre.';return;}collectionHermesCredentialAction('hermes-credentials',{username,password,auto_login:enabled});});
    document.querySelector('#hermes-credentials-delete')?.addEventListener('click',()=>collectionHermesCredentialAction('hermes-credentials-delete',{}));
    document.querySelector('#hermes-auto-login')?.addEventListener('change',e=>{const label=e.target.parentElement.querySelector('b');if(e.target.dataset.configured==='1')collectionHermesCredentialAction('hermes-auto-login',{enabled:!!e.target.checked});else if(label)label.textContent=e.target.checked?'Activé après enregistrement':'Désactivé après enregistrement';});
  }
  collectionLiveDay=d.server_day;collectionLivePage=0;collectionUpdateStatus(d);await Promise.all([collectionLoadLive(ticket,collectionLiveDay),collectionLoadDiagnostic(ticket),collectionHermesCredentialLoad(),collectionHermesScanLoad(ticket)]);collectionTimer=setTimeout(()=>collectionPoll(ticket),5000);
}

let collectionViewIntent=null;
function collectionOpenView(view,day){
  if(!/^\d{4}-\d{2}-\d{2}$/.test(day))return;
  collectionViewIntent={view,day};
  try{sessionStorage.setItem('nelyio-live-open',JSON.stringify(collectionViewIntent));}catch(_){}
  location.hash='#'+view;
}
function collectionDayQuery(view){
  let v=collectionViewIntent;
  try{v=v||JSON.parse(sessionStorage.getItem('nelyio-live-open')||'null');}catch(_){}
  if(v?.view===view&&/^\d{4}-\d{2}-\d{2}$/.test(v.day)){
    collectionViewIntent=null;try{sessionStorage.removeItem('nelyio-live-open');}catch(_){}
    return 'date_from='+v.day+'&date_to='+v.day+'&day='+v.day;
  }
  return '';
}
// Live numbers and source evidence: no undocumented timer is called patient wait.
function livePhoneText(r){
  if(r.phone)return r.phone;
  return ({anonymous:'Anonyme',disabled:'Collecte d\u00e9sactiv\u00e9e',not_provided:'Non transmis',legacy:'Non enregistr\u00e9 (ancien)'})[r.phone_status]||'Non disponible';
}
function liveStatusText(r){
  return ({observing:'En cours (observ\u00e9)',left_call:'Sortie d\u2019appel observ\u00e9e',segment_changed:'Segment suivant',capture_gap:'Capture interrompue',capture_ended:'Collecte arr\u00eat\u00e9e',unconfirmed:'\u00c9tat non actualis\u00e9',legacy:'Ancienne observation'})[r.live_status]||'Observation';
}
function liveSpanText(r){
  const n=r.observed_span_seconds;
  return n===null||n===undefined?(r.live_status==='capture_gap'?'Suivi interrompu':'Non mesurable'):supDuration(n)+' suivies';
}
function liveCounterTable(counters){
  const rows=Object.entries(counters||{}).sort(([a],[b])=>Number(a.slice(4))-Number(b.slice(4)));
  if(!rows.length)return '<p class="sub">Aucun compteur conserv\u00e9.</p>';
  return '<dl class="live-counter-list">'+rows.map(([k,v])=>`<div><dt>${esc(k)}</dt><dd>${esc(String(v))}</dd></div>`).join('')+'</dl>';
}
function collectionOpenCallDetail(r){
  document.querySelector('#live-call-detail')?.remove();
  const dlg=document.createElement('dialog');dlg.id='live-call-detail';dlg.className='details-log-dialog live-call-dialog';
  const fields=[['Num\u00e9ro appelant',livePhoneText(r)],['Agent',`${r.name||r.agent} (${r.agent})`],['Client',r.campaign||'\u2014'],['File',r.line_name||r.line_id||'\u2014'],['Premi\u00e8re observation',r.start_text],['Dernier \u00e9tat re\u00e7u',r.last_observation_text||r.start_text],['Suivi jusqu\u2019\u00e0',r.observed_until_text||r.start_text],['Statut',liveStatusText(r)],['Dur\u00e9e suivie',liveSpanText(r)],['\u00c9tat source',r.state],['\u00c9tat suivant',r.next_state||'\u2014'],['Dur\u00e9e totale / conversation', 'Non certifi\u00e9es par ce flux'],['Attente patient','Compteur individuel non identifi\u00e9'],['\u00c9chantillons re\u00e7us',r.observation_count||1],['R\u00e9f\u00e9rence observation (pas ID appel)',r.key]];
  dlg.innerHTML=`<div class="details-dialog-head"><h3>D\u00e9tails de l\u2019appel live</h3><button type="button" class="details-dialog-close" aria-label="Fermer">\u00d7</button></div>
    <dl class="details-dialog-fields">${fields.map(([k,v])=>`<div class="details-field"><dt>${esc(k)}</dt><dd>${esc(String(v??'\u2014'))}</dd></div>`).join('')}</dl>
    <p class="collection-hint">La dur\u00e9e suivie est une estimation depuis la premi\u00e8re observation, born\u00e9e \u00e0 la derni\u00e8re r\u00e9ponse valide. Ce n\u2019est pas une dur\u00e9e totale ou de conversation certifi\u00e9e. ${r.partial_start?'Capture commenc\u00e9e dans un \u00e9tat d\u00e9j\u00e0 actif.':''} Aucun compteur global n\u2019est attribu\u00e9 \u00e0 l\u2019attente du patient.</p>
    <details class="live-source-details"><summary>Compteurs Hermes re\u00e7us</summary><p class="sub">${esc(r.source_function||'UpAgtTState')} \u00b7 positions d\u2019arguments \u00e0 partir de z\u00e9ro. Unit\u00e9s et signification non confirm\u00e9es.</p><h4>Premier \u00e9chantillon</h4>${liveCounterTable(r.first_counters)}<h4>Dernier \u00e9chantillon en appel</h4>${liveCounterTable(r.source_counters)}${Object.keys(r.end_counters||{}).length?'<h4>Sortie de l\u2019\u00e9tat appel</h4>'+liveCounterTable(r.end_counters):''}</details>
    <details class="live-source-details"><summary>Chronologie (${Number(r.observation_count||1)} \u00e9chantillons)</summary><div class="table-wrap"><table><thead><tr><th>Heure de r\u00e9ception</th><th>\u00c9tat</th><th>Compteurs source</th></tr></thead><tbody>${(r.timeline||[]).map(t=>`<tr><td>${esc(t.stamp_text)}</td><td>${esc(t.state)}</td><td>${esc(Object.entries(t.counters||{}).map(([k,v])=>k+'='+v).join(' ; '))}</td></tr>`).join('')}</tbody></table></div>${r.timeline_trimmed?`<p class="sub">${Number(r.timeline_trimmed)} \u00e9chantillons interm\u00e9diaires restent dans les logs d\u00e9taill\u00e9s.</p>`:''}</details>
    <details class="live-source-details"><summary>Statistiques de contexte agent / file</summary><p class="sub">Instantan\u00e9s cumul\u00e9s de contexte, pas des mesures de cet appel. Horodatage affich\u00e9 pour chaque source.</p>${(r.context_counters||[]).map(x=>`<h4>${esc(x.function)} \u00b7 ${esc(x.stamp_text)}</h4>${liveCounterTable(x.counters)}`).join('')||'<p class="sub">Aucun instantan\u00e9 disponible.</p>'}</details>`;
  const opener=document.activeElement;
  const dismiss=()=>{if(dlg.open)dlg.close();dlg.remove();if(opener?.isConnected)opener.focus({preventScroll:true});};
  document.body.append(dlg);dlg.querySelector('button').onclick=dismiss;
  dlg.addEventListener('cancel',e=>{e.preventDefault();dismiss();},{once:true});
  dlg.addEventListener('keydown',e=>{if(e.key==='Escape'){e.preventDefault();dismiss();}});
  dlg.addEventListener('close',()=>dlg.remove(),{once:true});dlg.showModal();
}
function collectionRenderObservations(data){
  const host=document.querySelector('#calls-live-observations');if(!host)return;const d=data.live_observations||{};
  if(!d.count){host.innerHTML=d.suppressed_days?.length?'<p class="collection-hint">Export journalier utilis\u00e9 sur les journ\u00e9es import\u00e9es. Le live reste dans D\u00e9tails, sans double comptage.</p>':'';return;}
  const rows=d.rows||[],disabled=rows.some(r=>r.phone_status==='disabled');
  const heading=d.revision==='V56.3-live-1'?'Appels live \u00b7 V56.3':'Observations live \u00b7 ancien collecteur';
  host.innerHTML=`<section class="card panel live-calls-panel"><div class="panel-head"><div><h2>${heading} <span class="sub">${Number(d.count)} observations</span></h2><span class="collection-partial-label">Dur\u00e9e suivie estim\u00e9e depuis la premi\u00e8re observation. D\u00e9tails et compteurs Hermes accessibles sur chaque ligne. Hors totaux export\u00e9s.</span></div></div>
    ${disabled?'<p class="collection-warning">Num\u00e9ros non conserv\u00e9s : activer \u00ab Collecter les num\u00e9ros \u00bb dans Collecte live avant de red\u00e9marrer la collecte. Les anciennes valeurs absentes ne sont pas recr\u00e9\u00e9es.</p>':''}
    <div class="table-wrap"><table id="live-calls-table"><thead><tr><th data-required-column>D\u00e9tails</th><th>Heure observ\u00e9e</th><th>Agent</th><th data-required-column>Num\u00e9ro patient</th><th data-required-column>Dur\u00e9e suivie</th><th data-required-column>Attente patient</th><th>Client / file</th><th>\u00c9tat</th></tr></thead><tbody>${rows.map((r,i)=>`<tr><td><button type="button" class="button ghost" data-live-call-detail="${i}">D\u00e9tails</button></td><td>${esc(r.start_text)}</td><td>${esc(r.name)}<small class="sub">${esc(r.agent)}</small></td><td data-live-field="phone">${esc(livePhoneText(r))}</td><td data-live-field="duration">${esc(liveSpanText(r))}</td><td data-live-field="wait">Non identifi\u00e9e<small class="sub">Compteurs dans D\u00e9tails</small></td><td>${esc(r.campaign||'\u2014')}<small class="sub">${esc(r.line_name||r.line_id||'\u2014')}</small></td><td>${esc(liveStatusText(r))}</td></tr>`).join('')}</tbody></table></div><div class="sup-pager"><button class="button ghost" id="live-calls-prev" ${d.page<=0?'disabled':''}>Pr\u00e9c\u00e9dent</button><span>Page ${d.page+1} / ${Math.ceil(d.count/50)}</span><button class="button ghost" id="live-calls-next" ${(d.page+1)*50>=d.count?'disabled':''}>Suivant</button></div></section>`;
  host.querySelectorAll('[data-live-call-detail]').forEach(b=>b.onclick=()=>collectionOpenCallDetail(rows[Number(b.dataset.liveCallDetail)]));
  document.querySelector('#live-calls-prev').onclick=()=>{callsObservationPage=Math.max(0,callsObservationPage-1);callsLoad();};document.querySelector('#live-calls-next').onclick=()=>{callsObservationPage++;callsLoad();};
}
window.addEventListener('hashchange',()=>{document.querySelector('#live-call-detail')?.remove();if(location.hash!=='#collection'){collectionGeneration++;clearTimeout(collectionTimer);}});
// V60: Live is intentionally isolated. No global Support/Details/Calls polling.
