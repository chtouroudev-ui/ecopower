let liveViewGeneration=0,liveViewTimer=null,liveDurationTimer=null;
const liveSupervisionState={layout:(()=>{try{return localStorage.getItem('nelyio.live.layout')||sessionStorage.getItem('nelyio.live.layout')||'agents';}catch(_){return 'agents';}})(),railCollapsed:(()=>{try{return localStorage.getItem('nelyio.live.railCollapsed')==='1';}catch(_){return false;}})(),agentState:'',agentSignals:{}};
document.addEventListener('fullscreenchange',()=>{if(!document.fullscreenElement)document.body.classList.remove('live-wall-active');});
const liveSearchState={window:'30m',q:'',agent:'',reference:'',page:0};
const liveCampaignsState={q:'',service:'',group:'',status:'',alertsOnly:false,selected:'',detailById:{},detailLoadedAt:{},detailLoading:{},detailError:{},detailQueue:'',detailAgent:''};
const liveIncidentsState={mode:'history',from:'',to:'',page:0,pageSize:100};


// RC29 Phase 2 - shared three-state sort contract for Live tables.
const rc29SortMemory={};
const rc29MissingStrings=new Set(['','—','-','inconnu','unknown','non observé','non observe','non calculable','n/a','null','none']);
function rc29SortLoad(tableKey){
  if(rc29SortMemory[tableKey])return rc29SortMemory[tableKey];
  try{const raw=sessionStorage.getItem('nelyio.rc29.sort.'+tableKey);if(raw){const parsed=JSON.parse(raw);if(parsed&&parsed.key&&['asc','desc'].includes(parsed.direction))return rc29SortMemory[tableKey]=parsed;}}catch(_){ }
  return rc29SortMemory[tableKey]={key:'',direction:'default'};
}
function rc29SortSave(tableKey,state){
  rc29SortMemory[tableKey]=state;
  try{if(state?.key&&state.direction!=='default')sessionStorage.setItem('nelyio.rc29.sort.'+tableKey,JSON.stringify(state));else sessionStorage.removeItem('nelyio.rc29.sort.'+tableKey);}catch(_){ }
  return state;
}
function rc29SortCycle(tableKey,key){
  const cur=rc29SortLoad(tableKey);
  if(cur.key!==key||cur.direction==='default')return rc29SortSave(tableKey,{key,direction:'asc'});
  if(cur.direction==='asc')return rc29SortSave(tableKey,{key,direction:'desc'});
  return rc29SortSave(tableKey,{key:'',direction:'default'});
}
function rc29SortReset(tableKey){return rc29SortSave(tableKey,{key:'',direction:'default'});}
function rc29IsMissing(value){
  if(value===null||value===undefined)return true;
  if(typeof value==='number')return !Number.isFinite(value);
  return rc29MissingStrings.has(String(value).trim().toLocaleLowerCase('fr'));
}
function rc29SortValue(value,type='string'){
  if(rc29IsMissing(value))return null;
  if(['number','percentage','duration','timestamp','state'].includes(type)){const n=Number(value);return Number.isFinite(n)?n:null;}
  return String(value).trim();
}
function rc29SortCompare(a,b,direction,type='string'){
  const av=rc29SortValue(a,type),bv=rc29SortValue(b,type),am=av===null,bm=bv===null;
  if(am||bm){if(am&&bm)return 0;return am?1:-1;}// missing always last, even DESC
  let cmp=(type==='string')?String(av).localeCompare(String(bv),'fr',{numeric:true,sensitivity:'base'}):(av-bv);
  return direction==='desc'?-cmp:cmp;
}
function rc29SortRows(rows,tableKey,specs,idGetter){
  const state=rc29SortLoad(tableKey);const list=(rows||[]).map((row,index)=>({row,index}));
  if(!state.key||state.direction==='default'||!specs[state.key])return list.map(x=>x.row);
  const spec=specs[state.key];
  list.sort((a,b)=>rc29SortCompare(spec.value(a.row),spec.value(b.row),state.direction,spec.type)||String(idGetter(a.row)||'').localeCompare(String(idGetter(b.row)||''),'fr',{numeric:true,sensitivity:'base'})||a.index-b.index);
  return list.map(x=>x.row);
}
function rc29SortHeader(tableKey,key,label,type='string'){
  const state=rc29SortLoad(tableKey),active=state.key===key&&state.direction!=='default';
  const icon=active?(state.direction==='asc'?' ↑':' ↓'):' ↕';
  const aria=active?(state.direction==='asc'?'ascending':'descending'):'none';
  return `<th aria-sort="${aria}"><button type="button" class="quality-sort-button rc29-sort-button" data-rc29-table="${esc(tableKey)}" data-rc29-sort="${esc(key)}" data-sort-type="${esc(type)}">${esc(label)}${icon}</button></th>`;
}

function liveDuration(seconds){
  if(seconds===null||seconds===undefined||!Number.isFinite(Number(seconds)))return '—';
  let n=Math.max(0,Math.floor(Number(seconds)));
  const h=Math.floor(n/3600),m=Math.floor(n/60)%60,s=n%60;
  return h?`${h}h ${String(m).padStart(2,'0')}m ${String(s).padStart(2,'0')}s`:`${m}m ${String(s).padStart(2,'0')}s`;
}
function liveHealthBadge(h){
  const state=String(h?.state||'inactive');
  return `<span class="live-health-badge ${esc(state)}"><span class="live-health-dot"></span>${esc(h?.label||'Live indisponible')}</span>`;
}
function liveStateLabel(kind){
  return ({call:'En appel',hold:'Mise en attente',ready:'Disponible',pause:'Pause',wrap:'Post-appel',offline:'Déconnecté',inactive_context:'Contexte inactif',unobserved:'Non observé',arrival:'Sonnerie',other:'Autre'})[kind]||kind||'Inconnu';
}
function liveNormalizedStateText(value){
  return String(value||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLocaleLowerCase('fr').replace(/\s+/g,' ').trim();
}
function liveAgentStatePresentation(r){
  const raw=liveNormalizedStateText(r?.state),kind=String(r?.kind||'unobserved');let out;
  if(kind==='wrap'||raw.includes('post-travail')||raw.includes('post travail')||raw.includes('post-appel')||raw.includes('post appel')||raw.includes('wrap'))out={label:'Post-appel',classes:'wrap live-postwork',postWork:true,pauseType:'postwork'};
  else if(raw.includes('coaching')||raw==='coach'||raw.includes('pause coaching'))out={label:'Coaching',classes:'pause pause-coaching',postWork:false,pauseType:'coaching'};
  else if(raw.includes('dejeuner')||raw.includes('lunch')||raw.includes('pause midi')||raw.includes('meal break'))out={label:'Pause déjeuner',classes:'pause pause-lunch',postWork:false,pauseType:'lunch'};
  else if(raw.includes('general break')||raw.includes('general breack')||raw.includes('pause generale')||raw.includes('general pause'))out={label:'General Break',classes:'pause pause-general',postWork:false,pauseType:'general'};
  else if(kind==='pause'||raw==='break'||raw.includes('pause'))out={label:'Pause',classes:'pause pause-normal',postWork:false,pauseType:'normal'};
  else out={label:liveStateLabel(kind),classes:kind||'unobserved',postWork:false,pauseType:''};
  if(r?.current_observed===false&&r?.last_known)return {...out,label:`Dernier état · ${out.label}`,classes:`${out.classes} live-last-known`,postWork:false};
  return out;
}
function livePostWorkSeverity(seconds){
  const n=Math.max(0,Number(seconds)||0);
  if(n>25)return 'critical';
  if(n>=15)return 'alert';
  if(n>=10)return 'warning';
  return 'normal';
}
function livePostWorkSignalText(level){
  return level==='critical'?'Critique · > 25 s':level==='alert'?'Alerte · 15–25 s':level==='warning'?'Surveillance · 10–15 s':'';
}
function liveClearPostWorkSeverity(row){
  if(!row)return;
  row.classList.remove('live-postwork-warning','live-postwork-alert','live-postwork-critical');
  const badge=row.querySelector('[data-live-postwork-badge]');if(badge)badge.classList.remove('live-postwork-warning','live-postwork-alert','live-postwork-critical');
  const signal=row.querySelector('[data-live-postwork-signal]');if(signal)signal.textContent='';
}
function liveApplyPostWorkSeverity(durationNode,seconds){
  const row=durationNode?.closest?.('tr');if(!row)return;
  if(row.dataset.liveRuleSignal==='1'){liveClearPostWorkSeverity(row);return;}
  const level=livePostWorkSeverity(seconds);liveClearPostWorkSeverity(row);
  if(level!=='normal'){row.classList.add('live-postwork-'+level);const badge=row.querySelector('[data-live-postwork-badge]');if(badge)badge.classList.add('live-postwork-'+level);}
  const signal=row.querySelector('[data-live-postwork-signal]');if(signal)signal.textContent=livePostWorkSignalText(level);
}

function liveAgentObserved(r){return r?.current_observed!==false&&r?.observed!==false&&String(r?.kind||'')!=='unobserved';}
function liveAgentActivity(r){return liveAgentObserved(r)?(r?.activity||{}):{};}
function liveStateSeconds(r,key){return Number(liveAgentActivity(r)?.state_seconds?.[key]||0);}
function liveCallHold(call){
  if(!call)return '<span class="live-na">—</span>';
  if(call.hold_observed_seconds===null||call.hold_observed_seconds===undefined)return '<span class="live-na">Non certifiée</span>';
  return `<strong>${liveDuration(call.hold_observed_seconds)}</strong><small>${Number(call.hold_observed_segments||0)} segment(s) explicite(s)</small>`;
}
function liveAgentTimeBreakdown(r){
  if(!liveAgentObserved(r))return '<span class="live-na">—</span>';
  const a=liveAgentActivity(r),s=a.state_seconds||{};
  return `<div class="live-agent-times"><span><b>Appel</b>${liveDuration(s.call||0)}</span><span><b>Dispo</b>${liveDuration(s.ready||0)}</span><span><b>Post</b>${liveDuration(s.wrap||0)}</span><span><b>Pause</b>${liveDuration(s.pause||0)}</span><span><b>Déconn.</b>${liveDuration(s.offline||0)}</span></div>`;
}

function liveStatusLabel(status){
  return ({observing:'En cours observé',unconfirmed:'Dernier état non confirmé',capture_gap:'Capture interrompue',left_call:'Sortie d’appel observée',segment_changed:'Segment suivant',capture_ended:'Collecte arrêtée',capture_stopped:'Collecte arrêtée',legacy:'Ancienne observation'})[status]||status||'Observation';
}
function livePhoneLabel(r){
  if(r.phone)return r.phone+(r.phone_masked?' · masqué':'');
  return ({anonymous:'Anonyme',disabled:'Collecte du numéro désactivée',not_provided:'Non transmis',legacy:'Non enregistré'})[r.phone_status]||'Non disponible';
}
function liveStopTimers(){
  if(liveViewTimer){clearTimeout(liveViewTimer);liveViewTimer=null;}
  if(liveDurationTimer){clearInterval(liveDurationTimer);liveDurationTimer=null;}
}
function liveStartDurationTicker(){
  if(liveDurationTimer)clearInterval(liveDurationTimer);
  const started=Date.now();
  const nodes=[...document.querySelectorAll('[data-live-duration]')];
  const tick=()=>{
    const delta=(Date.now()-started)/1000;
    nodes.forEach(el=>{
      const base=Number(el.dataset.liveDuration||0);
      const ticking=el.dataset.liveTick==='1';
      const seconds=base+(ticking?delta:0);
      el.textContent=liveDuration(seconds);
      if(el.dataset.livePostwork==='1')liveApplyPostWorkSeverity(el,seconds);
    });
  };
  tick();liveDurationTimer=setInterval(tick,1000);
}
function liveSchedule(fn,generation){
  if(liveViewTimer)clearTimeout(liveViewTimer);
  liveViewTimer=setTimeout(()=>{if(generation===liveViewGeneration)fn();},5000);
}


const liveCenterColorRules=new Set();
function liveCenterColorClass(color){
  const c=String(color||'#667085').toUpperCase();
  return 'live-center-color-'+c.replace('#','').toLowerCase();
}
function liveCenterEnsureColor(color){
  const c=/^#[0-9A-F]{6}$/.test(String(color||'').toUpperCase())?String(color).toUpperCase():'#667085';
  const cls=liveCenterColorClass(c);
  if(liveCenterColorRules.has(cls))return cls;
  const rule=`.${cls}{--live-color:${c};color:${c};border-color:${c}66;background:${c}12}`;
  for(const sheet of [...document.styleSheets]){
    try{sheet.insertRule(rule,sheet.cssRules.length);liveCenterColorRules.add(cls);break;}catch(_){ }
  }
  return cls;
}
function liveQualityStatus(status,compact=false){
  status=status||{};const cls=liveCenterEnsureColor(status.color||'#667085');
  return `<span class="live-quality-status ${compact?'compact':''} ${cls}"><i></i>${esc(status.label||'INDÉTERMINÉ')}</span>`;
}
function liveMetricValue(metric){
  metric=metric||{};const value=metric.value,unit=String(metric.unit||'');
  if(value===null||value===undefined||!Number.isFinite(Number(value)))return '<span class="live-na">Non disponible</span>';
  if(unit==='s')return `<strong>${liveDuration(Number(value))}</strong>`;
  if(unit==='%')return `<strong>${Number(value).toLocaleString('fr-FR',{minimumFractionDigits:0,maximumFractionDigits:1})} %</strong>`;
  return `<strong>${Number(value).toLocaleString('fr-FR',{maximumFractionDigits:1})}</strong>`;
}
function liveMetricCard(metric,label=''){
  metric=metric||{};const unavailable=metric.value===null||metric.value===undefined;
  const q=String(metric.quality||'unavailable');
  const reason=String(metric.reason||'');
  const reasonText=reason==='semantics_not_certified'?'Source Live non certifiée':reason==='live_data_not_fresh'?'Donnée Live périmée':reason==='metric_missing'?'Métrique absente':'';
  return `<article class="live-quality-metric ${unavailable?'unavailable':''}"><span>${esc(label||metric.label||metric.key||'Métrique')}</span>${liveMetricValue(metric)}<small>${esc(reasonText||(q==='reliable'?'Hermes Live fiable':q==='partial'?'Donnée partielle':'Non exploitable'))}</small></article>`;
}
function liveReasonObserved(reason){
  const unit=String(reason?.unit||''),value=reason?.value,threshold=reason?.threshold;
  const fmt=v=>unit==='s'?liveDuration(v):unit==='%'?`${Number(v).toLocaleString('fr-FR',{maximumFractionDigits:1})} %`:Number(v).toLocaleString('fr-FR',{maximumFractionDigits:1});
  if(value===null||value===undefined)return `${esc(reason?.label||reason?.metric||'Métrique')} : non disponible`;
  return `${esc(reason?.label||reason?.metric||'Métrique')} : <strong>${fmt(value)}</strong> ${esc(reason?.operator||'')} ${fmt(threshold)}`;
}
function liveIncidentSearchHref(incident){
  const type=String(incident?.scope_type||''),key=String(incident?.scope_key||''),label=String(incident?.scope_label||key);
  if(type==='AGENT')return `#live-search?agent=${encodeURIComponent(key)}&window=in_progress`;
  if(type==='CAMPAIGN'||type==='QUEUE')return `#live-search?q=${encodeURIComponent(label)}&window=in_progress`;
  return '';
}
function liveIncidentCard(incident){
  const cls=liveCenterEnsureColor(incident.color||'#667085');
  const reasons=(incident.matched_reasons?.length?incident.matched_reasons:incident.reasons||[]).slice(0,4);
  const searchHref=liveIncidentSearchHref(incident);
  const contributors=(incident.contributors||[]).slice(0,6);
  const scopeType=String(incident.scope_type||'').toUpperCase(),scopeKey=String(incident.scope_key||''),scopeLabel=String(incident.scope_label||scopeKey),directAgent=scopeType==='AGENT'?scopeKey:String(contributors[0]?.agent||'');
  return `<article class="live-signal-card ${cls}" role="button" tabindex="0" data-live-alert-target="1" data-live-alert-scope-type="${esc(scopeType)}" data-live-alert-scope-key="${esc(scopeKey)}" data-live-alert-scope-label="${esc(scopeLabel)}" data-live-alert-agent="${esc(directAgent)}">
    <div class="live-signal-head"><div>${liveQualityStatus({label:incident.level_label,color:incident.color},true)}<span class="live-incident-status status-${esc(String(incident.status||'').toLowerCase())}">${esc(incident.status_label||liveIncidentStatusLabel(incident.status))}</span><strong>${esc(incident.rule_name||'Signal Qualité')}</strong></div><span>${liveDuration(incident.duration_seconds)}</span></div>
    <p><b>${esc(incident.scope_type||'PÉRIMÈTRE')}</b> · ${esc(incident.scope_label||incident.scope_key||'—')}</p>
    <ul>${reasons.map(r=>`<li>${liveReasonObserved(r)}</li>`).join('')||'<li>Condition active — détail métrique indisponible.</li>'}</ul>
    ${contributors.length?`<div class="live-incident-contributors"><small class="live-incident-contributors-label">Agents contributeurs observés</small>${contributors.map(a=>`<span class="live-incident-contributor"><b>${esc(a.name||a.agent)}</b><small>${esc(a.state||a.kind||'')}</small></span>`).join('')}</div>`:''}
    <div class="live-signal-actions"><a class="button" href="#live-incidents?mode=history">Voir l’historique</a>${searchHref?`<a class="button ghost" href="${searchHref}">Voir les appels / états</a>`:''}${canRead('quality')?'<a class="button ghost" href="#quality-pilotage">Pilotage Qualité</a>':''}</div>
  </article>`;
}
function liveScopeMetric(row,key){return row?.metrics?.[key]||{};}
function liveScopeHistoryMap(){
  const rows=liveSupervisionState.scopeQuality?.data?.rows||[];const map=new Map();
  rows.forEach(r=>map.set(`${String(r.scope_type||'')}|${String(r.scope_key||'')}`,r));return map;
}
function liveScopeHistoricalValue(row,key){
  const h=liveScopeHistoryMap().get(`${String(row?.scope_type||'')}|${String(row?.scope_key||'')}`);return h?h[key]:null;
}
function liveAgentHistoryMap(){
  const rows=liveSupervisionState.scopeQuality?.data?.agents||[];const map=new Map();
  rows.forEach(r=>map.set(String(r.agent||''),r));return map;
}
function liveScopeRowsHtml(center,type,query='',queueDiagnostics=null){
  const all=(center?.scopes||[]).filter(x=>String(x.scope_type)===String(type));
  const q=String(query||'').trim().toLocaleLowerCase('fr');
  let rows=q?all.filter(x=>`${x.scope_label||''} ${x.scope_key||''}`.toLocaleLowerCase('fr').includes(q)):all.slice();
  const tableKey=`live-scopes-${String(type).toLowerCase()}`;
  const nativeValue=(r,k)=>r?.native_calls?.[k];
  const histValue=(r,k)=>liveScopeHistoricalValue(r,k);
  const operational=(r,nativeKey,histKey)=>{const v=nativeValue(r,nativeKey);return v===null||v===undefined?histValue(r,histKey):v;};
  const specs={
    scope:{type:'string',value:r=>r.scope_label||r.scope_key},status:{type:'state',value:r=>Number(r.status?.rank)},observed:{type:'number',value:r=>r.observed_agent_count},
    available:{type:'number',value:r=>liveScopeMetric(r,'agents_available')?.value},connected:{type:'number',value:r=>liveScopeMetric(r,'agents_connected')?.value},call:{type:'number',value:r=>liveScopeMetric(r,'agents_in_call')?.value},pause:{type:'number',value:r=>liveScopeMetric(r,'agents_pause')?.value},
    waiting:{type:'number',value:r=>nativeValue(r,'calls_waiting')},inprogress:{type:'number',value:r=>nativeValue(r,'calls_in_progress')},received:{type:'number',value:r=>nativeValue(r,'received_today')},
    treated:{type:'number',value:r=>operational(r,'handled_today','treated')},abandoned:{type:'number',value:r=>operational(r,'abandoned_today','abandoned')},qos:{type:'percentage',value:r=>operational(r,'qos_today','qos')},incidents:{type:'number',value:r=>Number(r.incident_count||0)}
  };
  rows=rc29SortRows(rows,tableKey,specs,r=>r.scope_key);
  const isCampaign=String(type)==='CAMPAIGN',totalRows=rows.length,pageSize=10;
  let pager='';
  if(isCampaign){
    liveSupervisionState.scopePage=0;
    pager=`<div class="live-compact-pager"><span>${totalRows} campagne(s) · défilement vertical</span></div>`;
  }else{
    const maxPage=Math.max(0,Math.ceil(totalRows/pageSize)-1);liveSupervisionState.scopePage=Math.min(Math.max(0,Number(liveSupervisionState.scopePage||0)),maxPage);const pageStart=liveSupervisionState.scopePage*pageSize;rows=rows.slice(pageStart,pageStart+pageSize);
    pager=totalRows>pageSize?`<div class="live-compact-pager"><button class="button ghost small" data-live-scope-page="prev" ${liveSupervisionState.scopePage<=0?'disabled':''}>Précédent</button><span>${pageStart+1}–${Math.min(totalRows,pageStart+pageSize)} / ${totalRows}</span><button class="button ghost small" data-live-scope-page="next" ${liveSupervisionState.scopePage>=maxPage?'disabled':''}>Suivant</button></div>`:`<div class="live-compact-pager"><span>${totalRows} ligne(s)</span></div>`;
  }
  const hmap=liveScopeHistoryMap();
  const nfmt=v=>v===null||v===undefined||!Number.isFinite(Number(v))?'<span class="live-na">—</span>':`<strong>${Number(v).toLocaleString('fr-FR',{maximumFractionDigits:1})}</strong>`;
  const qfmt=v=>v===null||v===undefined||!Number.isFinite(Number(v))?'<span class="live-na">—</span>':`<strong>${Number(v).toLocaleString('fr-FR',{maximumFractionDigits:1})} %</strong>`;
  const cells=rows.map(row=>{
    const status=row.status||{},searchType=['CAMPAIGN','QUEUE'].includes(type),href=searchType?`#live-search?q=${encodeURIComponent(row.scope_label||row.scope_key||'')}&window=in_progress`:'';
    const observed=Number(row.observed_agent_count??row.agent_count??0),configured=Number(row.configured_agent_count??row.agent_count??0);
    const coverage=configured?`${observed}/${configured} état(s) Live observé(s)`:`${observed} état(s) Live observé(s)`;
    const hist=hmap.get(`${String(row.scope_type)}|${String(row.scope_key)}`)||{},native=row.native_calls||{};
    const received=native.received_today??hist.received,treated=native.handled_today??hist.treated,abandoned=native.abandoned_today??hist.abandoned,qos=native.qos_today??hist.qos;
    if(isCampaign){
      const connected=liveScopeMetric(row,'agents_connected')?.value,availableState=liveScopeMetric(row,'agents_available')?.value,pause=liveScopeMetric(row,'agents_pause')?.value;
      const nativeAvailable=Number(native.line_count||0)===1?native.agents_available_on_queue:null,available=availableState??nativeAvailable;
      const availableSource=(availableState===null||availableState===undefined)&&nativeAvailable!==null&&nativeAvailable!==undefined?' · Hermes file':'';
      const hermesCoverage=Number(native.line_count||0)?`Hermes : UpQuH ${Number(native.daily_coverage||0)}/${Number(native.line_count||0)} · UpQuR ${Number(native.realtime_coverage||0)}/${Number(native.line_count||0)}`:'Hermes : aucune file rattachée';
      return `<tr data-scope-key="${esc(row.scope_key||'')}"><td><strong>${esc(row.scope_label||row.scope_key||'—')}</strong><small>${Number(row.incident_count||0)?`${Number(row.incident_count)} alerte(s) · `:''}${esc(coverage)}</small><small class="live-hermes-coverage ${native.daily_quality==='reliable'?'ok':native.daily_quality==='partial'?'partial':'missing'}">${esc(hermesCoverage)}</small></td>
        <td>${nfmt(native.calls_waiting)}</td><td>${nfmt(native.calls_in_progress)}</td><td>${nfmt(received)}</td><td>${nfmt(treated)}</td><td>${nfmt(abandoned)}</td><td>${qfmt(qos)}</td>
        <td>${nfmt(available)}<small>dispo${esc(availableSource)} · ${nfmt(connected)} total · ${nfmt(pause)} pause</small></td></tr>`;
    }
    const hermesCoverage=Number(native.line_count||0)?`UpQuH ${Number(native.daily_coverage||0)}/${Number(native.line_count||0)} · UpQuR ${Number(native.realtime_coverage||0)}/${Number(native.line_count||0)}`:'';
    return `<tr data-scope-key="${esc(row.scope_key||'')}"><td>${liveQualityStatus(status,true)}<small>${row.monitored?`${Number(row.rule_count||0)} règle(s)`:'aucune règle applicable'}</small></td>
      <td><strong>${esc(row.scope_label||row.scope_key||'—')}</strong><small>${esc(row.scope_key&&row.scope_key!==row.scope_label?row.scope_key:'')}</small><small>${esc(coverage)}</small>${hermesCoverage?`<small class="live-hermes-coverage ${native.daily_quality==='reliable'?'ok':native.daily_quality==='partial'?'partial':'missing'}">${esc(hermesCoverage)}</small>`:''}</td>
      <td><strong>${observed}</strong><small>${configured?`${configured} référencé(s)`:''}</small></td><td>${liveMetricValue(liveScopeMetric(row,'agents_available'))}</td><td>${liveMetricValue(liveScopeMetric(row,'agents_in_call'))}</td><td>${liveMetricValue(liveScopeMetric(row,'agents_pause'))}</td>
      <td>${nfmt(received)}</td><td>${nfmt(treated)}</td><td>${nfmt(abandoned)}</td><td>${qfmt(qos)}</td><td>${Number(row.incident_count||0)?`<strong>${Number(row.incident_count)}</strong>`:'0'}${href?`<small><a class="link" href="${href}">Recherche Live</a></small>`:''}</td></tr>`;
  }).join('');
  if(isCampaign){
    const qdiag=queueDiagnostics||{};
    const qhint=Number(qdiag.line_count||0)>0
      ?`<p class="live-scope-limit">Hermes files reçues : ${Number(qdiag.line_count||0)} · temps réel UpQuR : ${Number(qdiag.upqur_count||0)} · stats jour UpQuH : ${Number(qdiag.upquh_count||0)}</p>`
      :`<div class="live-warning live-queue-metrics-warning"><strong>Compteurs de files Hermes non reçus.</strong> Les états agents arrivent, mais aucun UpQuR/UpQuH n'est présent dans la collecte actuelle. Dans l'onglet Hermes capturé, garde la « Liste des files d'attente » ouverte/visible puis relance la collecte.</div>`;
    return `<div class="table-wrap"><table class="live-scope-table live-scope-compact rc29-sort-table"><thead><tr>${rc29SortHeader(tableKey,'scope','Campagne','string')}${rc29SortHeader(tableKey,'waiting','Attente','number')}${rc29SortHeader(tableKey,'inprogress','En cours','number')}${rc29SortHeader(tableKey,'received','Reçus','number')}${rc29SortHeader(tableKey,'treated','Traités','number')}${rc29SortHeader(tableKey,'abandoned','Abandonnés','number')}${rc29SortHeader(tableKey,'qos','QoS','percentage')}<th>Agents</th></tr></thead><tbody>${cells||'<tr><td colspan="8" class="empty">Aucune campagne correspondante.</td></tr>'}</tbody></table></div>${pager}${qhint}`;
  }
  const hist=liveSupervisionState.scopeQuality?.data;
  const period=hist?.available?`Historique importé : Stats.INBOUND · ${esc(hist.period_label||'période non précisée')} · QoS = Traités / (Reçus - Clôturés - Raccrochés avant file d’attente).`:'Historique importé : indisponible pour la période courante.';
  return `<div class="table-wrap"><table class="live-scope-table rc29-sort-table"><thead><tr>${rc29SortHeader(tableKey,'status','Statut','state')}${rc29SortHeader(tableKey,'scope',({SERVICE:'Service',GROUP:'Groupe',QUEUE:'File'})[type]||type,'string')}${rc29SortHeader(tableKey,'observed','Observés','number')}${rc29SortHeader(tableKey,'available','Disponibles','number')}${rc29SortHeader(tableKey,'call','En appel','number')}${rc29SortHeader(tableKey,'pause','Pause','number')}${rc29SortHeader(tableKey,'received','Reçus','number')}${rc29SortHeader(tableKey,'treated','Traités','number')}${rc29SortHeader(tableKey,'abandoned','Abandonnés','number')}${rc29SortHeader(tableKey,'qos','QoS','percentage')}${rc29SortHeader(tableKey,'incidents','Incidents','number')}</tr></thead><tbody>${cells||'<tr><td colspan="11" class="empty">Aucun périmètre correspondant.</td></tr>'}</tbody></table></div>${pager}<p class="live-scope-limit">${rows.length} périmètre(s) affiché(s) sur ${all.length} référencé(s). ${period}</p>`;
}

function liveCertifiedQualityBody(day){
  if(!canOpenInterface('quality_pilotage'))return '';
  const st=liveSupervisionState.certifiedQuality||{};
  if(st.day!==day||(!st.data&&!st.error))return '<div class="loading compact">Chargement des attentes certifiées…</div>';
  if(st.error)return '';
  const d=st.data||{},cur=d.current,base=d.baseline;
  if(!cur)return '';
  const metric=(label,value,unit='',baselineValue=null)=>{
    const valid=value!==null&&value!==undefined&&Number.isFinite(Number(value));if(!valid)return '';
    const text=unit==='s'?liveDuration(Number(value)):unit==='%'?`${Number(value).toLocaleString('fr-FR',{maximumFractionDigits:1})} %`:Number(value).toLocaleString('fr-FR');
    let delta='';if(baselineValue!==null&&baselineValue!==undefined&&Number.isFinite(Number(baselineValue))){const diff=Number(value)-Number(baselineValue);delta=`Réf. ${unit==='s'?liveDuration(Number(baselineValue)):unit==='%'?Number(baselineValue).toLocaleString('fr-FR',{maximumFractionDigits:1})+' %':Number(baselineValue).toLocaleString('fr-FR')} · écart ${diff>=0?'+':''}${unit==='s'?Math.round(diff)+' s':diff.toLocaleString('fr-FR',{maximumFractionDigits:1})+(unit==='%'?' pt':'')}`;}
    return `<article><span>${esc(label)}</span><strong>${esc(text)}</strong><small>${esc(delta||'Stats.INBOUND importé')}</small></article>`;
  };
  const cards=[
    metric('Reçus',cur.received,'',base?.received),metric('Traités',cur.treated,'',base?.treated),metric('Abandonnés',cur.abandoned,'',base?.abandoned),
    metric('Taux abandon',cur.abandonment_rate,'%',base?.abandonment_rate),metric('QoS',cur.qos,'%',base?.qos),
    metric('Attente moyenne',cur.asa,'s',base?.asa),metric('P90 attente',cur.p90_wait,'s',base?.p90_wait),metric('Agents ayant traité',cur.agents_treating,'',base?.agents_treating)
  ].filter(Boolean);
  if(!cards.length)return '';
  const signals=(d.signals||[]).slice(0,4);
  return `<div class="live-certified-kpis">${cards.join('')}</div>
    <div class="live-certified-foot"><span>Source : Stats.INBOUND importé · ${esc(d.time_from||'08:00')}–${esc(d.time_to||'19:00')} · référence ${d.baseline_status==='ready'?`${(d.baseline_days||[]).length} jour(s) comparable(s)`:'insuffisante'}</span>${signals.length?`<details><summary>${signals.length} signal(aux) historique(s)</summary>${signals.map(x=>`<p><strong>${esc(x.scope_label||x.service_name||'Périmètre')}</strong> — ${esc(x.title||'Signal')} · ${esc(x.detail||'')}</p>`).join('')}</details>`:''}</div>`;
}

async function liveRefreshCertifiedQuality(day,generation,active,groupId=''){
  if(!canOpenInterface('quality_pilotage'))return;
  const now=Date.now(),st=liveSupervisionState.certifiedQuality||(liveSupervisionState.certifiedQuality={day:'',loadedAt:0,data:null,error:'',loading:false});
  if(st.loading)return;
  const cacheKey=`${day}|${groupId||''}`;
  if(st.cacheKey===cacheKey&&st.loadedAt&&now-st.loadedAt<60000)return;
  st.loading=true;st.day=day;st.cacheKey=cacheKey;st.loadedAt=now;st.error='';
  try{const gp=groupId?`&group=${encodeURIComponent(groupId)}`:'';st.data=await api(`/api/quality/pilotage?day=${encodeURIComponent(day)}&min_volume=30&granularity=60${gp}`);}catch(err){st.data=null;st.error=err.message||'Données Qualité indisponibles.';}finally{st.loading=false;}
  if(generation===liveViewGeneration&&active()){
    const node=document.getElementById('live-certified-quality-body');if(node){const html=liveCertifiedQualityBody(day);node.innerHTML=html;const panel=node.closest('.live-certified-panel');if(panel)panel.hidden=!html;}
  }
}

async function liveRefreshScopeQuality(day,generation,active,groupId='',onUpdate=null){
  const now=Date.now(),st=liveSupervisionState.scopeQuality||(liveSupervisionState.scopeQuality={cacheKey:'',loadedAt:0,data:null,error:'',loadingKey:''});
  const cacheKey=`${day}|${groupId||''}`;
  if(st.loadingKey===cacheKey)return;
  if(st.cacheKey===cacheKey&&st.loadedAt&&now-st.loadedAt<60000){if(onUpdate)onUpdate();return;}
  st.loadingKey=cacheKey;st.error='';
  const gp=groupId?`&group=${encodeURIComponent(groupId)}`:'';
  try{
    const data=await api(`/api/live/scope-quality?day=${encodeURIComponent(day)}${gp}`);
    if(st.loadingKey!==cacheKey)return;
    st.data=data;st.cacheKey=cacheKey;st.loadedAt=Date.now();
  }catch(err){if(st.loadingKey===cacheKey){st.data=null;st.cacheKey=cacheKey;st.loadedAt=Date.now();st.error=err.message||'Historique périmètres indisponible.';}}
  finally{if(st.loadingKey===cacheKey)st.loadingKey='';}
  if(generation===liveViewGeneration&&active()&&onUpdate)onUpdate();
}

function liveAgentSortSpecs(){
  const stateRank={call:70,hold:65,ready:60,arrival:55,wrap:50,pause:40,inactive_context:35,other:30,offline:20,unobserved:10};
  return {
    agent:{type:'string',value:r=>r.name||r.agent},id:{type:'string',value:r=>r.agent},state:{type:'state',value:r=>stateRank[String(r.kind||'unobserved')]??0},
    duration:{type:'duration',value:r=>liveAgentObserved(r)?r.state_age_seconds:null},campaign:{type:'string',value:r=>r.campaign_name||r.campaign||r.current_call?.campaign_name||r.current_call?.campaign},
    handled:{type:'number',value:r=>r.hermes_daily?.reception_today??liveAgentHistoryMap().get(String(r.agent||''))?.handled},callDuration:{type:'duration',value:r=>r.current_call?.call_age_seconds},pauseDuration:{type:'duration',value:r=>r.hermes_daily?.pause_seconds_today},offlineDuration:{type:'duration',value:r=>r.activity?.state_seconds?.offline},ani:{type:'string',value:r=>r.current_call?.phone||''}
  };
}
function liveAgentStateBucket(kind,row=null){if(row?.current_observed===false||row?.observed===false)return 'unobserved';kind=String(kind||'unobserved');if(kind==='hold')return 'hold';if(kind==='call')return 'call';if(kind==='ready')return 'ready';if(kind==='offline')return 'offline';if(kind==='pause')return 'pause';if(kind==='wrap')return 'wrap';if(kind==='unobserved')return 'unobserved';return '';}
function liveAgentStateCounts(rows){const c={all:0,call:0,hold:0,ready:0,offline:0,pause:0,wrap:0,unobserved:0};for(const r of rows||[]){c.all++;const k=liveAgentStateBucket(r.kind,r);if(k)c[k]++;if(k==='hold')c.call++;}return c;}
function liveAgentStateChips(rows){const c=liveAgentStateCounts(rows),active=String(liveSupervisionState.agentState||'');const chip=(key,label,count)=>`<button type="button" class="live-state-chip ${active===key?'active':''}" data-live-agent-state="${key}"><span>${label}</span><b>${Number(count||0)}</b></button>`;return chip('','Tous',c.all)+chip('call','En appel',c.call)+chip('hold','Mise en attente',c.hold)+chip('ready','Disponible',c.ready)+chip('offline','Déconnectés',c.offline)+chip('pause','Pause',c.pause)+chip('wrap','Post-appel',c.wrap)+chip('unobserved','Non observé',c.unobserved);}
function liveNativeCoverageText(native,source='UpQuH'){const total=Number(native?.line_count||0),covered=Number(source==='UpQuR'?native?.realtime_coverage:native?.daily_coverage||0);if(!total)return `${source} : aucune file rattachée`;if(!covered)return `${source} : 0/${total} file(s)`;return `${source} : ${covered}/${total} file(s)${covered<total?' · partiel':''}`;}
function liveNativeKpi(native,key,unit=''){const value=native?.[key],valid=value!==null&&value!==undefined&&Number.isFinite(Number(value));const text=!valid?'—':unit==='%'?`${Number(value).toLocaleString('fr-FR',{maximumFractionDigits:1})} %`:Number(value).toLocaleString('fr-FR',{maximumFractionDigits:0});return `<strong class="${valid?'':'live-na'}">${text}</strong><small>${esc(liveNativeCoverageText(native,'UpQuH'))}</small>`;}
function liveAgentFilteredSortedRows(rows){
  const q=String(liveSupervisionState.agentQuery||'').trim().toLocaleLowerCase('fr');
  const all=(rows||[]).slice();
  let filtered=q?all.filter(r=>{
    const groups=(r.groups||r.assigned_groups||[]).map(g=>g.name).filter(Boolean).join(' '),services=(r.service_names||[]).join(' ');
    return [r.agent,r.name,services,groups,liveStateLabel(r.kind),r.state,r.line_id,r.campaign_name||r.campaign,r.current_call?.campaign_name].join(' ').toLocaleLowerCase('fr').includes(q);
  }):all;
  const state=String(liveSupervisionState.agentState||'');if(state)filtered=filtered.filter(r=>{const bucket=liveAgentStateBucket(r.kind,r);return state==='call'?['call','hold'].includes(bucket):bucket===state;});
  return rc29SortRows(filtered,'live-agents',liveAgentSortSpecs(),r=>r.agent);
}
function liveAgentConfiguredSignal(r){
  if(!liveAgentObserved(r))return null;
  return (liveSupervisionState.agentSignals||{})[String(r?.agent||'')]||null;
}
function liveAgentRowInner(r){
  const observed=liveAgentObserved(r),known=observed||Boolean(r?.last_known),call=r.current_call,hist=liveAgentHistoryMap().get(String(r.agent||''))||{};
  const presentation=liveAgentStatePresentation(r),configuredSignal=liveAgentConfiguredSignal(r);
  const stateDuration=known&&r.state_age_seconds!==null&&r.state_age_seconds!==undefined
    ?`<span data-live-duration-role="state" data-live-duration="${Number(r.state_age_seconds)||0}" data-live-tick="${r.ticking?'1':'0'}" data-live-postwork="${presentation.postWork?'1':'0'}">${liveDuration(r.state_age_seconds)}</span>`
    :'<span class="live-na">—</span>';
  const callDuration=call&&['call','hold'].includes(String(r.kind||''))&&call.call_age_seconds!==null&&call.call_age_seconds!==undefined
    ?`<span data-live-duration-role="call" data-live-duration="${Number(call.call_age_seconds)||0}" data-live-tick="${call.call_ticking?'1':'0'}">${liveDuration(call.call_age_seconds)}</span>`
    :'<span class="live-na">—</span>';
  const campaign=known?(r.campaign_name||call?.campaign_name||r.campaign||call?.campaign||'—'):'—';
  const hd=r.hermes_daily||{};
  const handledLive=hd.reception_today;
  const handled=handledLive!==null&&handledLive!==undefined?`<strong>${Number(handledLive).toLocaleString('fr-FR')}</strong>`:(hist.handled===null||hist.handled===undefined?'<span class="live-na">—</span>':`<strong>${Number(hist.handled).toLocaleString('fr-FR')}</strong>`);
  const pauseCount=hd.pause_count_today===null||hd.pause_count_today===undefined?'<span class="live-na">—</span>':Number(hd.pause_count_today).toLocaleString('fr-FR');
  const pauseDuration=hd.pause_seconds_today===null||hd.pause_seconds_today===undefined?'<span class="live-na">—</span>':liveDuration(Number(hd.pause_seconds_today));
  const offlineSeconds=r.activity?.state_seconds?.offline;
  const offlineDuration=offlineSeconds===null||offlineSeconds===undefined?'<span class="live-na">—</span>':`<strong>${liveDuration(Number(offlineSeconds))}</strong>`;
  const ani=call?.phone?`${esc(call.phone)}${call.phone_masked?'<small>ANI masqué</small>':''}`:'<span class="live-na">—</span>';
  const stateDurationLabel=String(r.kind||'')==='hold'?'HOLD':'État';
  const postWorkSignal=presentation.postWork&&!configuredSignal?'<small class="live-postwork-signal" data-live-postwork-signal></small>':'';
  const ruleSignal=configuredSignal?`<small class="live-agent-rule-signal ${liveCenterEnsureColor(configuredSignal.color)}"><b>${esc(configuredSignal.level_label||configuredSignal.level_key||'Signal')}</b> · ${esc(configuredSignal.rule_name||'Règle Qualité Live')}</small>`:'';
  const resumeNote=r?.last_known&&!observed?'<small class="live-last-known-note">Conservé en base · à revalider par Hermes</small>':'';
  return `<td><strong>${esc(r.name||r.agent)}</strong><small class="mono">${esc(r.agent)}</small></td><td><span class="live-state ${esc(presentation.classes)}" ${presentation.postWork?'data-live-postwork-badge="1"':''}>${esc(presentation.label)}</span><small><span class="live-duration-label">${stateDurationLabel} · </span>${stateDuration}</small>${resumeNote}${ruleSignal}${postWorkSignal}</td><td>${callDuration}</td><td>${esc(campaign)}</td><td>${handled}</td><td><strong>${pauseCount}</strong><small>${pauseDuration}</small></td><td>${offlineDuration}</td><td class="mono">${ani}</td>`;
}
function liveAgentPageData(rows){
  const all=liveAgentFilteredSortedRows(rows);
  liveSupervisionState.agentPage=0;
  return {all,rows:all,pageSize:all.length||1,maxPage:0,start:0};
}
function liveAgentRosterRows(rows){
  return liveAgentPageData(rows).rows.map(r=>`<tr data-live-agent-id="${esc(r.agent)}" data-live-current="${liveAgentObserved(r)?'1':'0'}">${liveAgentRowInner(r)}</tr>`).join('');
}
function livePatchAgentRoster(rows){
  const body=document.getElementById('live-agent-roster-body');if(!body)return;
  const ordered=liveAgentPageData(rows).rows,keep=new Set();
  for(const r of ordered){
    const id=String(r.agent||'');keep.add(id);let tr=[...body.querySelectorAll('tr[data-live-agent-id]')].find(x=>x.dataset.liveAgentId===id);
    if(!tr){tr=document.createElement('tr');tr.dataset.liveAgentId=id;body.appendChild(tr);}
    tr.dataset.liveCurrent=liveAgentObserved(r)?'1':'0';
    [...tr.classList].filter(x=>x.startsWith('live-center-color-')).forEach(x=>tr.classList.remove(x));
    const configuredSignal=liveAgentConfiguredSignal(r);tr.classList.toggle('live-rule-signal',!!configuredSignal);tr.dataset.liveRuleSignal=configuredSignal?'1':'0';if(configuredSignal)tr.classList.add(liveCenterEnsureColor(configuredSignal.color));
    const hist=liveAgentHistoryMap().get(String(r.agent||''))||{};const inner=liveAgentRowInner(r),signature=[r.name,r.kind,r.state,r.current_observed,r.last_known,r.campaign_name||r.campaign,r.current_call?.phone,r.current_call?.status,r.current_call?.partial_start,hist.handled,r.hermes_daily?.reception_today,r.hermes_daily?.pause_count_today,r.hermes_daily?.pause_seconds_today,r.activity?.state_seconds?.offline].join('|');
    if(tr.dataset.liveSignature!==signature){tr.innerHTML=inner;tr.dataset.liveSignature=signature;}
    else{
      const stateDuration=tr.querySelector('[data-live-duration-role="state"]');
      if(stateDuration){stateDuration.dataset.liveDuration=String(Number(r.state_age_seconds)||0);stateDuration.dataset.liveTick=r.ticking?'1':'0';}
      const callDuration=tr.querySelector('[data-live-duration-role="call"]');
      if(callDuration&&r.current_call){callDuration.dataset.liveDuration=String(Number(r.current_call.call_age_seconds)||0);callDuration.dataset.liveTick=r.current_call.call_ticking?'1':'0';}
    }
    const postWorkDuration=tr.querySelector('[data-live-postwork="1"]');
    if(postWorkDuration)liveApplyPostWorkSeverity(postWorkDuration,Number(r.state_age_seconds)||0);else liveClearPostWorkSeverity(tr);
    body.appendChild(tr);
  }
  body.querySelectorAll('tr[data-live-agent-id]').forEach(tr=>{if(!keep.has(tr.dataset.liveAgentId))tr.remove();});
  const empty=body.querySelector('tr[data-live-agent-empty]');if(empty)empty.remove();
  if(!ordered.length){const tr=document.createElement('tr');tr.dataset.liveAgentEmpty='1';tr.innerHTML='<td colspan="8" class="empty">Aucun agent correspondant à ce filtre.</td>';body.appendChild(tr);}
}
function liveAgentHeaderHtml(){
  const key='live-agents';return `<tr>${rc29SortHeader(key,'agent','Agent','string')}${rc29SortHeader(key,'state','État','state')}${rc29SortHeader(key,'callDuration','Appel total','duration')}${rc29SortHeader(key,'campaign','Campagne','string')}${rc29SortHeader(key,'handled','Traités','number')}${rc29SortHeader(key,'pauseDuration','Pauses','duration')}${rc29SortHeader(key,'offlineDuration','Déconnecté','duration')}${rc29SortHeader(key,'ani','ANI','string')}</tr>`;
}



function liveCampaignMetric(block,key){return block?.calls?.[key]||{};}
function liveCampaignNumber(metric,unit=''){
  const value=metric?.value;
  if(value===null||value===undefined||!Number.isFinite(Number(value)))return '<span class="live-na">—</span>';
  if(unit==='%')return `${Number(value).toLocaleString('fr-FR',{maximumFractionDigits:1})} %`;
  if(unit==='s')return liveDuration(Number(value));
  return Number(value).toLocaleString('fr-FR',{maximumFractionDigits:1});
}
function liveCampaignWindowCard(title,block,subtitle=''){
  block=block||{};const wait=block.wait||{};
  return `<article class="live-campaign-window"><div class="live-campaign-window-head"><strong>${esc(title)}</strong><small>${esc(subtitle||block.source||'')}</small></div>
    <div class="live-campaign-window-grid">
      <div><span>Reçus</span><b>${liveCampaignNumber(liveCampaignMetric(block,'received'))}</b></div>
      <div><span>Traités</span><b>${liveCampaignNumber(liveCampaignMetric(block,'handled'))}</b></div>
      <div><span>Abandonnés</span><b>${liveCampaignNumber(liveCampaignMetric(block,'abandoned'))}</b></div>
      <div><span>Abandon</span><b>${liveCampaignNumber(liveCampaignMetric(block,'abandon_rate'),'%')}</b></div>
      <div><span>QoS</span><b>${liveCampaignNumber(liveCampaignMetric(block,'qos'),'%')}</b></div>
      <div><span>Attente moy.</span><b>${liveCampaignNumber(wait.average_seconds,'s')}</b></div>
      <div><span>Médiane</span><b>${liveCampaignNumber(wait.median_seconds,'s')}</b></div>
      <div><span>P90</span><b>${liveCampaignNumber(wait.p90_seconds,'s')}</b></div>
    </div>${wait.low_volume_flag?'<p class="live-low-volume">Volume faible — indicatif</p>':''}
  </article>`;
}
function liveDrillNumber(value,unit=''){
  if(value===null||value===undefined||!Number.isFinite(Number(value)))return '<span class="live-na">—</span>';
  if(unit==='s')return liveDuration(Number(value));
  if(unit==='%')return `${Number(value).toLocaleString('fr-FR',{maximumFractionDigits:1})} %`;
  return Number(value).toLocaleString('fr-FR',{maximumFractionDigits:1});
}
function liveSuspiciousHref(detail,queue='',agent=''){
  const p=new URLSearchParams();p.set('campaign',detail?.campaign_id||'');
  if(detail?.day){p.set('date_from',detail.day);p.set('date_to',detail.day);}
  if(queue)p.set('queue',queue);if(agent)p.set('agent',agent);
  return '#suspicious-calls?'+p.toString();
}
function liveCampaignDrilldownHtml(detail,fallback,windows){
  const id=String(fallback?.campaign_id||'');
  if(liveCampaignsState.detailLoading?.[id]&&!detail)return '<div class="loading compact">Chargement du drill-down campagne → file → agent → appel…</div>';
  const error=liveCampaignsState.detailError?.[id];
  if(error&&!detail)return `<div class="flash error">${esc(error)}</div>`;
  if(!detail)return '<p class="live-certified-note">Ouvrez le détail pour charger les preuves de cette campagne.</p>';
  const queueFilter=String(liveCampaignsState.detailQueue||''),agentFilter=String(liveCampaignsState.detailAgent||'');
  const queues=detail.queues||[];
  const agents=(detail.agents||[]).filter(a=>!queueFilter||(a.active_files||[]).map(String).includes(queueFilter)||String(a.line_id||'')===queueFilter);
  const calls=(detail.calls?.rows||[]).filter(r=>(!queueFilter||String(r.line_id||'')===queueFilter)&&(!agentFilter||String(r.agent||'')===agentFilter));
  const summary=detail.summary||fallback||{},a=summary.live_now?.agents||{},callsNow=summary.live_now?.calls||{};
  const selectedQueue=queues.find(q=>String(q.file_id)===queueFilter);
  const selectedAgent=(detail.agents||[]).find(x=>String(x.agent)===agentFilter);
  return `<div class="live-campaign-drilldown">
    <section class="live-campaign-now"><div class="panel-head"><div><h3>Résumé opérationnel</h3><p>Hermes Live + configuration des files. Les métriques historiques restent identifiées séparément.</p></div>${liveQualityStatus(summary.status||{},true)}</div>
      <div class="live-campaign-now-grid">
        <div><span>Configurés</span><b>${liveCampaignNumber(a.configured)}</b></div><div><span>ACTIVE sur files</span><b>${liveCampaignNumber(a.active_on_queues)}</b></div>
        <div><span>Connectés</span><b>${liveCampaignNumber(a.connected)}</b></div><div><span>Disponibles</span><b>${liveCampaignNumber(a.available)}</b></div>
        <div><span>En appel</span><b>${liveCampaignNumber(a.on_call)}</b></div><div><span>Mise en attente</span><b>${liveCampaignNumber(a.on_hold)}</b></div>
        <div><span>Post-appel</span><b>${liveCampaignNumber(a.wrap_up)}</b></div><div><span>Pause</span><b>${liveCampaignNumber(a.on_break)}</b></div>
        <div><span>Appels en cours</span><b>${liveCampaignNumber(callsNow.current_observed)}</b></div><div><span>Appels Live 15 min</span><b>${liveCampaignNumber(callsNow.observed_15m)}</b></div>
        <div><span>Appels Live 1 h</span><b>${liveCampaignNumber(callsNow.observed_60m)}</b></div><div><span>Appels Live aujourd'hui</span><b>${liveCampaignNumber(callsNow.observed_today)}</b></div>
        <div><span>Attente en file</span><b>${liveCampaignNumber(callsNow.waiting_now)}</b><small>non certifiée si —</small></div>
      </div>
    </section>
    <div class="live-campaign-window-cards">
      ${liveCampaignWindowCard('15 dernières minutes',summary.last_15m,`${windows?.last_15m?.source||''} · ${windows?.last_15m?.quality||''}`)}
      ${liveCampaignWindowCard("Aujourd'hui",summary.today,`${windows?.today?.source||''} · ${windows?.today?.quality||''}`)}
      ${liveCampaignWindowCard('Référence',summary.reference,summary.trend?.reference_label||'Référence indisponible')}
    </div>
    <section class="live-drill-section"><div class="panel-head"><div><h3>1. Files</h3><p>Cliquez sur une file pour limiter les agents et les appels ci-dessous.</p></div><button type="button" class="button ghost small live-drill-queue" data-file-id="">Toutes les files</button></div>
      <div class="table-wrap"><table class="live-drill-queues"><thead><tr><th>File</th><th>Statut</th><th>Reçus</th><th>Part</th><th>Traités</th><th>Abandonnés</th><th>ACTIVE</th><th>Connectés</th><th>Disponibles</th><th>Post-appel</th><th></th></tr></thead><tbody>${queues.map(f=>`<tr class="${queueFilter===String(f.file_id)?'selected':''}"><td><strong>${esc(f.file_label||f.file_id)}</strong><small>${esc(f.file_id||'')}</small></td><td>${liveQualityStatus(f.status||{},true)}</td><td>${liveDrillNumber(f.received)}</td><td>${liveDrillNumber(f.share_percent,'%')}</td><td>${liveDrillNumber(f.treated)}</td><td>${liveDrillNumber(f.abandoned)}</td><td>${liveDrillNumber(f.active_agents)}</td><td>${liveDrillNumber(f.connected_agents)}</td><td>${liveDrillNumber(f.available_agents)}</td><td>${liveDrillNumber(f.post_call_agents)}</td><td><button type="button" class="button ghost small live-drill-queue" data-file-id="${esc(f.file_id)}">${queueFilter===String(f.file_id)?'Sélectionnée':'Analyser'}</button></td></tr>`).join('')||'<tr><td colspan="11" class="empty">Aucune file exploitable pour cette campagne.</td></tr>'}</tbody></table></div>
    </section>
    <section class="live-drill-section"><div class="panel-head"><div><h3>2. Agents</h3><p>${queueFilter?`File ${esc(selectedQueue?.file_label||queueFilter)} · `:''}état Live + contexte Stats.AGENT importé pour la campagne.</p></div><button type="button" class="button ghost small live-drill-agent" data-agent-id="">Tous les agents</button></div>
      <div class="table-wrap"><table class="live-drill-agents"><thead><tr><th>Agent</th><th>État Live</th><th>Durée état</th><th>Files ACTIVE</th><th>Appels Live</th><th>Temps non disponible</th><th>Traités certifiés</th><th>HOLD importé</th><th>Appel actuel / hold</th><th></th></tr></thead><tbody>${agents.map(x=>{const la=x.activity||{},ss=la.state_seconds||{};return `<tr class="${agentFilter===String(x.agent)?'selected':''}"><td><strong>${esc(x.name||x.agent)}</strong><small>${esc(x.agent)}</small></td><td><span class="live-state ${esc(liveAgentStatePresentation(x).classes)}">${esc(liveAgentStatePresentation(x).label)}</span><small>${esc(x.state||'')}</small></td><td>${liveDrillNumber(x.state_age_seconds,'s')}</td><td>${(x.active_files||[]).map(fid=>`<span class="live-file-chip">${esc(fid)}</span>`).join('')||'—'}</td><td><strong>${Number(la.calls_today||0)}</strong><small>15m ${Number(la.calls_15m||0)} · 1h ${Number(la.calls_60m||0)}</small></td><td><strong>${liveDuration(ss.non_available||0)}</strong><small>pause + déconn. + indisponible</small></td><td>${liveDrillNumber(x.handled_today)}<small>${esc(x.history_quality==='partial'?'import du jour':x.history_quality==='reliable'?'Stats.AGENT certifié':'non disponible')}</small></td><td>${x.hold_quality==='reliable'?liveDrillNumber(x.hold_seconds,'s'):'<span class="live-na">—</span>'}</td><td>${x.current_call?`<a class="link" href="#live-search?reference=${encodeURIComponent(x.current_call.reference)}">${esc(x.current_call.reference)}</a><small>${liveCallHold(x.current_call)}</small>`:'—'}</td><td><button type="button" class="button ghost small live-drill-agent" data-agent-id="${esc(x.agent)}">Appels</button></td></tr>`;}).join('')||'<tr><td colspan="8" class="empty">Aucun agent ACTIVE/observé dans ce périmètre.</td></tr>'}</tbody></table></div>
    </section>
    <section class="live-drill-section"><div class="panel-head"><div><h3>3. Appels Live récents</h3><p>Fenêtre ${esc(detail.calls?.window||'30m')} · ${queueFilter?`file ${esc(selectedQueue?.file_label||queueFilter)} · `:''}${agentFilter?`agent ${esc(selectedAgent?.name||agentFilter)} · `:''}${Number(calls.length)} affiché(s) sur ${Number(detail.calls?.count||0)} observation(s) campagne.</p></div><div class="live-page-actions"><a class="button ghost small" href="#live-search?q=${encodeURIComponent(detail.campaign_label||detail.campaign_id)}&window=30m">Recherche Live complète</a>${canRead('quality')?`<a class="button ghost small" href="${liveSuspiciousHref(detail,queueFilter,agentFilter)}">Appels suspects</a>`:''}</div></div>
      <div class="table-wrap"><table class="live-drill-calls"><thead><tr><th>Heure</th><th>Référence Live</th><th>ANI</th><th>Agent</th><th>File</th><th>État</th><th>Suivi observé</th><th>Mise en attente obs.</th><th>Timeline / diagnostic</th></tr></thead><tbody>${calls.map(r=>`<tr><td>${esc(r.start_text||'—')}<small>dernier ${esc(r.last_text||'—')}</small></td><td class="mono"><a class="link" href="#live-search?reference=${encodeURIComponent(r.reference)}">${esc(r.reference||'—')}</a></td><td>${esc(livePhoneLabel(r))}</td><td><strong>${esc(r.name||r.agent)}</strong><small>${esc(r.agent)}</small></td><td>${esc(r.line_name||r.line_id||'—')}</td><td>${esc(liveStatusLabel(r.status))}<small>${esc(r.state||'')}</small></td><td>${liveDuration(r.observed_span_seconds)}${r.partial_start?'<small>début réel inconnu</small>':''}</td><td>${liveCallHold(r)}</td><td><details class="live-call-inline"><summary>Chronologie observée</summary><ol>${(r.timeline||[]).map(t=>`<li><span>${esc(t.stamp_text||'')}</span> ${esc(t.state||'')} <small>${esc(t.phase||'')}</small></li>`).join('')||'<li>Aucun échantillon détaillé.</li>'}</ol><p><strong>Call ID / attente / conversation certifiée :</strong> non disponibles dans ce flux Live.</p></details></td></tr>`).join('')||'<tr><td colspan="9" class="empty">Aucun appel Live récent correspondant aux filtres.</td></tr>'}</tbody></table></div>
      ${detail.calls?.truncated?'<p class="live-warning">Aperçu borné : utilisez Recherche Live pour élargir l’investigation.</p>':''}
    </section>
    <section class="live-drill-section live-drill-proof"><h3>4. Preuves et limites</h3>${(detail.limitations||[]).map(x=>`<p>${esc(x)}</p>`).join('')}<p>Plan de requêtes : ${detail.query_plan?.bounded?'borné':'non confirmé'} · indépendant du nombre de files/agents : ${detail.query_plan?.independent_of_agent_count?'oui':'non confirmé'}.</p></section>
  </div>`;
}
function liveCampaignDetail(c,windows){
  const id=String(c.campaign_id||''),detail=liveCampaignsState.detailById?.[id];
  return liveCampaignDrilldownHtml(detail,c,windows);
}

function liveCampaignRowsHtml(payload){
  const s=liveCampaignsState,all=payload?.campaigns||[];
  const q=String(s.q||'').trim().toLocaleLowerCase('fr');
  const rows=all.filter(c=>{
    if(q&&!`${c.campaign_label||''} ${c.campaign_id||''} ${(c.services||[]).join(' ')} ${(c.groups||[]).map(g=>g.name).join(' ')}`.toLocaleLowerCase('fr').includes(q))return false;
    if(s.service&&!(c.services||[]).includes(s.service))return false;
    if(s.group&&!(c.groups||[]).some(g=>String(g.id)===String(s.group)))return false;
    if(s.status&&String(c.status?.level_key||'')!==String(s.status))return false;
    if(s.alertsOnly&&!Number(c.incident_count||0))return false;
    return true;
  });
  return `<div class="table-wrap"><table class="live-campaign-table"><thead><tr><th>Statut</th><th>Campagne</th><th>Service / groupes</th><th>Files</th><th>Agents maintenant</th><th>15 min</th><th>Aujourd'hui</th><th>Référence</th><th>Variation</th><th>Concentration</th><th></th></tr></thead><tbody>${rows.map(c=>{
    const a=c.live_now?.agents||{},qv=c.queues||{},l=c.last_15m||{},t=c.today||{},r=c.reference||{};
    const selected=String(s.selected)===String(c.campaign_id);
    const trend=c.trend?.volume_change_vs_reference;
    return `<tr class="live-campaign-main-row ${selected?'selected':''}"><td>${liveQualityStatus(c.status||{},true)}<small>${Number(c.incident_count||0)} incident(s)</small></td>
      <td><strong>${esc(c.campaign_label||c.campaign_id)}</strong><small>${esc(c.identity_quality||'')}</small></td>
      <td>${esc((c.services||[]).join(', ')||'—')}<small>${esc((c.groups||[]).map(g=>g.name).join(', ')||'')}</small></td>
      <td><strong>${Number(qv.count_active||0)} / ${Number(qv.count_configured||0)}</strong><small>${Number(qv.count_under_tension||0)} sous tension</small></td>
      <td><strong>${liveCampaignNumber(a.connected)} conn. · ${liveCampaignNumber(a.available)} disp.</strong><small>${liveCampaignNumber(a.on_call)} appel · ${liveCampaignNumber(a.on_hold)} hold · ${liveCampaignNumber(c.live_now?.calls?.observed_today)} appels Live/jour</small></td>
      <td><strong>${liveCampaignNumber(liveCampaignMetric(l,'received'))} reçus</strong><small>QoS ${liveCampaignNumber(liveCampaignMetric(l,'qos'),'%')} · P90 ${liveCampaignNumber(l.wait?.p90_seconds,'s')}</small></td>
      <td><strong>${liveCampaignNumber(liveCampaignMetric(t,'received'))} reçus</strong><small>${liveCampaignNumber(liveCampaignMetric(t,'abandoned'))} aband. · QoS ${liveCampaignNumber(liveCampaignMetric(t,'qos'),'%')}</small></td>
      <td><strong>${liveCampaignNumber(liveCampaignMetric(r,'received'))}</strong><small>${esc(c.trend?.reference_label||'')}</small></td>
      <td>${trend===null||trend===undefined||!Number.isFinite(Number(trend))?'<span class="live-na">—</span>':`<strong>${Number(trend)>=0?'+':''}${Number(trend).toLocaleString('fr-FR',{maximumFractionDigits:1})} %</strong>`}</td>
      <td>${qv.top_share_percent===null||qv.top_share_percent===undefined?'<span class="live-na">—</span>':`<strong>${Number(qv.top_share_percent).toLocaleString('fr-FR',{maximumFractionDigits:1})} %</strong><small>${esc(qv.top_files?.[0]?.file_label||'')}</small>`}</td>
      <td><button type="button" class="button ghost live-campaign-open" data-campaign-id="${esc(c.campaign_id)}">${selected?'Fermer':'Détails'}</button></td></tr>${selected?`<tr class="live-campaign-detail-row"><td colspan="11">${liveCampaignDetail(c,payload.windows)}</td></tr>`:''}`;
  }).join('')||'<tr><td colspan="11" class="empty">Aucune campagne ne correspond aux filtres.</td></tr>'}</tbody></table></div><p class="live-scope-limit">${rows.length} campagne(s) affichée(s) sur ${all.length} référencée(s).</p>`;
}
async function liveCampaignsView(){
  liveStopTimers();const generation=++liveViewGeneration,user=currentUser;
  activate('live-campaigns');setHead('Campagnes à surveiller','Qualité opérationnelle par campagne : maintenant, 15 min, aujourd’hui et référence');
  app.innerHTML='<div class="loading">Construction de la vue campagnes…</div>';
  const active=()=>generation===liveViewGeneration&&location.hash==='#live-campaigns'&&user===currentUser&&canRead('collection');
  const load=async()=>{
    try{
      const d=await api('/api/live/campaigns?include_inactive=1');if(!active())return;
      const services=[...new Set((d.campaigns||[]).flatMap(c=>c.services||[]))].sort((a,b)=>a.localeCompare(b,'fr'));
      const groups=[];const seen=new Set();(d.campaigns||[]).forEach(c=>(c.groups||[]).forEach(g=>{if(!seen.has(String(g.id))){seen.add(String(g.id));groups.push(g);}}));groups.sort((a,b)=>String(a.name||'').localeCompare(String(b.name||''),'fr'));
      const statuses=[...new Map((d.campaigns||[]).map(c=>[String(c.status?.level_key||''),c.status]).filter(x=>x[0])).entries()].map(x=>x[1]);
      const incidents=(d.campaigns||[]).reduce((n,c)=>n+Number(c.incident_count||0),0);
      app.innerHTML=`<section class="live-page live-campaigns-page">
        <div class="live-page-head"><div><h2>Campagnes à surveiller</h2><p>${esc(d.day||'')} · maintenant = Hermes Live · 15 min / aujourd'hui / référence = Stats.INBOUND importé.</p></div><div class="live-page-actions"><a class="button ghost" href="#live-supervision">Centre Qualité Live</a><a class="button ghost" href="#live-search">Recherche Live</a></div></div>
        <div class="live-kpis live-campaign-summary"><article><span>Campagnes référencées</span><strong>${Number(d.count||0)}</strong><small>configuration + activité observée</small></article><article><span>Incidents actifs</span><strong>${incidents}</strong><small>règles Qualité Live</small></article><article><span>Live maintenant</span><strong>${esc(d.windows?.live_now?.quality||'unavailable')}</strong><small>Hermes Live</small></article><article><span>Historique aujourd'hui</span><strong>${esc(d.windows?.today?.quality||'unavailable')}</strong><small>Stats.INBOUND</small></article><article><span>Référence</span><strong>${Number(d.windows?.reference?.days?.length||0)} j</strong><small>${esc(d.windows?.reference?.label||'')}</small></article></div>
        <section class="card panel live-campaign-filters"><div class="live-campaign-filter-grid"><label>Recherche<input id="live-campaign-q" type="search" value="${esc(liveCampaignsState.q)}" placeholder="Campagne, service, groupe…"></label><label>Service<select id="live-campaign-service"><option value="">Tous</option>${services.map(x=>`<option ${x===liveCampaignsState.service?'selected':''}>${esc(x)}</option>`).join('')}</select></label><label>Groupe<select id="live-campaign-group"><option value="">Tous</option>${groups.map(g=>`<option value="${esc(g.id)}" ${String(g.id)===String(liveCampaignsState.group)?'selected':''}>${esc(g.name||g.id)}</option>`).join('')}</select></label><label>Statut<select id="live-campaign-status"><option value="">Tous</option>${statuses.map(st=>`<option value="${esc(st.level_key)}" ${String(st.level_key)===String(liveCampaignsState.status)?'selected':''}>${esc(st.label||st.level_key)}</option>`).join('')}</select></label><label class="live-campaign-check"><input id="live-campaign-alerts" type="checkbox" ${liveCampaignsState.alertsOnly?'checked':''}> Alertes uniquement</label></div></section>
        <section class="card panel"><div id="live-campaign-table">${liveCampaignRowsHtml(d)}</div></section>
        <details class="card panel live-limitations"><summary>Sources et limites de la vue Campagnes</summary>${(d.limitations||[]).map(x=>`<p>${esc(x)}</p>`).join('')}<p>Plan SQL historique borné : ${d.query_plan?.independent_of_campaign_count?'indépendant du nombre de campagnes':'non confirmé'}.</p></details>
      </section>`;
      const loadDetail=async(id,force=false)=>{id=String(id||'');if(!id||liveCampaignsState.detailLoading[id])return;if(!force&&liveCampaignsState.detailById[id]&&Date.now()-Number(liveCampaignsState.detailLoadedAt[id]||0)<10000)return;liveCampaignsState.detailLoading[id]=true;liveCampaignsState.detailError[id]='';render();try{liveCampaignsState.detailById[id]=await api('/api/live/campaigns/'+encodeURIComponent(id));liveCampaignsState.detailLoadedAt[id]=Date.now();}catch(err){liveCampaignsState.detailError[id]=err.message||'Drill-down indisponible.';}finally{liveCampaignsState.detailLoading[id]=false;if(active())render();}};
      const render=()=>{const node=document.getElementById('live-campaign-table');if(node){node.innerHTML=liveCampaignRowsHtml(d);node.querySelectorAll('.live-campaign-open').forEach(btn=>btn.onclick=()=>{const id=String(btn.dataset.campaignId||'');if(String(liveCampaignsState.selected)===id){liveCampaignsState.selected='';liveCampaignsState.detailQueue='';liveCampaignsState.detailAgent='';render();return;}liveCampaignsState.selected=id;liveCampaignsState.detailQueue='';liveCampaignsState.detailAgent='';render();loadDetail(id);});node.querySelectorAll('.live-drill-queue').forEach(btn=>btn.onclick=()=>{liveCampaignsState.detailQueue=String(btn.dataset.fileId||'');liveCampaignsState.detailAgent='';render();});node.querySelectorAll('.live-drill-agent').forEach(btn=>btn.onclick=()=>{liveCampaignsState.detailAgent=String(btn.dataset.agentId||'');render();});}};
      const q=document.getElementById('live-campaign-q'),service=document.getElementById('live-campaign-service'),group=document.getElementById('live-campaign-group'),status=document.getElementById('live-campaign-status'),alerts=document.getElementById('live-campaign-alerts');
      q.oninput=()=>{liveCampaignsState.q=q.value;render();};service.onchange=()=>{liveCampaignsState.service=service.value;render();};group.onchange=()=>{liveCampaignsState.group=group.value;render();};status.onchange=()=>{liveCampaignsState.status=status.value;render();};alerts.onchange=()=>{liveCampaignsState.alertsOnly=alerts.checked;render();};
      render();if(liveCampaignsState.selected)loadDetail(liveCampaignsState.selected);liveSchedule(load,generation);
    }catch(e){if(active()){app.innerHTML=flash(e.message,'error');liveSchedule(load,generation);}}
  };
  await load();
}

async function liveSupervisionView(){
  liveStopTimers();
  const generation=++liveViewGeneration,user=currentUser;
  liveSupervisionState.scopeType=liveSupervisionState.scopeType||'CAMPAIGN';
  liveSupervisionState.scopeQuery=liveSupervisionState.scopeQuery||'';
  liveSupervisionState.agentQuery=liveSupervisionState.agentQuery||'';
  liveSupervisionState.agentPage=Number(liveSupervisionState.agentPage||0);
  liveSupervisionState.scopePage=Number(liveSupervisionState.scopePage||0);
  if(liveSupervisionState.group===undefined){const gp=groupScopePolicy();let saved='';try{saved=localStorage.getItem('nelyio.live.group')||'';}catch(_){ }const allowed=(gp.allowed_group_ids||[]).map(String);liveSupervisionState.group=String(saved&&(gp.all_groups||allowed.includes(String(saved)))?saved:(gp.default_group_id||''));}
  activate('live-supervision');
  setHead('Centre Qualité Live','Détecter, comprendre et investiguer la qualité opérationnelle en temps réel · Hermes + règles Nelyio');
  app.innerHTML='<div class="loading">Chargement du Centre Qualité Live…</div>';
  const active=()=>generation===liveViewGeneration&&location.hash==='#live-supervision'&&user===currentUser&&canOpenInterface('live_supervision');
  let latestPayload=null,rendered=false,requestSeq=0;

  const renderScope=()=>{
    if(!latestPayload)return;const center=latestPayload.quality?.center||{};
    const host=document.getElementById('live-scope-table');if(host)host.innerHTML=liveScopeRowsHtml(center,liveSupervisionState.scopeType,liveSupervisionState.scopeQuery,latestPayload.native_queue_metrics||{});
  };
  const renderAgents=()=>{
    if(!latestPayload)return;const roster=latestPayload.agent_roster||latestPayload.agents||[];
    const chips=document.getElementById('live-agent-state-chips');if(chips)chips.innerHTML=liveAgentStateChips(roster);
    const head=document.querySelector('#live-agent-table thead');if(head)head.innerHTML=liveAgentHeaderHtml();
    livePatchAgentRoster(roster);
    const pg=liveAgentPageData(roster),pager=document.getElementById('live-agent-pager');
    if(pager)pager.innerHTML=`<span>${pg.all.length} agent(s) · défilement vertical</span>`;
  };
  const bindControls=()=>{
    const groupSelect=document.getElementById('live-business-group');
    if(groupSelect)groupSelect.onchange=()=>{
      liveSupervisionState.group=groupSelect.value;try{localStorage.setItem('nelyio.live.group',liveSupervisionState.group);}catch(_){ }liveSupervisionState.certifiedQuality=null;liveSupervisionState.scopeQuality=null;
      if(liveViewTimer){clearTimeout(liveViewTimer);liveViewTimer=null;}load();
    };
    const tabs=document.getElementById('live-scope-tabs');if(tabs)tabs.onclick=e=>{const btn=e.target.closest('[data-live-scope-type]');if(!btn)return;liveSupervisionState.scopeType=btn.dataset.liveScopeType;liveSupervisionState.scopePage=0;renderScope();patchScopeTabs();};
    const scopeQuery=document.getElementById('live-scope-query');if(scopeQuery){scopeQuery.value=liveSupervisionState.scopeQuery;scopeQuery.oninput=()=>{liveSupervisionState.scopeQuery=scopeQuery.value;liveSupervisionState.scopePage=0;renderScope();};}
    const scopeReset=document.getElementById('live-scope-reset');if(scopeReset)scopeReset.onclick=()=>{liveSupervisionState.scopeQuery='';liveSupervisionState.scopePage=0;if(scopeQuery)scopeQuery.value='';rc29SortReset(`live-scopes-${String(liveSupervisionState.scopeType).toLowerCase()}`);renderScope();};
    const scopeHost=document.getElementById('live-scope-table');if(scopeHost)scopeHost.onclick=e=>{const pageBtn=e.target.closest('[data-live-scope-page]');if(pageBtn){liveSupervisionState.scopePage=Math.max(0,liveSupervisionState.scopePage+(pageBtn.dataset.liveScopePage==='next'?1:-1));renderScope();return;}const btn=e.target.closest('[data-rc29-sort]');if(!btn)return;rc29SortCycle(btn.dataset.rc29Table,btn.dataset.rc29Sort);liveSupervisionState.scopePage=0;renderScope();};
    const agentQuery=document.getElementById('live-agent-query');if(agentQuery){agentQuery.value=liveSupervisionState.agentQuery;agentQuery.oninput=()=>{liveSupervisionState.agentQuery=agentQuery.value;liveSupervisionState.agentPage=0;renderAgents();liveStartDurationTicker();};}
    const stateChips=document.getElementById('live-agent-state-chips');if(stateChips)stateChips.onclick=e=>{const btn=e.target.closest('[data-live-agent-state]');if(!btn)return;liveSupervisionState.agentState=btn.dataset.liveAgentState||'';renderAgents();liveStartDurationTicker();};
    const agentReset=document.getElementById('live-agent-reset');if(agentReset)agentReset.onclick=()=>{liveSupervisionState.agentQuery='';liveSupervisionState.agentPage=0;if(agentQuery)agentQuery.value='';rc29SortReset('live-agents');renderAgents();liveStartDurationTicker();};
    const agentTable=document.getElementById('live-agent-table');if(agentTable)agentTable.onclick=e=>{const btn=e.target.closest('[data-rc29-sort]');if(!btn)return;rc29SortCycle(btn.dataset.rc29Table,btn.dataset.rc29Sort);liveSupervisionState.agentPage=0;renderAgents();liveStartDurationTicker();};
    const agentPager=document.getElementById('live-agent-pager');if(agentPager)agentPager.onclick=e=>{const btn=e.target.closest('[data-live-agent-page]');if(!btn)return;liveSupervisionState.agentPage=Math.max(0,liveSupervisionState.agentPage+(btn.dataset.liveAgentPage==='next'?1:-1));renderAgents();liveStartDurationTicker();};
    const applyRail=()=>{const main=document.querySelector('.live-supervision-main'),btn=document.getElementById('live-rail-toggle');if(!main)return;main.dataset.railCollapsed=liveSupervisionState.railCollapsed?'1':'0';if(btn){btn.setAttribute('aria-expanded',liveSupervisionState.railCollapsed?'false':'true');btn.title=liveSupervisionState.railCollapsed?'Déplier le rail':'Replier le rail';btn.textContent=liveSupervisionState.railCollapsed?'›':'‹';}};
    const railToggle=document.getElementById('live-rail-toggle');if(railToggle)railToggle.onclick=()=>{liveSupervisionState.railCollapsed=!liveSupervisionState.railCollapsed;try{localStorage.setItem('nelyio.live.railCollapsed',liveSupervisionState.railCollapsed?'1':'0');}catch(_){ }applyRail();};applyRail();
    const applyLayout=()=>{const board=document.getElementById('live-ops-board');if(!board)return;const mode=['agents','split','scopes'].includes(liveSupervisionState.layout)?liveSupervisionState.layout:'agents';board.dataset.layout=mode;const picker=document.getElementById('live-layout-select');if(picker)picker.value=mode;};
    const layoutSelect=document.getElementById('live-layout-select');if(layoutSelect)layoutSelect.onchange=()=>{liveSupervisionState.layout=layoutSelect.value;try{sessionStorage.setItem('nelyio.live.layout',liveSupervisionState.layout);localStorage.setItem('nelyio.live.layout',liveSupervisionState.layout);}catch(_){ }applyLayout();};applyLayout();
    const wall=document.getElementById('live-wall-toggle');if(wall)wall.onclick=async()=>{const workspace=document.querySelector('.live-supervision-workstation');const entering=!document.body.classList.contains('live-wall-active');if(entering){document.body.classList.add('live-wall-active');wall.textContent='Quitter mur';try{if(workspace?.requestFullscreen&&!document.fullscreenElement)await workspace.requestFullscreen();}catch(_){ }}else{document.body.classList.remove('live-wall-active');wall.textContent='Mur d’écran';try{if(document.fullscreenElement)await document.exitFullscreen();}catch(_){ }}};
  };
  const openAlertTarget=card=>{if(!card)return;const scopeType=String(card.dataset.liveAlertScopeType||'').toUpperCase(),scopeKey=String(card.dataset.liveAlertScopeKey||''),scopeLabel=String(card.dataset.liveAlertScopeLabel||scopeKey),agent=String(card.dataset.liveAlertAgent||'');if(scopeType==='CAMPAIGN'){liveSupervisionState.scopeType='CAMPAIGN';liveSupervisionState.scopeQuery=scopeLabel||scopeKey;liveSupervisionState.layout='scopes';try{localStorage.setItem('nelyio.live.layout','scopes');sessionStorage.setItem('nelyio.live.layout','scopes');}catch(_){ }const board=document.getElementById('live-ops-board');if(board)board.dataset.layout='scopes';const picker=document.getElementById('live-layout-select');if(picker)picker.value='scopes';const q=document.getElementById('live-scope-query');if(q)q.value=liveSupervisionState.scopeQuery;patchScopeTabs();renderScope();document.querySelector('.live-scope-panel')?.scrollIntoView({block:'nearest'});return;}const targetAgent=scopeType==='AGENT'?scopeKey:agent;if(targetAgent){liveSupervisionState.agentQuery=targetAgent;liveSupervisionState.agentState='';liveSupervisionState.layout='agents';try{localStorage.setItem('nelyio.live.layout','agents');sessionStorage.setItem('nelyio.live.layout','agents');}catch(_){ }const board=document.getElementById('live-ops-board');if(board)board.dataset.layout='agents';const picker=document.getElementById('live-layout-select');if(picker)picker.value='agents';const q=document.getElementById('live-agent-query');if(q)q.value=targetAgent;renderAgents();requestAnimationFrame(()=>document.querySelector(`tr[data-live-agent-id="${CSS.escape(targetAgent)}"]`)?.scrollIntoView({block:'center'}));return;}if(['SERVICE','GROUP','QUEUE'].includes(scopeType)){liveSupervisionState.scopeType=scopeType;liveSupervisionState.scopeQuery=scopeLabel||scopeKey;liveSupervisionState.layout='scopes';const board=document.getElementById('live-ops-board');if(board)board.dataset.layout='scopes';const picker=document.getElementById('live-layout-select');if(picker)picker.value='scopes';patchScopeTabs();renderScope();}};
  const patchScopeTabs=()=>{
    if(!latestPayload)return;const center=latestPayload.quality?.center||{},counts=center.scope_counts||{},host=document.getElementById('live-scope-tabs');if(!host)return;
    host.innerHTML=['SERVICE','GROUP','CAMPAIGN','QUEUE'].map(t=>{const c=counts[t]||{};return `<button type="button" class="${liveSupervisionState.scopeType===t?'active':''}" data-live-scope-type="${t}">${esc(({SERVICE:'Services',GROUP:'Groupes',CAMPAIGN:'Campagnes',QUEUE:'Files'})[t])}<small>${Number(c.with_incident||0)} alerte(s) · ${Number(c.total||0)} référencé(s)</small></button>`;}).join('');
  };
  const shell=d=>{
    const accessScope=d.access_scope||{};
    return `<section class="live-page live-quality-center live-supervision-workstation live-supervision-simple">
      <div class="live-cockpit-toolbar">
        <div class="live-cockpit-left"><span class="live-build-marker" title="Révision runtime servie">RC29.4 · Live Native R10</span><div id="live-health-dynamic"></div><label class="live-group-filter live-group-filter-inline"><span>Groupe</span><select id="live-business-group" ${accessScope.locked?'disabled':''}>${accessScope.mode==='ALL'?`<option value="" ${!liveSupervisionState.group?'selected':''}>Tous les groupes</option>`:''}${(accessScope.groups||[]).map(g=>`<option value="${esc(g.id)}" ${String(g.id)===String(liveSupervisionState.group)?'selected':''}>${esc(g.service_name?`${g.service_name} · ${g.name}`:g.name)}</option>`).join('')}</select></label><label class="live-layout-picker live-layout-picker-inline"><span>Vue</span><select id="live-layout-select"><option value="agents">Agents</option><option value="scopes">Campagnes / périmètres</option><option value="split">Double vue</option></select></label></div>
        <div class="live-cockpit-actions"><button type="button" class="button ghost" id="live-wall-toggle">Mur d’écran</button><a class="button ghost" href="#live-search">Recherche</a><details class="live-tools-menu"><summary class="button ghost">Plus</summary><div class="live-tools-menu-pop">${canOpenInterface('quality_pilotage')?'<a class="button ghost" href="#quality-pilotage">Analyse qualité</a>':''}${canOpenInterface('live_quality_admin')?'<a class="button ghost" href="#live-quality-admin">Règles / alertes</a>':''}</div></details></div>
      </div>
      <div id="live-warning-wrap"></div>
      <div class="live-supervision-main">
        <aside class="live-supervision-rail"><button type="button" id="live-rail-toggle" class="live-rail-toggle" aria-label="Replier ou déplier le rail Qualité" aria-expanded="true">‹</button><section id="live-quality-hero" class="live-quality-hero live-quality-status-compact"></section><div id="live-kpis-wrap" class="live-kpis live-quality-kpis live-kpis-rail"></div><div id="live-persistence-note" class="live-persistence-note"></div></aside>
        <div id="live-ops-board" class="live-ops-board">
          <section class="card panel live-agent-panel live-agent-roster-panel"><div class="panel-head"><div><h2>Agents</h2><p id="live-agent-summary" class="live-panel-count"></p></div><div class="live-scope-filter rc29-filter-actions"><input id="live-agent-query" type="search" value="${esc(liveSupervisionState.agentQuery)}" placeholder="Rechercher agent, état, campagne…"><button type="button" class="button ghost small" id="live-agent-reset">×</button></div></div><div id="live-agent-state-chips" class="live-agent-state-chips" aria-label="Filtres rapides par état"></div><div class="table-wrap live-monitor-scroll"><table id="live-agent-table" class="live-agent-table live-agent-ops-table rc29-sort-table"><thead>${liveAgentHeaderHtml()}</thead><tbody id="live-agent-roster-body"></tbody></table></div><div id="live-agent-pager" class="live-compact-pager"></div></section>
          <section class="card panel live-scope-panel"><div class="panel-head"><div><h2>Campagnes / périmètres</h2></div><div class="live-scope-filter rc29-filter-actions"><input id="live-scope-query" type="search" value="${esc(liveSupervisionState.scopeQuery)}" placeholder="Rechercher…"><button type="button" class="button ghost small" id="live-scope-reset">×</button></div></div><div id="live-scope-tabs" class="live-scope-tabs"></div><div id="live-scope-table" class="live-monitor-scope"></div></section>
        </div>
      </div>
    </section>`;
  };
  const patch=d=>{
    latestPayload=d;const h=d.health||{},k=d.kpi||{},rows=d.agents||[],rosterRows=d.agent_roster||d.agents||[],rosterCounts=d.roster_counts||{},quality=d.quality||{},center=quality.center||{};liveSupervisionState.agentSignals=center.agent_signals||{};
    const status=center.status||quality.operational_status||{},dataQuality=center.data_quality||quality.data_quality||{},engine=center.engine||{},gm=center.global_metrics||{},native=center.global_native_calls||{},attention=center.attention||[];
    if(!rendered){app.innerHTML=shell(d);rendered=true;bindControls();}
    const hermesAge=h.last_response_age===null||h.last_response_age===undefined?'Aucune donnée':`il y a ${Math.round(Number(h.last_response_age))} s`;const health=document.getElementById('live-health-dynamic');if(health)health.innerHTML=`${liveHealthBadge(h)}<p><strong>Hermes</strong> ${esc(hermesAge)} <span>· ${esc(h.connection_state||'—')}</span></p>`;
    const hero=document.getElementById('live-quality-hero');if(hero){const statusCls=liveCenterEnsureColor(status.color||'#667085'),dqCls=liveCenterEnsureColor(dataQuality.color||'#667085'),lastOperational=center.last_operational_status||{},statusOverridden=String(status.kind||'')!=='operational'&&lastOperational.label;hero.className=`live-quality-hero live-quality-status-compact ${statusCls}`;hero.innerHTML=`<div class="live-compact-status"><span>Qualité</span><strong>${esc(status.label||'INDÉTERMINÉ')}</strong></div><div class="live-compact-fact"><span>Alertes</span><strong>${Number(center.active_incident_count||0)}</strong></div><div class="live-compact-fact live-hermes-freshness"><span>Hermes</span><strong>${esc(hermesAge)}</strong></div><div class="live-compact-fact ${dqCls}"><span>Données</span><strong>${esc(dataQuality.label||'—')}</strong></div>`;}
    const warn=document.getElementById('live-warning-wrap');if(warn)warn.innerHTML=!h.fresh?`<div class="live-warning"><strong>${esc(h.label||'Live non actualisé')}</strong> — les états sont gelés et Nelyio ne transforme pas une absence de donnée en valeur normale.</div>`:'';
    const disconnected=k.disconnected===null||k.disconnected===undefined?'—':Number(k.disconnected).toLocaleString('fr-FR');const metricNumber=m=>m?.value===null||m?.value===undefined?0:Number(m.value||0);const pauseNow=metricNumber(gm.agents_pause),wrapNow=metricNumber(gm.agents_wrap),connectedNow=Number(k.connected||0),availableNow=Number(k.available||0),callNow=Number(k.in_call||0),otherNow=Math.max(0,connectedNow-availableNow-callNow-pauseNow-wrapNow);const connectedDetail=`${availableNow} dispo · ${callNow} appel · ${pauseNow} pause · ${wrapNow} post${otherNow?` · ${otherNow} autre(s)`:''}`;const kpis=document.getElementById('live-kpis-wrap');if(kpis)kpis.innerHTML=`<article><span>Connectés</span><strong>${connectedNow}</strong><small>${esc(connectedDetail)}</small></article><article><span>Disponibles</span><strong>${availableNow}</strong><small>${gm.available_percent?.value===null||gm.available_percent?.value===undefined?'ratio indisponible':Number(gm.available_percent.value).toLocaleString('fr-FR',{maximumFractionDigits:1})+' % des connectés'}</small></article><article><span>Déconnectés</span><strong>${disconnected}</strong><small>état offline réellement observé</small></article><article><span>En appel</span><strong>${callNow}</strong><small>appel + HOLD</small></article><article class="live-kpi-daily"><span>Reçus</span>${liveNativeKpi(native,'received_today')}</article><article class="live-kpi-daily"><span>Traités</span>${liveNativeKpi(native,'handled_today')}</article><article class="live-kpi-daily"><span>Abandonnés</span>${liveNativeKpi(native,'abandoned_today')}</article><article class="live-kpi-daily"><span>QoS</span>${liveNativeKpi(native,'qos_today','%')}</article>`;const persistence=d.persistence||{},pnote=document.getElementById('live-persistence-note');if(pnote){const restored=Number(persistence.last_known_agents||0);pnote.innerHTML=`<strong>Données du jour enregistrées</strong><span>${Number(persistence.normalized_events||0).toLocaleString('fr-FR')} événements · ${Number(persistence.day_sessions||0)} session(s)</span>${restored?`<span>${restored} dernier(s) état(s) conservé(s) après reprise</span>`:''}`;}
    const liveMetricCards=[[gm.available_percent,'Disponibilité agents'],[gm.in_call_percent,'Part des agents en appel'],[gm.wrap_percent,'Part en post-appel'],[gm.pause_percent,'Part en pause'],[gm.max_wrap_seconds,'Post-appel le plus long'],[gm.max_pause_seconds,'Pause la plus longue']].filter(x=>x[0]?.value!==null&&x[0]?.value!==undefined).map(x=>liveMetricCard(x[0],x[1])).join('');const metricGrid=document.getElementById('live-quality-metric-grid');if(metricGrid)metricGrid.innerHTML=liveMetricCards||'<div class="live-empty-state"><strong>Aucune métrique Live exploitable</strong><p>La collecte doit fournir des états frais avant d’afficher les indicateurs.</p></div>';
    patchScopeTabs();renderScope();
    const summary=document.getElementById('live-agent-summary');if(summary){const restored=Number(rosterCounts.last_known||0);summary.textContent=`${Number(rosterCounts.observed??rows.length)}/${Number(rosterCounts.configured??rosterRows.length)} observés${restored?` · ${restored} dernier(s) état(s) conservé(s)`:''}`;}
    renderAgents();
    const counts=document.getElementById('live-signal-counts');if(counts)counts.innerHTML=(center.signal_counts||[]).map(x=>`<span class="${liveCenterEnsureColor(x.color)}"><i></i>${esc(x.label)} ${Number(x.count)}</span>`).join('');
    const list=document.getElementById('live-signal-list');if(list){list.innerHTML=attention.length?attention.slice(0,8).map(liveIncidentCard).join(''):'<div class="live-empty-state"><strong>Aucun incident Qualité Live actif</strong><p>Cela signifie seulement qu’aucune règle applicable n’est actuellement déclenchée sur les métriques disponibles.</p></div>';list.onclick=e=>{if(e.target.closest('a,button'))return;openAlertTarget(e.target.closest('[data-live-alert-target]'));};list.onkeydown=e=>{if(!['Enter',' '].includes(e.key)||e.target.closest('a,button'))return;const card=e.target.closest('[data-live-alert-target]');if(card){e.preventDefault();openAlertTarget(card);}};}
    const limitations=document.getElementById('live-limitations-body');if(limitations)limitations.innerHTML=`<p><strong>Appels en attente instantanés :</strong> alimentés par UpQuR quand les compteurs de files sont reçus par la collecte Hermes.</p>${(center.limitations||d.limitations||[]).map(x=>`<p>${esc(x)}</p>`).join('')}${(d.limitations||[]).filter(x=>!(center.limitations||[]).includes(x)).map(x=>`<p>${esc(x)}</p>`).join('')}<p><strong>RC29 :</strong> le refresh Hermes met à jour le Live sans reconstruire la page ; les KPI importés ont leur propre cadence.</p>`;
    const select=document.getElementById('live-business-group');if(select&&document.activeElement!==select)select.value=String(liveSupervisionState.group||'');
    liveStartDurationTicker();
  };
  const load=async()=>{
    const seq=++requestSeq,groupAtRequest=String(liveSupervisionState.group||'');
    try{
      const groupParam=groupAtRequest?`?group=${encodeURIComponent(groupAtRequest)}`:'';
      const d=await api('/api/live/supervision'+groupParam);if(!active()||seq!==requestSeq)return;
      const accessScope=d.access_scope||{};if(accessScope.selected_group_id!==undefined){liveSupervisionState.group=String(accessScope.selected_group_id||'');try{localStorage.setItem('nelyio.live.group',liveSupervisionState.group);}catch(_){ }}
      patch(d);
      liveRefreshScopeQuality(d.day||'',generation,active,liveSupervisionState.group||'',renderScope);
      liveSchedule(load,generation);
    }catch(e){if(active()&&seq===requestSeq){if(!rendered)app.innerHTML=flash(e.message,'error');else{const warn=document.getElementById('live-warning-wrap');if(warn)warn.innerHTML=flash(e.message,'error');}liveSchedule(load,generation);}}
  };
  await load();
}

function liveIncidentStatusLabel(status){
  return ({NOUVEAU:'NOUVEAU',VU:'VU',EN_INVESTIGATION:'EN INVESTIGATION',ACTION_EN_COURS:'ACTION EN COURS',RETABLI:'RÉTABLI',CLOTURE:'CLÔTURÉ'})[String(status||'')]||String(status||'INCONNU');
}
function liveIncidentTime(ts){
  const n=Number(ts);if(!Number.isFinite(n)||n<=0)return '—';
  try{return new Date(n*1000).toLocaleString('fr-FR');}catch(_){return '—';}
}
function liveIncidentEventLabel(type){
  return ({OUVERTURE:'Incident ouvert',TRANSITION_MANUELLE:'Statut modifié',ACTION_DEMARREE:'Action engagée',COMMENTAIRE:'Commentaire',RETOUR_NORMAL_AUTOMATIQUE:'Retour à la normale observé',CLOTURE_MANUELLE:'Incident clôturé'})[String(type||'')]||String(type||'Événement');
}
function liveIncidentMetricFmt(value,unit=''){
  if(value===null||value===undefined||!Number.isFinite(Number(value)))return 'Non disponible';
  if(unit==='s')return liveDuration(Number(value));
  if(unit==='%')return `${Number(value).toLocaleString('fr-FR',{maximumFractionDigits:1})} %`;
  return Number(value).toLocaleString('fr-FR',{maximumFractionDigits:2});
}
function liveIncidentHashState(){
  const raw=String(location.hash||''),qmark=raw.indexOf('?');if(qmark<0)return;
  const p=new URLSearchParams(raw.slice(qmark+1));
  if(p.has('mode')&&['history','stats'].includes(p.get('mode')))liveIncidentsState.mode=p.get('mode');
  if(p.has('from'))liveIncidentsState.from=p.get('from')||'';
  if(p.has('to'))liveIncidentsState.to=p.get('to')||'';
  if(p.has('page'))liveIncidentsState.page=Math.max(0,Number(p.get('page')||0)||0);
}
function liveIncidentAgentLabel(i){
  if(String(i.scope_type||'').toUpperCase()==='AGENT')return `<strong>${esc(i.agent_name||i.scope_label||i.scope_key||'—')}</strong><small>${esc(i.agent||i.scope_key||'')}</small>`;
  return `<strong>Collectif</strong><small>${esc(i.scope_type||'PÉRIMÈTRE')} · ${esc(i.scope_label||i.scope_key||'—')}</small>`;
}
function liveIncidentDetails(i){
  const reasons=(i.reasons||[]).filter(r=>r.usable&&r.passed);
  const detail=reasons.slice(0,4).map(r=>`<li>${liveReasonObserved(r)}</li>`).join('');
  return `<strong>${esc(i.rule_name||i.category_label||'Incident Qualité Live')}</strong>${detail?`<ul>${detail}</ul>`:'<small>Condition enregistrée sans détail métrique exploitable.</small>'}`;
}
function liveIncidentBarChart(title,items){
  const rows=(items||[]).filter(x=>Number(x.count||0)>0),max=Math.max(1,...rows.map(x=>Number(x.count||0)));
  return `<section class="card panel live-incident-chart"><div class="panel-head"><div><h2>${esc(title)}</h2><p>Nombre de signalements enregistrés sur la période sélectionnée.</p></div></div><div class="live-incident-bars">${rows.map(x=>`<div class="live-incident-bar"><span>${esc(x.label||x.day||x.key||'')}</span><div><i style="width:${Math.max(2,Math.round(100*Number(x.count||0)/max))}%"></i></div><b>${Number(x.count||0).toLocaleString('fr-FR')}</b></div>`).join('')||'<div class="empty">Aucun incident sur cette période.</div>'}</div></section>`;
}
function liveIncidentStatsTable(stats){
  const cats=stats.categories||[],rows=stats.agents||[];
  return `<section class="card panel"><div class="panel-head"><div><h2>Incidents par agent</h2><p>Les incidents collectifs restent séparés et ne sont pas attribués artificiellement à un agent.</p></div><span>${Number(stats.agent_incidents||0)} incident(s) agent</span></div><div class="table-wrap"><table class="live-incident-stats-table"><thead><tr><th>Agent</th><th>Total</th>${cats.map(c=>`<th>${esc(c.label)}</th>`).join('')}<th>Dernier incident</th></tr></thead><tbody>${rows.map(r=>`<tr><td><strong>${esc(r.name||r.agent)}</strong><small>${esc(r.agent)}</small></td><td><strong>${Number(r.total||0)}</strong></td>${cats.map(c=>`<td>${Number((r.counts||{})[c.key]||0)}</td>`).join('')}<td>${esc(liveIncidentTime(r.last_incident_at))}</td></tr>`).join('')||`<tr><td colspan="${3+cats.length}" class="empty">Aucun incident Agent sur la période.</td></tr>`}</tbody></table></div>${Number(stats.collective_incidents||0)?`<p class="collection-hint">${Number(stats.collective_incidents)} incident(s) collectif(s) Groupe/Campagne/File sont conservés dans l’historique mais exclus du tableau par agent.</p>`:''}</section>`;
}
async function liveIncidentsView(){
  liveStopTimers();liveIncidentHashState();const generation=++liveViewGeneration,user=currentUser;
  activate('live-incidents');setHead('Incidents / Stat Live','Historique des incidents Qualité Live conservé 90 jours · statistiques par agent et période.');
  app.innerHTML='<div class="loading">Chargement de l’historique des incidents…</div>';
  const active=()=>generation===liveViewGeneration&&String(location.hash).startsWith('#live-incidents')&&user===currentUser&&canRead('collection');
  const load=async()=>{
    try{
      const q=new URLSearchParams();if(liveIncidentsState.from)q.set('from',liveIncidentsState.from);if(liveIncidentsState.to)q.set('to',liveIncidentsState.to);q.set('active','0');q.set('limit','10000');
      const [history,stats]=await Promise.all([api('/api/live/incidents?'+q),api('/api/live/incident-stats?'+q)]);if(!active())return;
      liveIncidentsState.from=history.period?.from||stats.period?.from||liveIncidentsState.from;liveIncidentsState.to=history.period?.to||stats.period?.to||liveIncidentsState.to;
      const all=history.incidents||[],pageSize=liveIncidentsState.pageSize,pages=Math.max(1,Math.ceil(all.length/pageSize));if(liveIncidentsState.page>=pages)liveIncidentsState.page=pages-1;
      const visible=all.slice(liveIncidentsState.page*pageSize,(liveIncidentsState.page+1)*pageSize);
      app.innerHTML=`<section class="live-incidents-workspace live-incidents-history-only"><div class="live-incidents-toolbar"><div><span class="eyebrow">QUALITÉ LIVE</span><h2>Incidents / Stat Live</h2><p><strong>Historique 90 jours.</strong> Seuls les incidents Qualité Live sont conservés jusqu’à ${Number(history.retention_days||90)} jours. La capture Live opérationnelle reste limitée à la journée courante.</p></div><div class="live-incident-tabs"><button type="button" class="${liveIncidentsState.mode==='history'?'active':''}" data-incident-mode="history">Historique <b>${all.length}</b></button><button type="button" class="${liveIncidentsState.mode==='stats'?'active':''}" data-incident-mode="stats">Statistiques <b>${Number(stats.total||0)}</b></button></div></div>
        <form id="live-incident-period" class="live-incident-period"><label>Du<input type="date" name="from" value="${esc(liveIncidentsState.from)}"></label><label>Au<input type="date" name="to" value="${esc(liveIncidentsState.to)}"></label><button class="button" type="submit">Appliquer</button><span>Intervalle maximal : 90 jours</span></form>
        ${liveIncidentsState.mode==='history'?`<section class="card panel"><div class="panel-head"><div><h2>Historique des signalements</h2><p>Date/heure, agent ou périmètre, détail du déclenchement, niveau et durée.</p></div><span>${all.length.toLocaleString('fr-FR')} incident(s)</span></div><div class="table-wrap"><table class="live-incident-history-table"><thead><tr><th>Date / heure</th><th>Agent</th><th>Incident</th><th>Détails</th><th>Niveau</th><th>Statut</th><th>Durée</th></tr></thead><tbody>${visible.map(i=>`<tr><td>${esc(liveIncidentTime(i.triggered_at||i.first_seen))}</td><td>${liveIncidentAgentLabel(i)}</td><td><strong>${esc(i.category_label||'Autres')}</strong><small>${esc(i.rule_name||'')}</small></td><td>${liveIncidentDetails(i)}</td><td>${liveQualityStatus({label:i.level_label,color:i.color},true)}</td><td><span class="live-incident-status status-${esc(String(i.status||'').toLowerCase())}">${esc(i.status_label||liveIncidentStatusLabel(i.status))}</span></td><td>${esc(liveDuration(i.duration_seconds||0))}</td></tr>`).join('')||'<tr><td colspan="7" class="empty">Aucun incident sur cette période.</td></tr>'}</tbody></table></div><div class="sup-pager"><button class="button ghost" id="live-inc-prev" ${liveIncidentsState.page<=0?'disabled':''}>Précédent</button><span>Page ${liveIncidentsState.page+1} / ${pages}</span><button class="button ghost" id="live-inc-next" ${liveIncidentsState.page+1>=pages?'disabled':''}>Suivant</button></div></section>`:`<div class="live-incident-stat-summary"><article><span>Total incidents</span><strong>${Number(stats.total||0)}</strong></article><article><span>Incidents agents</span><strong>${Number(stats.agent_incidents||0)}</strong></article><article><span>Incidents collectifs</span><strong>${Number(stats.collective_incidents||0)}</strong></article><article><span>Agents concernés</span><strong>${Number((stats.agents||[]).length)}</strong></article></div>${liveIncidentStatsTable(stats)}<div class="live-incident-chart-grid">${liveIncidentBarChart('Distribution par type',stats.categories||[])}${liveIncidentBarChart('Distribution par jour',(stats.daily||[]).map(x=>({label:x.day,count:x.count})))}</div>`}
      </section>`;
      document.querySelectorAll('[data-incident-mode]').forEach(b=>b.onclick=()=>{liveIncidentsState.mode=b.dataset.incidentMode;liveIncidentsState.page=0;load();});
      const form=document.getElementById('live-incident-period');form.onsubmit=e=>{e.preventDefault();liveIncidentsState.from=form.elements.from.value;liveIncidentsState.to=form.elements.to.value;liveIncidentsState.page=0;load();};
      const prev=document.getElementById('live-inc-prev'),next=document.getElementById('live-inc-next');if(prev)prev.onclick=()=>{liveIncidentsState.page=Math.max(0,liveIncidentsState.page-1);load();};if(next)next.onclick=()=>{liveIncidentsState.page++;load();};
      liveSchedule(load,generation);
    }catch(e){if(active()){app.innerHTML=flash(e.message,'error');liveSchedule(load,generation);}}
  };
  await load();
}

function liveSearchHashState(){
  const raw=String(location.hash||'');const qmark=raw.indexOf('?');if(qmark<0)return;
  const p=new URLSearchParams(raw.slice(qmark+1));
  if(p.has('reference')){liveSearchState.reference=p.get('reference')||'';liveSearchState.q='';}
  if(p.has('q')){liveSearchState.q=p.get('q')||'';liveSearchState.reference='';}
  if(p.has('agent'))liveSearchState.agent=p.get('agent')||'';
  if(p.has('window')&&['in_progress','5m','15m','30m','1h','today'].includes(p.get('window')))liveSearchState.window=p.get('window');
  liveSearchState.page=0;
}
async function liveSearchView(){
  liveStopTimers();liveSearchHashState();
  const generation=++liveViewGeneration,user=currentUser;
  activate('live-search');setHead('Recherche d’appels Live','Retrouver une observation récente par ANI, agent, file, campagne ou référence Live');
  app.innerHTML='<div class="loading">Chargement des appels Live…</div>';
  const active=()=>generation===liveViewGeneration&&String(location.hash).startsWith('#live-search')&&user===currentUser&&canRead('calls');
  const load=async()=>{
    const s=liveSearchState,q=new URLSearchParams();
    for(const key of ['window','q','agent','reference'])if(s[key])q.set(key,s[key]);q.set('page',String(s.page||0));
    try{
      const d=await api('/api/live/search?'+q);if(!active())return;
      const rows=d.rows||[],page=Number(d.page||0),pageSize=Number(d.page_size||100),count=Number(d.count||0);s.page=page;
      app.innerHTML=`<section class="live-page live-search-page">
        <div class="live-page-head"><div>${liveHealthBadge(d.health||{})}<p>Recherche dans le spool Live du ${esc(d.day||'')} uniquement.</p></div><a class="button ghost" href="#live-supervision">Supervision Live</a></div>
        <form id="live-search-form" class="live-search-form">
          <label>Recherche<input name="q" type="search" autocomplete="off" value="${esc(s.q)}" placeholder="${canRead('ani')?'ANI, agent, file, campagne…':'Agent, file, campagne…'}"></label>
          <label>Fenêtre<select name="window"><option value="in_progress" ${s.window==='in_progress'?'selected':''}>En cours</option><option value="5m" ${s.window==='5m'?'selected':''}>5 dernières minutes</option><option value="15m" ${s.window==='15m'?'selected':''}>15 dernières minutes</option><option value="30m" ${s.window==='30m'?'selected':''}>30 dernières minutes</option><option value="1h" ${s.window==='1h'?'selected':''}>1 heure</option><option value="today" ${s.window==='today'?'selected':''}>Aujourd’hui</option></select></label>
          <label>Agent<select name="agent"><option value="">Tous</option>${(d.agents||[]).map(a=>`<option value="${esc(a.agent)}" ${String(a.agent)===String(s.agent)?'selected':''}>${esc(a.name||a.agent)} · ${esc(a.agent)}</option>`).join('')}</select></label>
          <label>Référence Live<input name="reference" value="${esc(s.reference)}" placeholder="ex. 1001-4"></label>
          <div class="live-search-actions"><button class="button">Rechercher</button><button type="button" class="button ghost" id="live-search-reset">Réinitialiser</button></div>
        </form>
        <div class="live-search-summary"><strong>${count.toLocaleString('fr-FR')}</strong> observation(s) · ${esc(d.reference_label||'Référence Live')}</div>
        <div class="table-wrap"><table class="live-search-table"><thead><tr><th>Heure</th><th>Référence Live</th><th>ANI</th><th>Agent</th><th>File / campagne</th><th>État</th><th>Suivi observé</th><th>Détail</th></tr></thead><tbody>${rows.map((r,i)=>`<tr>
          <td>${esc(r.start_text||'—')}<small>dernier ${esc(r.last_text||'—')}</small></td><td class="mono">${esc(r.reference||'—')}</td><td>${esc(livePhoneLabel(r))}</td>
          <td><strong>${esc(r.name||r.agent)}</strong><small>${esc(r.agent)}</small></td><td>${esc(r.line_name||r.line_id||'—')}<small>${esc(r.campaign_name||r.campaign||'')}</small></td>
          <td>${esc(liveStatusLabel(r.status))}<small>${esc(r.state||'')}</small></td><td>${liveDuration(r.observed_span_seconds)}${r.partial_start?'<small>début réel inconnu</small>':''}</td>
          <td><details class="live-call-inline"><summary>Chronologie</summary><p><strong>Call ID :</strong> non disponible dans ce flux.</p><p><strong>Attente / conversation :</strong> non certifiées.</p><ol>${(r.timeline||[]).map(t=>`<li><span>${esc(t.stamp_text||'')}</span> ${esc(t.state||'')} <small>${esc(t.phase||'')}</small></li>`).join('')||'<li>Aucun échantillon détaillé.</li>'}</ol>${r.timeline_trimmed?`<p>${Number(r.timeline_trimmed)} échantillon(s) intermédiaire(s) restent dans les événements bruts.</p>`:''}</details></td></tr>`).join('')||'<tr><td colspan="8" class="empty">Aucune observation dans cette fenêtre.</td></tr>'}</tbody></table></div>
        <div class="sup-pager"><button class="button ghost" id="live-search-prev" ${page<=0?'disabled':''}>Précédent</button><span>${count?`${page*pageSize+1}–${Math.min(count,(page+1)*pageSize)} sur ${count}`:'0 résultat'}</span><button class="button ghost" id="live-search-next" ${(page+1)*pageSize>=count?'disabled':''}>Suivant</button></div>
        <details class="card panel live-limitations"><summary>Ce que cette recherche ne prétend pas savoir</summary>${(d.limitations||[]).map(x=>`<p>${esc(x)}</p>`).join('')}</details>
      </section>`;
      const form=document.querySelector('#live-search-form');form.onsubmit=e=>{e.preventDefault();s.q=form.elements.q.value.trim();s.window=form.elements.window.value;s.agent=form.elements.agent.value;s.reference=form.elements.reference.value.trim();s.page=0;load();};
      document.querySelector('#live-search-reset').onclick=()=>{Object.assign(s,{window:'30m',q:'',agent:'',reference:'',page:0});load();};
      document.querySelector('#live-search-prev').onclick=()=>{s.page=Math.max(0,s.page-1);load();};document.querySelector('#live-search-next').onclick=()=>{s.page++;load();};
      liveSchedule(load,generation);
    }catch(e){if(active()){app.innerHTML=flash(e.message,'error');liveSchedule(load,generation);}}
  };
  await load();
}

window.addEventListener('hashchange',()=>{
  if(!String(location.hash).startsWith('#live-supervision')&&!String(location.hash).startsWith('#live-search')){
    liveViewGeneration++;liveStopTimers();
  }
});
