let suspiciousCallsGeneration=0;
const suspiciousCallsState={date_from:'',date_to:'',service:'',group:'',queue:'',agent:'',campaign:'',category:'all',page:0,sort:'',sort_dir:'default'};
try{const v=JSON.parse(sessionStorage.getItem('nelyio.rc29.suspicious.sort')||'null');if(v&&v.key&&['asc','desc'].includes(v.direction)){suspiciousCallsState.sort=v.key;suspiciousCallsState.sort_dir=v.direction;}}catch(_){}
function suspectSortHeader(label,key){const s=suspiciousCallsState,active=s.sort===key&&s.sort_dir!=='default';return `<th aria-sort="${active?(s.sort_dir==='asc'?'ascending':'descending'):'none'}"><button type="button" class="quality-sort-button" data-suspect-sort="${esc(key)}">${esc(label)}${active?(s.sort_dir==='asc'?' ↑':' ↓'):' ↕'}</button></th>`;}
function suspectCycleSort(key){const s=suspiciousCallsState;if(s.sort!==key||s.sort_dir==='default'){s.sort=key;s.sort_dir='asc';}else if(s.sort_dir==='asc')s.sort_dir='desc';else{s.sort='';s.sort_dir='default';}try{if(s.sort)sessionStorage.setItem('nelyio.rc29.suspicious.sort',JSON.stringify({key:s.sort,direction:s.sort_dir}));else sessionStorage.removeItem('nelyio.rc29.suspicious.sort');}catch(_){}s.page=0;suspiciousCallsView();}

let suspiciousCallsHashSeen='';
function suspiciousCallsHashState(){
  const raw=String(location.hash||'');if(!raw.startsWith('#suspicious-calls'))return;if(raw===suspiciousCallsHashSeen)return;suspiciousCallsHashSeen=raw;
  const qmark=raw.indexOf('?');if(qmark<0)return;const p=new URLSearchParams(raw.slice(qmark+1));
  for(const k of ['date_from','date_to','service','group','queue','agent','campaign','category'])if(p.has(k))suspiciousCallsState[k]=p.get(k)||'';
  suspiciousCallsState.page=0;
}

function suspectDuration(value){
  if(value===null||value===undefined||value==='')return '—';
  const n=Math.max(0,Math.round(Number(value)||0));
  if(n<60)return `${n} s`;
  if(n<3600)return `${Math.floor(n/60)}m ${String(n%60).padStart(2,'0')}s`;
  return `${Math.floor(n/3600)}h ${String(Math.floor((n%3600)/60)).padStart(2,'0')}m`;
}
function suspectOption(value,label,selected,disabled=false){
  return `<option value="${esc(value)}" ${String(value)===String(selected)?'selected':''} ${disabled?'disabled':''}>${esc(label)}</option>`;
}
function suspectGroupsForService(groups,service){
  if(!service)return groups;
  const key=String(service).trim().toLowerCase();
  return groups.filter(g=>String(g.service_name||'').trim().toLowerCase()===key);
}
function suspectReasonBadge(reason){
  let cls='neutral';
  if(reason.includes('< 10'))cls='danger';
  else if(reason.includes('50'))cls='danger';
  else if(reason.includes('30'))cls='warning';
  else if(reason.includes('contenu')||reason.includes('size'))cls='warning';
  else if(reason.includes('technique'))cls='technical';
  else if(reason.includes('agent'))cls='info';
  return `<span class="suspect-badge ${cls}">${esc(reason)}</span>`;
}

async function suspiciousCallsView(){
  suspiciousCallsHashState();
  const s=suspiciousCallsState,generation=++suspiciousCallsGeneration,user=currentUser;
  activate('suspicious-calls');
  setHead('Appels suspects','Appels individuels à vérifier · faits séparés des hypothèses');
  app.innerHTML='<div class="loading">Chargement…</div>';
  const active=()=>generation===suspiciousCallsGeneration&&String(location.hash).startsWith('#suspicious-calls')&&user===currentUser&&canRead('quality');
  try{
    const query=new URLSearchParams();
    for(const k of ['date_from','date_to','service','group','queue','agent','campaign','category'])if(s[k])query.set(k,s[k]);
    query.set('page',String(s.page||0));if(s.sort&&s.sort_dir!=='default'){query.set('sort',s.sort);query.set('sort_dir',s.sort_dir);}
    const d=await api('/api/quality/suspicious-calls?'+query);
    if(!active())return;
    s.date_from=d.date_from||s.date_from;s.date_to=d.date_to||s.date_to;
    s.category=d.category||s.category;s.service=d.service||s.service;s.group=d.group||s.group;
    const groups=(d.groups||[]).filter(g=>String(g.id)!=='unassigned');
    const scopedGroups=suspectGroupsForService(groups,s.service);
    const rows=d.rows||[];
    const pageSize=Number(d.page_size||100),count=Number(d.count||0),page=Number(d.page||0);
    s.page=page;
    const first=count?page*pageSize+1:0,last=Math.min(count,(page+1)*pageSize);
    const categories=[
      ['all','Tous les appels à examiner'],['short','Appels < 10 s'],['long_suspect','Suspects > 10 s'],
      ['hold30','Mise en attente ≥ 30 %'],['hold50','Mise en attente ≥ 50 %'],
      ['low_content','Contenu faible / size anormal'],['end_agent','Fin par agent'],
      ['end_caller','Fin par appelant — non démontrable'],['technical','Indice technique']
    ];
    const coverageMissing=(d.coverage||[]).filter(x=>!x.available).length;
    app.innerHTML=`<section class="q-page suspect-page">
      <form id="suspect-filters" class="q-toolbar suspect-toolbar">
        <div class="q-main-filters">
          <label>Du<input name="date_from" type="date" required value="${esc(s.date_from)}"></label>
          <label>Au<input name="date_to" type="date" required value="${esc(s.date_to)}"></label>
          <label>Catégorie<select name="category">${categories.map(([v,l])=>suspectOption(v,l,s.category,(v==='end_caller'&&d.capabilities?.end_by_caller===false)||(v==='low_content'&&d.capabilities?.media_size===false))).join('')}</select></label>
          <label>Service<select name="service">${suspectOption('','Tous les services',s.service)}${(d.services||[]).map(x=>suspectOption(x,x,s.service)).join('')}</select></label>
          <label>Sous-groupe<select name="group">${suspectOption('','Tous les groupes',s.group)}${scopedGroups.map(g=>suspectOption(g.id,(g.service_name?g.service_name+' · ':'')+g.name,s.group)).join('')}</select></label>
          <label>File<select name="queue">${suspectOption('','Toutes les files',s.queue)}${(d.queues||[]).map(x=>suspectOption(x,x,s.queue)).join('')}</select></label>
          <label>Agent<select name="agent">${suspectOption('','Tous les agents',s.agent)}${(d.agents||[]).map(x=>suspectOption(x.agent,(x.name||x.agent)+' · '+x.agent,s.agent)).join('')}</select></label>
          <label>Campagne<select name="campaign">${suspectOption('','Toutes les campagnes',s.campaign)}${(d.campaigns||[]).map(x=>suspectOption(x,x,s.campaign)).join('')}</select></label>
        </div>
        <div class="q-actions"><button class="button">Appliquer</button><button class="button ghost" id="suspect-reset" type="button">Réinitialiser</button></div>
      </form>
      <div class="q-info suspect-summary"><span><b>${count.toLocaleString('fr-FR')}</b> appel(s) correspondant(s)</span><span>${first?`${first.toLocaleString('fr-FR')}–${last.toLocaleString('fr-FR')}`:'Aucun résultat'}</span><span>Source : ${esc(d.source||'ODCalls')}</span></div>
      ${(d.agent_summary||[]).length?`<section class="suspect-agent-summary"><div class="panel-head"><div><h2>Agents à vérifier</h2><p>Nombre d’appels correspondant aux critères sélectionnés. Ce n’est pas un classement de performance.</p></div></div><div class="suspect-agent-grid">${(d.agent_summary||[]).map(x=>`<button type="button" class="suspect-agent-card" data-suspect-agent="${esc(x.agent)}"><span>${esc(x.name||x.agent)}</span><small>${esc(x.agent)}</small><strong>${Number(x.calls||0).toLocaleString('fr-FR')}</strong><em>appel(s) à vérifier</em></button>`).join('')}</div></section>`:''}
      ${coverageMissing?`<p class="notice">${coverageMissing} jour(s) de la période ne disposent pas de couverture appels : aucune conclusion n’est fabriquée pour ces jours.</p>`:''}
      <details class="qo-definitions suspect-rules"><summary>Fiabilité et règles d’interprétation</summary>
        <p><strong>Mise en attente</strong> : sous-action Hermes/Stats.AGENT confirmée par ODActions état <code>1003</code>. <code>SessionID</code> doit correspondre exactement au <code>CallID</code>. Le ratio utilise la durée cumulée de mise en attente / <code>CallDuration</code>.</p>
        <p><strong>Transferts / consultations / reroutages</strong> : identifiés par <code>ODRelations</code> et exclus des heuristiques durée/mise en attente/contenu faible, car leur structure est normale pour ce type de flux.</p>
        <p><strong>Contenu faible / size</strong> : taille WAV Hermes reliée par Indice, comparée uniquement à la durée réelle de conversation. Si Conversation = 0 s, le signal Size est ignoré. Le signal exige un seul WAV, aucune mise en attente et aucun transfert/consultation/reroutage. La référence initiale est configurable et vaut environ 8 000 octets/s.</p>
        <p><strong>Fin par agent</strong> : affichée uniquement quand <code>EndByAgent</code> le démontre. <strong>EndByAgent=0 n’est jamais transformé en “fin par appelant”.</strong></p>
        <p><strong>Indice technique</strong> : corrélation temporelle avec un événement technique du même agent ; ce n’est pas une preuve de panne réseau.</p>
        ${(d.limitations||[]).map(x=>`<p>${esc(x)}</p>`).join('')}
      </details>
      <div class="table-wrap"><table class="suspect-table"><thead><tr>
        ${suspectSortHeader('Date / heure','date')}${suspectSortHeader('Agent','agent')}<th>Service / groupe</th>${suspectSortHeader('File','queue')}${suspectSortHeader('Campagne','campaign')}${suspectSortHeader('ANI','ani')}${suspectSortHeader('Durée','duration')}${suspectSortHeader('Mise en attente','hold')}${suspectSortHeader('Fin','finish')}<th>Motifs / détail</th>
      </tr></thead><tbody>${rows.map(r=>{
        const service=(r.service_names||[]).join(', ')||'—';
        const groupNames=(r.groups||[]).map(g=>g.name).join(', ')||'—';
        const finish=r.finish_origin==='agent'?'Fin par agent':'Origine indéterminée';
        const ratio=r.hold_ratio===null||r.hold_ratio===undefined?'—':`${Number(r.hold_ratio).toLocaleString('fr-FR',{maximumFractionDigits:1})} %`;
        const reasons=(r.reasons||[]).map(suspectReasonBadge).join('')||'<span class="suspect-badge neutral">À examiner</span>';
        const governance=r.governance_excluded?`<span class="suspect-badge neutral">Exclu des KPI</span><small>${esc(r.governance_reason||'Policy / Déclaration')}</small>`:'';
        const signals=(r.technical_signals||[]);
        const callParams=new URLSearchParams({call_id:String(r.call_id||''),date_from:String(r.business_day||s.date_from||''),date_to:String(r.business_day||s.date_to||'')});
        const diagnosticParams=new URLSearchParams({date_from:String(r.business_day||s.date_from||''),date_to:String(r.business_day||s.date_to||''),agent:String(r.agent||''),call_id:String(r.call_id||'')});
        return `<tr>
          <td><strong>${esc(r.start_text||'—')}</strong><small>Call ID ${esc(r.call_id||'—')}</small></td>
          <td><strong>${esc(r.agent_name||r.agent||'—')}</strong><small>${esc(r.agent||'')}</small></td>
          <td>${esc(service)}<small>${esc(groupNames)}</small></td>
          <td>${esc(r.first_queue||'—')}<small>${r.last_queue&&String(r.last_queue)!==String(r.first_queue)?'Dernière : '+esc(r.last_queue):''}</small></td>
          <td>${esc(r.last_campaign||r.first_campaign||r.campaign||'—')}</td>
          <td>${esc(r.ani||'—')}${r.ani_masked?'<small>masqué selon vos droits</small>':''}</td>
          <td>${suspectDuration(r.call_duration??r.duration)}<small>Conversation ${suspectDuration(r.conversation)}</small>${r.recording_verified&&r.recording_size_bytes?`<small>WAV ${(Number(r.recording_size_bytes)/1024).toLocaleString('fr-FR',{maximumFractionDigits:2})} KB · ${r.media_density_kbps!==null&&r.media_density_kbps!==undefined?Number(r.media_density_kbps).toLocaleString('fr-FR',{maximumFractionDigits:2})+' kB/s':'—'}</small>`:''}</td>
          <td>${suspectDuration(r.hold_duration)}<small>${ratio}${r.hold_segments?` · ${Number(r.hold_segments)} segment(s)`:''}</small>${r.complex_flow?'<small>Flux transfert/consultation : heuristique exclue</small>':''}</td>
          <td>${esc(finish)}</td>
          <td><div class="suspect-reasons">${reasons}${governance}</div><details class="suspect-detail"><summary>Détail</summary><dl>
            <dt>Indice</dt><dd>${esc(r.indice||'—')}</dd><dt>Premier agent</dt><dd>${esc(r.first_agent||'—')}</dd><dt>Dernier agent</dt><dd>${esc(r.last_agent||'—')}</dd>
            <dt>Attente en file</dt><dd>${suspectDuration(r.wait_initial)}</dd><dt>Mise en attente cumulée</dt><dd>${suspectDuration(r.hold_duration)}</dd><dt>Segments de hold</dt><dd>${Number(r.hold_segments||0)}</dd>
            <dt>Taille WAV vérifiée</dt><dd>${r.recording_verified&&r.recording_size_bytes?(Number(r.recording_size_bytes)/1024).toLocaleString('fr-FR',{maximumFractionDigits:2})+' KB':'—'}</dd><dt>Densité média</dt><dd>${r.media_density_kbps!==null&&r.media_density_kbps!==undefined?Number(r.media_density_kbps).toLocaleString('fr-FR',{maximumFractionDigits:2})+' kB/s · '+Number(r.media_coverage_pct||0).toLocaleString('fr-FR',{maximumFractionDigits:1})+' % réf.':'—'}</dd>
            <dt>Flux complexe</dt><dd>${r.complex_flow?esc((r.complex_flow_labels||[]).join(', ')||'Transfert / consultation'):'Non'}</dd><dt>Dernier transfert</dt><dd>${esc(r.last_transfer||'—')}</dd><dt>Fin brute</dt><dd>${esc(r.end_reason||'—')}</dd>
          </dl><div class="suspect-links"><a class="button ghost small" href="#calls?${esc(callParams.toString())}">Ouvrir l’appel</a>${signals.length&&canRead('support')?`<a class="button ghost small" href="#support?${esc(diagnosticParams.toString())}">Diagnostic technique</a>`:''}</div>${signals.length?`<div class="suspect-signals"><strong>Indices techniques</strong>${signals.map(x=>`<p>${esc(x.category||x.source||'Signal')} · ${esc(x.detail||'')}</p>`).join('')}</div>`:'<p class="q-note">Aucun indice technique corrélé sur cette fenêtre.</p>'}</details></td>
        </tr>`;
      }).join('')||'<tr><td colspan="10">Aucun appel correspondant à cette sélection.</td></tr>'}</tbody></table></div>
      <div class="suspect-pagination"><button type="button" class="button ghost" id="suspect-prev" ${page<=0?'disabled':''}>Précédent</button><span>Page ${(page+1).toLocaleString('fr-FR')}</span><button type="button" class="button ghost" id="suspect-next" ${(page+1)*pageSize>=count?'disabled':''}>Suivant</button></div>
    </section>`;

    const form=document.getElementById('suspect-filters');
    form.onsubmit=e=>{e.preventDefault();const fd=new FormData(form);for(const k of ['date_from','date_to','service','group','queue','agent','campaign','category'])s[k]=String(fd.get(k)||'');s.page=0;suspiciousCallsView();};
    form.elements.service.onchange=()=>{s.service=String(form.elements.service.value||'');s.group='';s.queue='';s.agent='';s.campaign='';s.page=0;suspiciousCallsView();};
    form.elements.group.onchange=()=>{s.group=String(form.elements.group.value||'');s.queue='';s.agent='';s.campaign='';s.page=0;suspiciousCallsView();};
    document.querySelectorAll('[data-suspect-agent]').forEach(btn=>btn.onclick=()=>{s.agent=String(btn.dataset.suspectAgent||'');s.page=0;suspiciousCallsView();});
    document.querySelectorAll('[data-suspect-sort]').forEach(btn=>btn.onclick=()=>suspectCycleSort(btn.dataset.suspectSort));
    document.getElementById('suspect-reset').onclick=()=>{Object.assign(s,{date_from:'',date_to:'',service:'',group:'',queue:'',agent:'',campaign:'',category:'all',page:0,sort:'',sort_dir:'default'});try{sessionStorage.removeItem('nelyio.rc29.suspicious.sort');}catch(_){}suspiciousCallsView();};
    document.getElementById('suspect-prev').onclick=()=>{if(s.page>0){s.page--;suspiciousCallsView();}};
    document.getElementById('suspect-next').onclick=()=>{if((s.page+1)*pageSize<count){s.page++;suspiciousCallsView();}};
  }catch(err){if(active())app.innerHTML=`<div class="error">${esc(err.message||String(err))}</div>`;}
}
