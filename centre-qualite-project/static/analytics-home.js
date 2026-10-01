let analyticsHomeGeneration=0;
const analyticsHomeState={day:'',time_from:'',time_to:'',service:'',group:'',min_volume:'30',selectedSignal:0};

function ahNum(v,d=0){return v===null||v===undefined?'—':Number(v).toLocaleString('fr-FR',{minimumFractionDigits:d,maximumFractionDigits:d});}
function ahPct(v){return v===null||v===undefined?'—':`${ahNum(v,1)} %`;}
function ahSec(v){if(v===null||v===undefined)return '—';const n=Math.max(0,Math.round(Number(v)||0));return n<60?`${n} s`:`${Math.floor(n/60)}m ${String(n%60).padStart(2,'0')}s`;}
function ahOption(v,l,s){return `<option value="${esc(v)}" ${String(v)===String(s)?'selected':''}>${esc(l)}</option>`;}
function ahMetricValue(code,value){if(code.includes('wait')||code==='asa_high')return ahSec(value);if(code.includes('qos')||code.includes('abandon'))return ahPct(value);return ahNum(value);}
function ahScope(signal,d){return signal?.scope_label||signal?.service_name||d.service||((d.selected_groups||[]).length?`Sous-groupe ${d.selected_groups.join(', ')}`:'Périmètre global');}
function ahSignalTone(signal){return signal?.severity==='danger'?'danger':'warning';}
function ahReliabilityText(d){const r=d.reliability||{};return r.status||'Non déterminée';}
function ahDeepLink(kind,d,signal){
  const s=analyticsHomeState;
  if(kind==='pilotage'){
    try{Object.assign(pilotageState,{day:d.day||s.day,time_from:d.time_from||s.time_from,time_to:d.time_to||s.time_to,service:s.service,group:s.group,min_volume:s.min_volume,tab:'analysis'});}catch{}
    location.hash='#quality-pilotage';return;
  }
  if(kind==='overview'){
    try{Object.assign(qualityOverviewState,{date_from:d.day,date_to:d.day,time_from:d.time_from,time_to:d.time_to,service:s.service,group:s.group,campaign:'',agent:'',agent_search:''});}catch{}
    location.hash='#quality-overview';return;
  }
  if(kind==='agents'){
    try{Object.assign(qualityActivityState,{date_from:d.day,date_to:d.day,time_from:d.time_from,time_to:d.time_to,service:s.service,group:s.group,search:'',selectedAgent:''});}catch{}
    location.hash='#quality-activity';return;
  }
  if(kind==='distribution'){
    try{Object.assign(distributionState,{date_from:d.day,date_to:d.day,time_from:d.time_from,time_to:d.time_to,service:s.service,group:s.group,agent:'',campaign:''});}catch{}
    location.hash='#quality-distributions';return;
  }
  if(kind==='suspects'){
    const q=new URLSearchParams({date_from:d.day||'',date_to:d.day||''});if(s.service)q.set('service',s.service);if(s.group)q.set('group',s.group);
    location.hash='#suspicious-calls?'+q.toString();return;
  }
}
function ahActionDialog(d,signal){
  const title=signal?.title||'Action Qualité';
  return `<dialog id="ah-action-dialog" class="ah-action-dialog"><form id="ah-action-form">
    <h2>Créer une action</h2><p class="q-note">L'action sera enregistrée dans le suivi Qualité. Elle ne sera jamais présentée comme cause certaine d'une amélioration ultérieure.</p>
    <label>Titre<input name="title" maxlength="160" required value="${esc(title)}"></label>
    <label>Statut<select name="status">${['À faire','En cours','Appliqué','À vérifier','Clos'].map(x=>ahOption(x,x,'À faire')).join('')}</select></label>
    <label>Date d’application<input type="date" name="application_date"></label>
    <label>Commentaire<textarea name="comment" rows="4" maxlength="4000" placeholder="Action prévue, responsable, contexte…">${esc(signal?.detail?`Fait observé : ${signal.detail}`:'')}</textarea></label>
    <div id="ah-action-result" class="form-result"></div><div class="q-actions"><button type="button" class="button ghost" id="ah-action-cancel">Annuler</button><button class="button">Enregistrer</button></div>
  </form></dialog>`;
}

async function analyticsHomeView(){
  const s=analyticsHomeState,g=++analyticsHomeGeneration,user=currentUser;
  activate('analytics-home');setHead('Synthèse Analytiques','Signal → explication → périmètre → preuve → drilldown → action');
  app.innerHTML='<div class="loading">Chargement…</div>';
  const active=()=>g===analyticsHomeGeneration&&location.hash==='#analytics-home'&&user===currentUser&&canRead('quality');
  try{
    const q=new URLSearchParams();for(const k of ['day','time_from','time_to','service','group','min_volume'])if(s[k])q.set(k,s[k]);
    const d=await api('/api/quality/pilotage?'+q);if(!active())return;
    for(const k of ['day','time_from','time_to','service','group','min_volume'])if(d[k]!==undefined)s[k]=String(d[k]??'');
    const groups=(d.groups||[]).filter(x=>!s.service||String(x.service_name||'').toLowerCase()===s.service.toLowerCase());
    const signals=d.signals||[];if(s.selectedSignal>=signals.length)s.selectedSignal=Math.max(0,signals.length-1);const selected=signals[s.selectedSignal]||null;
    const current=d.current||{},base=d.baseline||{},files=d.files_to_investigate?.rows||[],verify=d.actions_to_verify||[],rel=d.reliability||{};
    const signalCards=signals.length?signals.map((x,i)=>`<button type="button" class="ah-signal-card ${ahSignalTone(x)} ${i===s.selectedSignal?'active':''}" data-ah-signal="${i}"><span>${x.severity==='danger'?'Attention forte':'À surveiller'}</span><strong>${esc(x.title)}</strong><small>${esc(ahScope(x,d))}</small><em>${ahMetricValue(x.code||'',x.current)} · réf. ${ahMetricValue(x.code||'',x.baseline)}</em></button>`).join(''):`<div class="ah-clear"><strong>Aucun signal majeur</strong><span>Selon les références comparables disponibles sur ce périmètre.</span></div>`;
    const proofFiles=files.slice(0,5).map(r=>`<article class="ah-proof-row"><div><strong>${esc(r.file||('File '+r.file_id))}</strong><small>${esc((r.factors||[]).join(' · ')||'À investiguer')}</small></div><div><b>${ahNum(r.received)}</b><span>reçus</span></div><div><b>${ahPct(r.abandonment_rate)}</b><span>abandon</span></div><div><b>${ahSec(r.p90_wait)}</b><span>P90</span></div></article>`).join('');
    app.innerHTML=`<section class="q-page ah-page">
      <form id="ah-filters" class="q-toolbar"><div class="q-main-filters">
        <label>Journée<input type="date" name="day" value="${esc(s.day)}" required></label><label>Début<input type="time" name="time_from" value="${esc(s.time_from)}" required></label><label>Fin<input type="time" name="time_to" value="${esc(s.time_to)}" required></label>
        <label>Service<select name="service">${ahOption('','Tous les services',s.service)}${(d.services||[]).map(x=>ahOption(x,x,s.service)).join('')}</select></label>
        <label>Sous-groupe<select name="group">${ahOption('','Tous les sous-groupes',s.group)}${groups.map(x=>ahOption(x.id,(x.service_name?x.service_name+' · ':'')+x.name,s.group)).join('')}</select></label>
        <label>Volume minimum<input type="number" min="1" max="10000" name="min_volume" value="${esc(s.min_volume)}"></label>
      </div><div class="q-actions"><button class="button">Appliquer</button><button type="button" class="button ghost" id="ah-reset">Réinitialiser</button></div></form>

      <div class="ah-context"><span><b>${esc(d.day)}</b> · ${esc(d.time_from)}–${esc(d.time_to)}</span><span>Référence : ${d.baseline_status==='ready'?esc((d.baseline_days||[]).join(', ')):'données insuffisantes'}</span><span>Fiabilité : <b>${esc(ahReliabilityText(d))}</b></span></div>

      <section class="ah-kpis" aria-label="Repères principaux">
        <article><small>QoS</small><strong>${ahPct(current.qos)}</strong><span>réf. ${d.baseline_status==='ready'?ahPct(base.qos):'—'}</span></article>
        <article><small>Taux d’abandon</small><strong>${ahPct(current.abandonment_rate)}</strong><span>réf. ${d.baseline_status==='ready'?ahPct(base.abandonment_rate):'—'}</span></article>
        <article><small>P90 attente</small><strong>${ahSec(current.p90_wait)}</strong><span>réf. ${d.baseline_status==='ready'?ahSec(base.p90_wait):'—'}</span></article>
        <article><small>Agents ayant traité</small><strong>${ahNum(current.agents_treating)}</strong><span>historique, pas connectés Live</span></article>
      </section>

      <section class="ah-step"><div class="ah-step-number">1</div><div class="ah-step-body"><div class="ah-step-head"><div><h2>Signal</h2><p>Maximum 5 anomalies explicables. Ce n’est pas un classement de performance.</p></div><span>${signals.length}</span></div><div class="ah-signal-grid">${signalCards}</div></div></section>

      ${selected?`<section class="ah-path">
        <article class="ah-step"><div class="ah-step-number">2</div><div class="ah-step-body"><h2>Explication</h2><div class="ah-explanation"><div><small>Fait observé</small><strong>${esc(selected.title)}</strong><p>${ahMetricValue(selected.code||'',selected.current)} · référence ${ahMetricValue(selected.code||'',selected.baseline)} · ${esc(selected.detail||'')}</p></div><div><small>À vérifier</small><p>${(selected.hypotheses||[]).map(x=>`<span class="ah-hypothesis">${esc(x)}</span>`).join('')||'Aucune hypothèse proposée.'}</p></div></div></div></article>
        <article class="ah-step"><div class="ah-step-number">3</div><div class="ah-step-body"><h2>Périmètre</h2><div class="ah-scope-card"><strong>${esc(ahScope(selected,d))}</strong><span>${esc(d.day)} · ${esc(d.time_from)}–${esc(d.time_to)}</span><span>Comparaison avec le même périmètre et les mêmes créneaux historiques.</span></div></div></article>
        <article class="ah-step"><div class="ah-step-number">4</div><div class="ah-step-body"><div class="ah-step-head"><div><h2>Preuves</h2><p>Faits observables et limites de fiabilité.</p></div><span>${files.length} file(s) à investiguer</span></div>${proofFiles?`<div class="ah-proof-list">${proofFiles}</div>`:'<p class="q-note">Aucune file ne ressort selon les règles d’investigation actuelles.</p>'}<details class="qo-definitions"><summary>Fiabilité des preuves</summary><p>Qualité source : ${esc(rel.status||'—')} · durées invalides : ${ahNum(rel.invalid_durations)} · cohérence : ${rel.coherence_ok===true?'OK':rel.coherence_ok===false?'à vérifier':'—'}.</p>${(d.limitations||[]).map(x=>`<p>${esc(x)}</p>`).join('')}</details></div></article>
        <article class="ah-step"><div class="ah-step-number">5</div><div class="ah-step-body"><h2>Drilldown</h2><p class="q-note">Ouvrir uniquement l’écran spécialisé nécessaire à l’investigation.</p><div class="ah-drill-grid"><button class="button ghost" data-ah-open="pilotage">Analyse détaillée</button><button class="button ghost" data-ah-open="overview">Qualité de service</button><button class="button ghost" data-ah-open="agents">Qualité agents</button><button class="button ghost" data-ah-open="distribution">Distribution horaire</button><button class="button ghost" data-ah-open="suspects">Appels suspects</button></div></div></article>
        <article class="ah-step"><div class="ah-step-number">6</div><div class="ah-step-body"><h2>Action</h2><p>Tracer une décision uniquement lorsque l’investigation justifie une intervention.</p><div class="q-actions">${canWrite('quality')?'<button type="button" class="button" id="ah-create-action">Créer une action</button>':''}<button type="button" class="button ghost" data-ah-open="pilotage">Voir le suivi des actions</button></div></div></article>
      </section>`:`<section class="ah-no-signal"><div><h2>Pas de signal majeur à expliquer</h2><p>Les écrans détaillés restent disponibles pour l’analyse, mais Nelyio n’invente pas une anomalie lorsqu’aucun écart significatif n’est détecté.</p></div><div class="ah-improvements">${(d.improvements||[]).map(x=>`<span>${esc(x.title)} · ${esc(x.detail||'')}</span>`).join('')||'<span>Aucune amélioration statistique notable signalée.</span>'}</div></section>`}

      <section class="ah-secondary"><div><h2>Actions à vérifier</h2><p>Décisions déjà enregistrées qui nécessitent une vérification avant/après.</p></div><div>${verify.slice(0,5).map(x=>`<article><strong>${esc(x.title)}</strong><span>${esc(x.service_name||'Tous services')}${x.application_date?' · '+esc(x.application_date):''}</span></article>`).join('')||'<p class="q-note">Aucune action au statut « À vérifier ».</p>'}</div><button type="button" class="button ghost small" data-ah-open="pilotage">Ouvrir le suivi complet</button></section>
      ${selected?ahActionDialog(d,selected):''}
    </section>`;

    document.getElementById('ah-filters').onsubmit=e=>{e.preventDefault();const fd=new FormData(e.target);for(const k of ['day','time_from','time_to','service','group','min_volume'])s[k]=String(fd.get(k)||'');s.selectedSignal=0;analyticsHomeView();};
    document.getElementById('ah-filters').elements.service.onchange=e=>{s.service=String(e.target.value||'');s.group='';s.selectedSignal=0;analyticsHomeView();};
    document.getElementById('ah-reset').onclick=()=>{Object.assign(s,{day:'',time_from:'',time_to:'',service:'',group:'',min_volume:'30',selectedSignal:0});analyticsHomeView();};
    document.querySelectorAll('[data-ah-signal]').forEach(b=>b.onclick=()=>{s.selectedSignal=Number(b.dataset.ahSignal)||0;analyticsHomeView();});
    document.querySelectorAll('[data-ah-open]').forEach(b=>b.onclick=()=>ahDeepLink(b.dataset.ahOpen,d,selected));
    const dialog=document.getElementById('ah-action-dialog');
    document.getElementById('ah-create-action')?.addEventListener('click',()=>dialog?.showModal());
    document.getElementById('ah-action-cancel')?.addEventListener('click',()=>dialog?.close());
    document.getElementById('ah-action-form')?.addEventListener('submit',async e=>{e.preventDefault();const body=Object.fromEntries(new FormData(e.target));body.service_name=s.service;body.group_id=s.group;body.anomaly_key=selected?.code||'';body.anomaly_label=selected?.title||'';body.context={day:d.day,time_from:d.time_from,time_to:d.time_to};const out=document.getElementById('ah-action-result');try{await api('/api/quality/action/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});out.textContent='Action enregistrée.';setTimeout(()=>{dialog?.close();analyticsHomeView();},250);}catch(err){out.textContent=err.message;}});
  }catch(err){if(active())app.innerHTML=`<div class="error">${esc(err.message||String(err))}</div>`;}
}
