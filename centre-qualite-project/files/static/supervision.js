let supRequestSerial=0,supPending=false;
let supMode='live',supPage=0,supTimer=null,supBusy=false,supData=null,supGeneration=0;
const supKinds={call:'Appel',ready:'Prêt / attente',pause:'Pause',offline:'Déconnecté',wrap:'Post-travail',arrival:'Arrivée',departure:'Départ final',other:'Autre'};
const supDuration=n=>{n=Math.max(0,Math.floor(n||0));return `${Math.floor(n/3600)}h ${String(Math.floor(n/60)%60).padStart(2,'0')}m ${String(n%60).padStart(2,'0')}s`;};
async function supervisionView(){
  clearTimeout(supTimer);supGeneration++;supPage=0;
  activate('supervision');setHead('Supervision Nelyio','Direct provisoire · Historique de référence SIMPLIFY2 · Suivi helpdesk');
  const cfg=await api('/api/supervision/view?mode=live&page=0');
  if(location.hash!=='#supervision')return;
  app.innerHTML=`<section class="sup-hero"><div><span class="sup-eyebrow">CENTRE DE SUPERVISION</span><h2>Comprendre chaque interruption.</h2><p>La capture aide à intervenir. L’export de fin de journée fait référence pour les durées.</p></div><div class="sup-clock" id="sup-clock"></div></section>
  <div class="sup-toolbar"><div class="sup-tabs" role="tablist" aria-label="Vue de supervision">${[['live','Direct'],['history','Historique'],['anomalies','Anomalies']].map(([k,v])=>`<button class="button ghost" role="tab" data-sup-mode="${k}">${v}</button>`).join('')}</div><button class="button ghost" id="sup-refresh">Actualiser</button></div>
  <section class="card sup-filters"><label id="sup-day-label">Du<input id="sup-day" type="date" value="${esc(cfg.day)}"></label><label id="sup-end-label">Au<input id="sup-end" type="date" value="${esc(cfg.day)}"></label><label>Agent<input id="sup-agent" placeholder="Nom ou identifiant"></label><label>État<select id="sup-kind"><option value="">Tous les états</option>${Object.entries(supKinds).map(([k,v])=>`<option value="${k}">${v}</option>`).join('')}</select></label><label id="sup-source-label">Source historique<select id="sup-source"><option value="reference">Référence (export prioritaire)</option><option value="capture">Observations de capture</option></select></label></section>
  <div id="sup-message" role="status"></div><div id="sup-health"></div><div id="sup-summary"></div><section id="sup-charts" aria-label="Graphiques de supervision"></section>
  <section class="card panel"><div class="panel-head"><div><h2 id="sup-heading">Activités</h2><p id="sup-provenance"></p></div><span id="sup-count"></span></div><div class="table-wrap"><table class="sup-table"><thead><tr><th>Agent</th><th>État / campagne</th><th>Début / fin</th><th>Durée</th><th>Qualification</th><th>Helpdesk</th></tr></thead><tbody id="sup-rows"></tbody></table></div><div class="sup-pager"><button class="button ghost" id="sup-prev">Précédent</button><span id="sup-page"></span><button class="button ghost" id="sup-next">Suivant</button></div></section>
  ${canWrite('support')?`<details class="card panel sup-settings"><summary>Import de fin de journée & configuration</summary><p>Importer un export complet de la journée. Il remplace la référence de cette journée dans les calculs, en conservant les anciens imports et les observations.</p><form id="sup-import" class="sup-import"><label>Export SIMPLIFY2<input type="file" id="sup-file" accept=".zip,.csv" multiple required><small class="sub">Vous pouvez sélectionner plusieurs exports ZIP/CSV en une seule fois.</small></label><label>Fuseau horaire des dates ActionDate<select id="sup-offset" required><option value="">À confirmer avant import</option><option value="120">UTC+02 — France en été</option><option value="60">UTC+01 — Tunisie / France en hiver</option><option value="0">UTC — temps universel</option></select></label><button class="button">Importer la journée</button></form><div id="sup-import-result" role="status"></div><div id="sup-imports"></div><hr><form id="sup-config" class="sup-config"></form><details><summary>Connecter la capture en direct</summary><p>Sur le PC de capture, lancer la version NELYIO de la capture puis le relais fourni. La clé ci-dessous autorise seulement l’envoi d’observations.</p><label>Clé de connexion<input id="sup-key" type="password" readonly></label><button class="button ghost" id="sup-copy-key" type="button">Copier la clé</button></details></details>`:''}
  <dialog id="sup-dialog"><form id="sup-note-form"><h2>Suivi helpdesk</h2><p id="sup-note-agent"></p><label>Statut<select id="sup-note-status"><option>À vérifier</option><option>En cours</option><option>Résolu</option><option>Comportement normal</option></select></label><label>Commentaire<textarea id="sup-note-text" rows="4" maxlength="4000" required placeholder="Constat, action effectuée, résultat…"></textarea></label><div id="sup-note-history"></div><p id="sup-note-error" role="status"></p><div class="sup-toolbar"><button type="button" class="button ghost" id="sup-note-cancel">Fermer</button><button class="button" id="sup-note-save">Enregistrer</button></div></form></dialog>`;
  $$('[data-sup-mode]').forEach(b=>b.onclick=()=>{supMode=b.dataset.supMode;supPage=0;supLoad();});
  ['#sup-day','#sup-end','#sup-kind','#sup-source'].forEach(id=>$(id).onchange=()=>{supPage=0;supLoad();});
  let debounce;$('#sup-agent').oninput=()=>{clearTimeout(debounce);debounce=setTimeout(()=>{supPage=0;supLoad();},300);};
  $('#sup-refresh').onclick=()=>supLoad();$('#sup-prev').onclick=()=>{supPage=Math.max(0,supPage-1);supLoad();};$('#sup-next').onclick=()=>{supPage++;supLoad();};
  $('#sup-note-cancel').onclick=()=>$('#sup-dialog').close();
  if(canWrite('support'))await supSetup();
  supRender(cfg);
  if(supMode==='live')supTimer=setTimeout(supLoad,5000);
}
function supRender(d){
    supData=d;
    $$('[data-sup-mode]').forEach(b=>{b.classList.toggle('sup-selected',b.dataset.supMode===supMode);b.setAttribute('aria-selected',b.dataset.supMode===supMode);});
    show($('#sup-day-label'),supMode!=='live');show($('#sup-end-label'),supMode!=='live');show($('#sup-source-label'),supMode!=='live');
    $('#sup-clock').textContent=d.clock;$('#sup-message').innerHTML='';
    $('#sup-health').innerHTML=d.health.length?d.health.map(h=>`<div class="sup-health ${h.fresh?'sup-ok':'sup-warn'}"><strong>${h.fresh?'Capture active':'Capture non confirmée'} · ${esc(h.source)}</strong><span>Dernier signal Hermès : ${esc(h.heartbeat_text||'aucun — capture NELYIO requise')}${h.error?' · '+esc(h.error):''}</span></div>`).join(''):'<div class="sup-health sup-warn"><strong>Aucune capture connectée</strong><span>Connecter le relais pour voir les observations en direct. Les exports restent consultables.</span></div>';
    const st=d.summary;
    $('#sup-summary').innerHTML=`<div class="sup-metrics"><div><span>Agents affichés</span><strong>${st.agents}</strong></div><div><span>À examiner</span><strong>${st.anomalies}</strong></div><div><span>${supMode==='live'?'Pauses en cours':'Temps de pause'}</span><strong>${supDuration(st.durations.pause)}</strong></div><div><span>${supMode==='live'?'Déconnexions en cours':'Temps déconnecté observé'}</span><strong>${supDuration(st.durations.offline)}</strong></div></div>`;
    supRenderCharts(d);
    $('#sup-heading').textContent={live:'Derniers états observés',history:'Chronologie des activités',anomalies:'Événements à examiner'}[supMode];
    $('#sup-provenance').textContent=supMode==='live'?'Durées provisoires depuis la transition observée. Une première observation peut commencer après le début réel de l’état.':(supSourceLabel(d)+'. Référence export par jour disponible ; sinon capture provisoire limitée aux séquences confirmées.')+` Plage ${d.config.work_start}–${d.config.work_end}. Une absence de données ne prouve pas un arrêt.`;
    $('#sup-count').textContent=`${d.count} résultat(s)`;
    $('#sup-rows').innerHTML=d.rows.map((r,i)=>`<tr><td><strong>${esc(r.name||r.agent)}</strong><small class="sub">${esc(r.agent)}${r.collector?' · '+esc(r.collector):''}</small><a class="link" href="#inventory/${encodeURIComponent(r.agent)}">Rechercher le PC</a></td><td><span class="sup-state sup-${esc(r.kind)}">${esc(r.state)}</span><small class="sub">${esc(r.campaign||'')}</small></td><td>${esc(r.start_text)}<small class="sub">${supMode==='live'?'Dernier état connu':esc(r.end_text)}</small></td><td class="sup-duration">${r.fresh===false?'—':supDuration(r.duration)}${r.initial?'<small class="sub">Début réel inconnu</small>':''}</td><td>${r.anomaly?`<strong class="sup-alert">${esc(r.anomaly)}</strong>`:''}<small class="sub">${esc(r.quality)}</small></td><td><button class="button ghost" data-sup-note="${i}">${esc(r.notes[0]?.status||'Examiner')}</button>${r.notes.length?`<small class="sub">${r.notes.length} note(s)</small>`:''}</td></tr>`).join('')||`<tr><td colspan="6" class="empty">${supMode==='live'?'Aucun état reçu. Connectez la capture.':'Aucun événement pour ces filtres.'}</td></tr>`;
    $('#sup-page').textContent=`Page ${supPage+1} / ${Math.max(1,Math.ceil(d.count/100))}`;$('#sup-prev').disabled=supPage===0;$('#sup-next').disabled=(supPage+1)*100>=d.count;
    $$('[data-sup-note]').forEach(b=>b.onclick=()=>supNote(d.rows[Number(b.dataset.supNote)]));
    if($('#sup-imports'))$('#sup-imports').innerHTML='<h3>Derniers imports</h3>'+d.imports.map(x=>`<p><strong>${esc(x.name)}</strong> · ${x.rows_count} activités · ${esc(x.imported_at)} · UTC${x.offset_minutes>=0?'+':''}${x.offset_minutes/60}</p>`).join('');
}
async function supLoad(){
  clearTimeout(supTimer);if(location.hash!=='#supervision'||!currentUser)return;
  const requestSerial=++supRequestSerial;
  if(supBusy){supPending=true;return;}
  supBusy=true;supPending=false;const gen=supGeneration;
  try{
    const q=new URLSearchParams({mode:supMode,date_from:$('#sup-day').value,date_to:$('#sup-end').value,agent:$('#sup-agent').value,kind:$('#sup-kind').value,source:$('#sup-source').value,page:supPage});
    const d=await api('/api/supervision/view?'+q);if(location.hash!=='#supervision'||gen!==supGeneration||requestSerial!==supRequestSerial)return;supRender(d);
  }catch(e){if($('#sup-message'))$('#sup-message').innerHTML=flash(e.message,'error');}
  finally{supBusy=false;if(location.hash==='#supervision'&&currentUser){if(supPending){supPending=false;supTimer=setTimeout(supLoad,0);}else if(supMode==='live')supTimer=setTimeout(supLoad,5000);}}
}
function supNote(r){
  const edit=String(r.key||'').startsWith('call:')?canWrite('calls'):canWrite('support');$('#sup-note-agent').textContent=`${r.name||r.agent} · ${r.state} · ${r.start_text}`;
  $('#sup-note-text').value='';$('#sup-note-error').textContent='';$('#sup-note-status').value=r.notes[0]?.status||'À vérifier';
  if(!$('#sup-note-diagnosis'))$('#sup-note-history').insertAdjacentHTML('beforebegin',supportDiagnosisFields());
  $('#sup-note-diagnosis').value=r.notes[0]?.diagnosis||'À qualifier';$('#sup-note-cause').value=r.notes[0]?.cause||'Indéterminée';
  $('#sup-note-diagnosis').disabled=!edit;$('#sup-note-cause').disabled=!edit;
  $('#sup-note-history').innerHTML=r.notes.map(n=>`<article class="sup-note"><strong>${esc(n.status)} · ${esc(n.diagnosis||'À qualifier')} · ${esc(n.cause||'Indéterminée')} · ${esc(n.author)}</strong><small class="sub">${esc(n.stamp)}</small><p>${esc(n.comment)}</p></article>`).join('');
  $('#sup-note-save').disabled=!edit;$('#sup-note-text').disabled=!edit;$('#sup-note-status').disabled=!edit;
  $('#sup-note-form').onsubmit=async e=>{e.preventDefault();try{await api('/api/supervision/note',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({key:r.key,status:$('#sup-note-status').value,comment:$('#sup-note-text').value,diagnosis:$('#sup-note-diagnosis').value,cause:$('#sup-note-cause').value})});$('#sup-dialog').close();if(location.hash==='#support')await supportLoad();else supLoad();}catch(err){$('#sup-note-error').textContent=err.message;}};
  $('#sup-dialog').showModal();
}
async function supSetup(){
  const c=await api('/api/supervision/config');if(!$('#sup-config'))return;
  const displayInfo='<p class="sub"><strong>Affichage :</strong> Europe/Paris automatique (UTC+1 hiver / UTC+2 ete). Le fuseau source de chaque export reste enregistre separement.</p>';
  const fields=[['pause_seconds','Pause longue (secondes)'],['offline_seconds','Déconnexion prolongée (secondes)'],['ready_seconds','Attente prolongée (secondes)'],['wrap_seconds','Post-travail prolongé (secondes)'],['stale_seconds','Capture périmée après (secondes)'],['capture_offset','Ancienne capture : décalage UTC en minutes'],['work_start','Début de plage'],['work_end','Fin de plage']];
  $('#sup-config').innerHTML=displayInfo+'<h3>Règles de supervision</h3>'+fields.map(([k,label])=>`<label>${label}<input name="${k}" type="${k.startsWith('work_')?'time':'number'}" value="${esc(c[k])}" required></label>`).join('')+'<button class="button">Enregistrer les règles</button><span id="sup-config-result" role="status"></span>';
  $('#sup-key').value=c.bridge_key;$('#sup-copy-key').onclick=async()=>{try{await navigator.clipboard.writeText(c.bridge_key);$('#sup-copy-key').textContent='Clé copiée';}catch{$('#sup-key').type='text';$('#sup-key').select();}};
  $('#sup-config').onsubmit=async e=>{e.preventDefault();try{await api('/api/supervision/config',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(Object.fromEntries(new FormData(e.target)))});$('#sup-config-result').textContent='Règles enregistrées.';supLoad();}catch(err){$('#sup-config-result').textContent=err.message;}};
  $('#sup-import').onsubmit=async e=>{
    e.preventDefault();const files=[...$('#sup-file').files];if(!files.length)return;
    const button=e.target.querySelector('button'),host=$('#sup-import-result'),offset=$('#sup-offset').value;button.disabled=true;
    const results=[],errors=[];let cursor=0,done=0;
    const update=()=>{host.textContent=`Import multiple : ${done}/${files.length} terminé(s) · ${errors.length} erreur(s)`;};update();
    const worker=async()=>{while(true){const i=cursor++;if(i>=files.length)return;const f=files[i];try{
      const q=new URLSearchParams({filename:f.name,offset});
      const r=await importInBackground('/api/supervision/import?'+q,{method:'POST',headers:{'Content-Type':'application/octet-stream'},body:f},'#sup-import-result');
      results.push({file:f.name,result:r});
    }catch(err){errors.push({file:f.name,error:err.message});}finally{done++;update();}}};
    try{await Promise.all(Array.from({length:Math.min(2,files.length)},()=>worker()));
      const days=results.flatMap(x=>x.result.days||[]).filter(Boolean).sort();
      const quality=results.filter(x=>x.result.quality_only||x.result.accepted_scopes?.includes('agent_queues')).length;
      const activities=results.reduce((n,x)=>n+Number(x.result.rows||0),0),calls=results.reduce((n,x)=>n+Number(x.result.calls||0),0);
      host.innerHTML=`<strong>${results.length}/${files.length} fichier(s) importé(s).</strong> ${activities} activités · ${calls} appels${quality?` · ${quality} configuration(s) Qualité/Agents traitée(s)`:''}.${errors.length?`<br><span class="danger">Échecs : ${errors.map(x=>esc(x.file)+': '+esc(x.error)).join(' · ')}</span>`:''}`;
      if(days.length){$('#sup-day').value=days[0];$('#sup-end').value=days[days.length-1];supMode='history';supPage=0;}
      await supLoad();
    }finally{button.disabled=false;$('#sup-file').value='';}
  };
}

const supChartColors={call:'#17826b',ready:'#2976b9',pause:'#b77713',wrap:'#7956b4',offline:'#bd4545',other:'#6d8091',arrival:'#6d8091',departure:'#6d8091'};
function supBarChart(id,title,description,items,format,action=''){
  const width=760,left=220,right=130,row=39,height=Math.max(95,items.length*row+24),max=Math.max(1,...items.map(r=>r.value));
  const svg=items.length?`<svg class="sup-chart-svg" viewBox="0 0 ${width} ${height}" role="img" aria-labelledby="${id}-title ${id}-desc"><title id="${id}-title">${esc(title)}</title><desc id="${id}-desc">${esc(description)}. ${esc(items.map(r=>`${r.label} : ${format(r.value)}`).join('; '))}</desc>${items.map((r,i)=>{const y=12+i*row;return `<text x="${left-12}" y="${y+17}" text-anchor="end" class="sup-svg-label">${esc(r.label.length>28?r.label.slice(0,26)+'…':r.label)}</text><rect x="${left}" y="${y}" width="${width-left-right}" height="25" rx="5" fill="#edf2f6"/><rect x="${left}" y="${y}" width="${(width-left-right)*r.value/max}" height="25" rx="5" fill="${r.color||'#2976b9'}"><title>${esc(r.label)} : ${esc(format(r.value))}</title></rect><text x="${width-right+12}" y="${y+17}" class="sup-svg-value">${esc(format(r.value))}</text>`;}).join('')}</svg>`:'<p class="empty">Aucune donnée pour ces filtres.</p>';
  return `<article class="card panel sup-chart-card"><h3>${esc(title)}</h3><p class="sup-chart-description">${esc(description)}</p>${svg}<details class="sup-chart-data"><summary>Voir les valeurs${action?' et filtrer':''}</summary><table><thead><tr><th>Libellé</th><th>Valeur</th>${action?'<th>Action</th>':''}</tr></thead><tbody>${items.map(r=>`<tr><td>${esc(r.label)}</td><td>${esc(format(r.value))}</td>${action?`<td><button type="button" class="button ghost" ${action}="${esc(r.key)}">Filtrer</button></td>`:''}</tr>`).join('')}</tbody></table></details></article>`;
}
function supHourlyChart(items){
  const w=760,h=250,l=45,bottom=207,plot=165,max=Math.max(1,...items.map(x=>x.value));
  const step=(w-l-20)/Math.max(1,items.length),bar=Math.min(42,step*0.65);
  return `<article class="card panel sup-chart-card"><h3>Quand commencent les anomalies ?</h3><p class="sup-chart-description">Nombre d’événements à examiner par tranche horaire, selon leur début dans la plage affichée. Ce graphique ne mesure pas une durée d’arrêt.</p><svg class="sup-chart-svg" viewBox="0 0 ${w} ${h}" role="img" aria-labelledby="sup-hour-title"><title id="sup-hour-title">Début des anomalies par tranche horaire</title>${[0,0.5,1].map(f=>`<line x1="${l}" x2="${w-15}" y1="${bottom-plot*f}" y2="${bottom-plot*f}" stroke="#e3eaf0"/><text x="${l-8}" y="${bottom-plot*f+4}" text-anchor="end" class="sup-svg-label">${Math.round(max*f)}</text>`).join('')}${items.map((r,i)=>{const x=l+i*step+(step-bar)/2,hh=plot*r.value/max;return `<rect x="${x}" y="${bottom-hh}" width="${bar}" height="${hh}" rx="4" fill="#ba6b38"><title>${esc(r.label)}–${esc(r.end_label)} : ${r.value} anomalie(s)</title></rect><text x="${x+bar/2}" y="${bottom-hh-8}" text-anchor="middle" class="sup-svg-value">${r.value||''}</text><text x="${x+bar/2}" y="${bottom+20}" text-anchor="middle" class="sup-svg-label">${esc(r.label)}</text>`;}).join('')}</svg><details class="sup-chart-data"><summary>Voir les valeurs</summary><table><thead><tr><th>Tranche</th><th>Anomalies</th></tr></thead><tbody>${items.map(r=>`<tr><td>${esc(r.label)}–${esc(r.end_label)}</td><td>${r.value}</td></tr>`).join('')}</tbody></table></details></article>`;
}
function supRenderCharts(d){
  const c=d.charts;if(!c||!$('#sup-charts'))return;
  const scope=supMode==='live'?'Capture provisoire':supSourceLabel(d);
  const durationItems=c.durations.map(r=>({...r,label:supKinds[r.key],color:supChartColors[r.key]}));
  const agentItems=c.agents.map(r=>({...r,key:r.agent,color:'#b77713'}));
  $('#sup-charts').innerHTML=`<div class="sup-chart-header"><div><h2>La période en graphiques</h2><p>${esc(scope)} · ${c.total_rows} événement(s) pris en compte sur toutes les pages${supMode==='anomalies'?' · anomalies uniquement':''}.</p></div><button type="button" class="button ghost" id="sup-chart-export">Exporter les valeurs CSV</button></div><div class="sup-chart-grid">${supMode==='live'?supBarChart('sup-states','États actuellement confirmés',`${c.stale} état(s) ancien(s) exclus. Nombre d’observations par état, une observation par agent et source.`,c.states.map(r=>({...r,label:supKinds[r.key]||r.key,color:supChartColors[r.key]})),n=>String(n),'data-sup-filter-kind'):supBarChart('sup-time','Temps observé par activité','Durées cumulées des agents filtrés. Les chevauchements sont fusionnés dans chaque catégorie ; les catégories ne forment pas nécessairement un total exclusif.',durationItems,supDuration,'data-sup-filter-kind')}${supBarChart('sup-agents','Agents avec le plus d’événements à examiner','Les 10 premiers selon le nombre d’événements dépassant les seuils. Ce classement ne détermine ni une faute ni la cause d’un incident.',agentItems,n=>`${n} événement(s)`,'data-sup-filter-agent')}${supMode!=='live'?(d.date_from!==d.date_to?supTrendChart('sup-period','Événements à examiner par jour',c.hourly,'Débuts des événements dans les données de la sélection. Les jours sans données restent inconnus.'):supHourlyChart(c.hourly)):''}</div>`;
  $$('[data-sup-filter-agent]').forEach(b=>b.onclick=()=>{$('#sup-agent').value=b.dataset.supFilterAgent;supPage=0;supLoad();});
  $$('[data-sup-filter-kind]').forEach(b=>b.onclick=()=>{$('#sup-kind').value=b.dataset.supFilterKind;supPage=0;supLoad();});
  $('#sup-charts').insertAdjacentHTML('beforeend',supStatistics(c));
  $$('[data-sup-stat-agent]').forEach(b=>b.onclick=()=>{$('#sup-agent').value=b.dataset.supStatAgent;supPage=0;supLoad();});
  $('#sup-chart-export').onclick=()=>{
    const lines=[['Source',scope],['Période',supMode==='live'?d.clock.slice(0,10):d.date_from+' → '+d.date_to],['Vue',supMode],['Agent filtré',d.filters?.agent||''],['État filtré',d.filters?.kind||''],[],['Graphique','Libellé','Valeur','Unité']];
    if(supMode==='live')c.states.forEach(r=>lines.push(['États confirmés',supKinds[r.key]||r.key,r.value,'observations']));
    else {c.durations.forEach(r=>lines.push(['Temps par activité',supKinds[r.key],r.value,'secondes']));c.hourly.forEach(r=>lines.push(['Anomalies par tranche',r.label+'–'+r.end_label,r.value,'événements']));}
    c.agents.forEach(r=>lines.push(['Agents à examiner',r.agent+' '+r.label,r.value,'événements']));
    lines.push([],['Statistiques par agent','Identifiant','Nom','Activités','Anomalies','Appel (s)','Attente (s)','Pause (s)','Post-travail (s)','Déconnecté (s)','Temps couvert (s)']);
    c.agent_stats.forEach(r=>lines.push(['Agent',r.agent,r.name,r.activities,r.anomalies,r.call,r.ready,r.pause,r.wrap,r.offline,r.covered]));
    const safe=v=>{v=String(v??'');if(/^[=+@\-\t\r]/.test(v))v="'"+v;return '"'+v.replace(/"/g,'""')+'"';};
    const blob=new Blob(['\ufeff'+lines.map(r=>r.map(safe).join(';')).join('\r\n')],{type:'text/csv;charset=utf-8'});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=`Nelyio_graphiques_${d.date_from}_${d.date_to}.csv`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  };
}

function supStatistics(c){
  const s=c.stats,live=supMode==='live';
  const cards=live?[
    ['Agents avec un événement à examiner',String(s.flagged_agents)],
    ['États anciens exclus des durées',String(c.stale)],
  ]:[
    ['Agents dans la sélection',String(s.agents)],
    ['Agents avec une anomalie',String(s.flagged_agents)],
    ['Temps couvert, tous agents',supDuration(s.covered)],
    ['Séquences de pause mesurées',String(s.pause_count)],
    ['Pause moyenne',s.pause_average===null?'—':supDuration(s.pause_average)],
    ['Pause la plus longue',s.pause_max===null?'—':supDuration(s.pause_max)],
    ['Séquences déconnectées mesurées',String(s.offline_count)],
    ['Déconnexion moyenne',s.offline_average===null?'—':supDuration(s.offline_average)],
    ['Séquence d’appel moyenne',s.call_average===null?'—':supDuration(s.call_average)],
    ['Attente moyenne',s.ready_average===null?'—':supDuration(s.ready_average)],
    ['Post-travail moyen',s.wrap_average===null?'—':supDuration(s.wrap_average)],
    ['Déconnexion la plus longue',s.offline_max===null?'—':supDuration(s.offline_max)],
  ];
  return `<section class="sup-stat-section"><h2>Statistiques ${live?'du direct':'de la sélection'}</h2><p class="sup-chart-description">${live?'Photographie des derniers états : les durées sont celles des états en cours observés, pas les cumuls de la journée.':'Calcul sur toutes les pages, avec les filtres actifs. Le temps couvert fusionne les chevauchements par agent ; il peut dépasser 24 heures car il cumule plusieurs agents. Les moyennes portent sur les séquences de durée positive dans la plage affichée.'}</p><div class="sup-metrics">${cards.map(([label,value])=>`<div><span>${esc(label)}</span><strong>${esc(value)}</strong></div>`).join('')}</div><details class="card panel sup-stat-table"><summary>Tableau détaillé par agent · ${c.agent_stats.length} agent(s)</summary><div class="table-wrap"><table><thead><tr><th>Agent</th><th>${live?'États':'Activités'}</th><th>Anomalies</th><th>Appel</th><th>Attente</th><th>Pause</th><th>Post-travail</th><th>Déconnecté</th><th>Temps couvert</th></tr></thead><tbody>${c.agent_stats.map(r=>`<tr><td><button class="button ghost" data-sup-stat-agent="${esc(r.agent)}">${esc(r.name)}</button><small class="sub">${esc(r.agent)}</small></td><td>${r.activities}</td><td>${r.anomalies}</td><td>${supDuration(r.call)}</td><td>${supDuration(r.ready)}</td><td>${supDuration(r.pause)}</td><td>${supDuration(r.wrap)}</td><td>${supDuration(r.offline)}</td><td>${supDuration(r.covered)}</td></tr>`).join('')||'<tr><td colspan="9">Aucune donnée pour cette sélection.</td></tr>'}</tbody></table></div></details></section>`;
}
