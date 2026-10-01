let supportMode='technical',supportPage=0,supportCurrent=null,supportRequest=0;
const supportCategories={offline:'Déconnexion prolongée',disconnect_call:'Déconnexion pendant un appel',audio_signal:'Signal audio',capture_error:'Erreur de capture',capture_gap:'Absence de signal de capture',end_code:'Code de fin non nul',invalid_duration:'Durée incohérente'};
const supportDiagnoses=['À qualifier','Incident technique confirmé','Non technique'];
const supportStatuses=['À vérifier','En cours','Résolu','Comportement normal'];
function supportOptions(items,empty='Tous'){return `<option value="">${esc(empty)}</option>`+items.map(x=>`<option>${esc(x)}</option>`).join('');}
function supportDiagnosisFields(){return `<label>Qualification technique<select id="sup-note-diagnosis">${supportDiagnoses.map(x=>`<option>${esc(x)}</option>`).join('')}</select></label><label>Cause constatée<select id="sup-note-cause">${['Indéterminée','Réseau / VPN','Audio / casque','Hermès / téléphonie','Poste / système','Capture / collecte','Organisation'].map(x=>`<option>${esc(x)}</option>`).join('')}</select></label>`;}
function supportDialog(){return `<dialog id="sup-dialog"><form id="sup-note-form"><h2>Diagnostic du technicien</h2><p id="sup-note-agent"></p><label>Suivi<select id="sup-note-status">${supportStatuses.map(x=>`<option>${esc(x)}</option>`).join('')}</select></label><label>Constat et intervention<textarea id="sup-note-text" rows="4" maxlength="4000" required placeholder="Symptôme, vérifications, cause constatée, action et résultat…"></textarea></label><div id="sup-note-history"></div><p id="sup-note-error" role="status"></p><div class="sup-toolbar"><button type="button" class="button ghost" id="sup-note-cancel">Fermer</button><button class="button" id="sup-note-save">Enregistrer</button></div></form></dialog>`;}
function supportMetric(label,value,sub=''){return `<div><span>${esc(label)}</span><strong>${esc(value)}</strong>${sub?`<small>${esc(sub)}</small>`:''}</div>`;}
const supportPriorityStyleCache=new Set();
const supportTableSortState={};
try{const v=JSON.parse(sessionStorage.getItem('nelyio.rc29.support.sort')||'{}');if(v&&typeof v==='object')Object.assign(supportTableSortState,v);}catch(_){}
function supportPersistSort(){try{sessionStorage.setItem('nelyio.rc29.support.sort',JSON.stringify(supportTableSortState));}catch(_){}}
function supportPriorityVisual(value,items=[]){
  const v=String(value||'Priorité'),all=items||[],policy=all.find(x=>String(x.priority||'')===v)||{};
  const color=/^#[0-9a-f]{6}$/i.test(String(policy.color||''))?String(policy.color).toUpperCase():'#667085';
  const colorKey=color.slice(1).toLowerCase(),colorClass=`priority-color-${colorKey}`;
  const ordered=all.slice().sort((a,b)=>(Number(b.rank)||0)-(Number(a.rank)||0)),index=Math.max(0,ordered.findIndex(x=>String(x.priority||'')===v));
  const tones=['tone-critical','tone-high','tone-investigate','tone-watch','tone-normal','tone-neutral'];
  const tone=tones[Math.min(index,tones.length-1)];
  if(!supportPriorityStyleCache.has(colorClass)){
    const rule=`.support-priority.${colorClass}{color:${color};border-color:${color}66;background:${color}1F;box-shadow:inset 3px 0 0 ${color}}`;
    for(const sheet of Array.from(document.styleSheets||[])){
      try{
        if(sheet.href&&sheet.href.includes('/static/supervision.css')){
          sheet.insertRule(rule,sheet.cssRules.length);supportPriorityStyleCache.add(colorClass);break;
        }
      }catch(_e){}
    }
  }
  return {policy,color,colorClass,tone};
}
function supportPriorityBadge(value,reasons=[],items=[]){
  const v=String(value||'Priorité'),visual=supportPriorityVisual(v,items),title=(reasons||[]).join(' · ');
  return `<span class="support-priority ${visual.tone} ${visual.colorClass}"${title?` title="${esc(title)}"`:''}>${esc(v)}</span>`;
}
function supportSortHeader(label,key,type='number'){
  return `<th class="support-sortable-th" data-support-sort-key="${esc(key)}" data-sort-type="${esc(type)}" aria-sort="none"><button type="button" class="support-sort-button">${esc(label)}<span class="support-sort-indicator" aria-hidden="true">⇅</span></button></th>`;
}
function supportEnableTableSorting(root=document){
  if(!root)return;
  root.querySelectorAll('table[data-support-sortable]').forEach(table=>{
    const tableId=table.dataset.supportSortable||'support-table',headers=Array.from(table.querySelectorAll('thead th[data-support-sort-key]')),tbody=table.tBodies[0];
    if(!tbody)return;
    const applySort=(key,direction,remember=true)=>{
      const header=headers.find(h=>h.dataset.supportSortKey===key);if(!header)return;
      const column=header.cellIndex,type=header.dataset.sortType||'string',factor=direction==='asc'?1:-1;
      const rows=Array.from(tbody.rows).map((row,i)=>({row,base:Number(row.dataset.originalIndex??i)}));
      rows.sort((a,b)=>{
        const av=a.row.cells[column]?.dataset.sortValue??a.row.cells[column]?.textContent??'',bv=b.row.cells[column]?.dataset.sortValue??b.row.cells[column]?.textContent??'';
        let cmp=0;
        const am=av===null||av===undefined||String(av).trim()===''||String(av).trim()==='—',bm=bv===null||bv===undefined||String(bv).trim()===''||String(bv).trim()==='—';
        if(am||bm){if(am&&bm)return a.base-b.base;return am?1:-1;}
        if(type==='number'){
          const an=Number(av),bn=Number(bv);cmp=(Number.isFinite(an)?an:0)-(Number.isFinite(bn)?bn:0);
        }else cmp=String(av).localeCompare(String(bv),'fr',{sensitivity:'base',numeric:true});
        return cmp?cmp*factor:(a.base-b.base);
      });
      rows.forEach((entry,i)=>{tbody.appendChild(entry.row);const n=entry.row.querySelector('[data-support-row-number]');if(n)n.textContent=String(i+1);});
      headers.forEach(h=>{const active=h===header;h.setAttribute('aria-sort',active?(direction==='asc'?'ascending':'descending'):'none');const icon=h.querySelector('.support-sort-indicator');if(icon)icon.textContent=active?(direction==='asc'?'▲':'▼'):'⇅';});
      if(remember){supportTableSortState[tableId]={key,direction};supportPersistSort();}
    };
    headers.forEach(header=>{
      const button=header.querySelector('.support-sort-button');if(!button)return;
      button.onclick=()=>{const key=header.dataset.supportSortKey,current=supportTableSortState[tableId],same=current&&current.key===key;if(!same){applySort(key,'asc',true);return;}if(current.direction==='asc'){applySort(key,'desc',true);return;}delete supportTableSortState[tableId];supportPersistSort();const rows=Array.from(tbody.rows).map((row,i)=>({row,base:Number(row.dataset.originalIndex??i)})).sort((a,b)=>a.base-b.base);rows.forEach((entry,i)=>{tbody.appendChild(entry.row);const n=entry.row.querySelector('[data-support-row-number]');if(n)n.textContent=String(i+1);});headers.forEach(h=>{h.setAttribute('aria-sort','none');const icon=h.querySelector('.support-sort-indicator');if(icon)icon.textContent='⇅';});};
    });
    const saved=supportTableSortState[tableId];if(saved)applySort(saved.key,saved.direction,false);
  });
}
function supportPriorityPolicyText(items){
  const all=items||[],fallback=all.find(x=>x.is_fallback),list=all.filter(x=>x.enabled&&!x.is_fallback);
  if(!list.length)return `Aucune règle conditionnelle active${fallback?` : ${fallback.priority} est utilisé comme niveau de repli.`:'.'}`;
  const rendered=list.map(p=>{
    const parts=(p.conditions||[]).map(c=>`${c.label||c.metric} ${c.operator||'>'} ${c.value}${c.unit?` ${c.unit}`:''}`);
    return `${p.priority} [rang ${p.rank}] (${p.match_mode==='ALL'?'toutes':'au moins une'}) : ${parts.join(' · ')||'aucune condition'}`;
  });
  if(fallback)rendered.push(`Repli : ${fallback.priority}`);
  return rendered.join(' | ');
}
function supportSourceName(source){return source==='export'?'SIMPLIFY2':source==='capture'?'Capture':'Aucune donnée';}
function nelyioCommonFilterFields(info,prefix,{includeDates=true,includeAgentGroup=true,includeCallScope=true,includeExclusions=true}={}){
  const f=info.common_filters||info.filters||{},cfg=info.config||{},from=f.date_from||info.date_from||info.day||'',to=f.date_to||info.date_to||info.day||from;
  const tf=f.time_from||cfg.work_start||'08:00',tt=f.time_to||cfg.work_end||'19:00';
  const agent=f.agent||'',group=f.group||'',min=String(f.min_disconnect??0),scope=f.call_scope||'all',listId=`${prefix}-agent-list`;
  const agents=(info.available_agents||[]).map(r=>`<option value="${esc(r.agent)}">${esc(r.name||r.agent)}${(r.group_names&&r.group_names.length)?' · '+esc(r.group_names.join(' / ')):(r.group_name?' · '+esc(r.group_name):'')}${r.pc?' · '+esc(r.pc):''}</option>`).join('');
  const groups=(info.admin_groups||info.available_groups||[]).map(g=>`<option value="${esc(g.id)}" ${String(g.id)===String(group)?'selected':''}>${esc(g.name)}</option>`).join('');
  const dates=includeDates?`<label>Du<input type="date" name="date_from" value="${esc(from)}" required></label><label>Au<input type="date" name="date_to" value="${esc(to)}" required></label>`:'';
  const scopeFields=includeAgentGroup?`<label>Groupe<select name="group"><option value="">Tous les groupes</option>${groups}</select></label><label>Agent<input name="agent" list="${listId}" value="${esc(agent)}" placeholder="Identifiant, nom ou PC"><datalist id="${listId}">${agents}</datalist></label>`:'';
  const legacyMode=f.legacy_exclusion_mode||'compat';
  const exclusion=includeExclusions?(legacyMode==='compat'?`<details class="support-exclusion-slots legacy-exclusion-compat"><summary>Compatibilité anciennes exclusions horaires</summary><p>Ces cases sont conservées temporairement pour les anciens rapports/liens. Pour une règle durable et traçable, utilisez Administration → Policies Nelyio puis migrez cette plage.</p><div class="legacy-exclusion-fields"><label><input type="checkbox" name="exclude_12_13" value="1" ${f.exclude_12_13?'checked':''}>12h–13h</label><label><input type="checkbox" name="exclude_13_14" value="1" ${f.exclude_13_14?'checked':''}>13h–14h</label><label>De<input type="time" name="exclude_custom_from" value="${esc(f.exclude_custom_from||'')}"></label><label>À<input type="time" name="exclude_custom_to" value="${esc(f.exclude_custom_to||'')}"></label></div></details>`:`<div class="legacy-exclusion-policy-only"><strong>Exclusions horaires : Policies</strong><small>Les anciennes cases 12h–13h / 13h–14h sont désactivées pour éviter un double filtrage.</small></div>`):'';
  return dates+
    `<label>Heure début<input type="time" name="time_from" value="${esc(tf)}" required></label><label>Heure fin<input type="time" name="time_to" value="${esc(tt)}" required></label>`+
    scopeFields+
    `<label>Durée minimum<select name="min_disconnect"><option value="0" ${min==='0'?'selected':''}>Toutes les coupures</option><option value="1" ${min==='1'?'selected':''}>≥ 1 s</option><option value="10" ${min==='10'?'selected':''}>≥ 10 s</option><option value="20" ${min==='20'?'selected':''}>≥ 20 s</option><option value="60" ${min==='60'?'selected':''}>≥ 1 min</option><option value="300" ${min==='300'?'selected':''}>≥ 5 min</option></select></label>`+
    (includeCallScope?`<label>Contexte déconnexion<select name="call_scope"><option value="all" ${scope==='all'?'selected':''}>Toutes</option><option value="during" ${scope==='during'?'selected':''}>Pendant appel</option><option value="outside" ${scope==='outside'?'selected':''}>Hors appel</option></select></label>`:'')+
    exclusion;
}

let diagnosticAgentPage=0;
let diagnosticAgentPageSize=10;
let diagnosticAgentSort={key:'',direction:'default'};try{const v=JSON.parse(sessionStorage.getItem('nelyio.rc29.diagnostic.sort')||'null');if(v&&v.key&&['asc','desc'].includes(v.direction))diagnosticAgentSort=v;}catch(_){}
function diagnosticDateLabel(){try{return new Intl.DateTimeFormat('fr-FR',{weekday:'short',day:'2-digit',month:'long',year:'numeric'}).format(new Date());}catch{return '';}}
function diagnosticPageHeader(title,subtitle){
  return `<section class="diag-page-head"><div><h2>${esc(title)}</h2><p>${esc(subtitle)}</p></div><span class="diag-current-date">${esc(diagnosticDateLabel())}</span></section>`;
}
function diagnosticHeader(subtitle='Obtenez rapidement une vue d’ensemble des incidents techniques par période et par équipe.'){
  return diagnosticPageHeader('Diagnostic Nelyio',subtitle);
}
function diagnosticInfoBanner(text){return `<div class="diag-info-banner"><span class="diag-info-icon">i</span><span>${esc(text)}</span></div>`;}
function diagnosticFilterFields(info,prefix,{status=true}={}){
  const f=info.common_filters||info.filters||{},cfg=info.config||{},from=f.date_from||info.date_from||info.day||'',to=f.date_to||info.date_to||info.day||from;
  const tf=f.time_from||cfg.work_start||'08:00',tt=f.time_to||cfg.work_end||'19:00',agent=f.agent||'',group=f.group||'',min=String(f.min_disconnect??0),scope=f.call_scope||'all',listId=`${prefix}-diag-agent-list`;
  const agents=(info.available_agents||[]).map(r=>`<option value="${esc(r.agent)}">${esc(r.name||r.agent)}${(r.group_names&&r.group_names.length)?' · '+esc(r.group_names.join(' / ')):(r.group_name?' · '+esc(r.group_name):'')}${r.pc?' · '+esc(r.pc):''}</option>`).join('');
  const groups=(info.admin_groups||info.available_groups||[]).map(g=>`<option value="${esc(g.id)}" ${String(g.id)===String(group)?'selected':''}>${esc(g.name)}</option>`).join('');
  return `<div class="diag-filter-main">
    <label>Du<input type="date" name="date_from" value="${esc(from)}" required></label>
    <label>Au<input type="date" name="date_to" value="${esc(to)}" required></label>
    <label>Équipe / groupe<select name="group"><option value="">Tous les groupes</option>${groups}</select></label>
    <label class="diag-agent-search">Rechercher un agent<input name="agent" list="${listId}" value="${esc(agent)}" placeholder="Nom ou identifiant…"><datalist id="${listId}">${agents}</datalist></label>
    <details class="diag-more-filters"><summary>Plus de filtres</summary><div class="diag-advanced-grid"><label>Heure début<input type="time" name="time_from" value="${esc(tf)}" required></label><label>Heure fin<input type="time" name="time_to" value="${esc(tt)}" required></label><label>Durée minimum<select name="min_disconnect"><option value="0" ${min==='0'?'selected':''}>Toutes</option><option value="1" ${min==='1'?'selected':''}>≥ 1 s</option><option value="10" ${min==='10'?'selected':''}>≥ 10 s</option><option value="20" ${min==='20'?'selected':''}>≥ 20 s</option><option value="60" ${min==='60'?'selected':''}>≥ 1 min</option><option value="300" ${min==='300'?'selected':''}>≥ 5 min</option></select></label><label>Contexte<select name="call_scope"><option value="all" ${scope==='all'?'selected':''}>Tous</option><option value="during" ${scope==='during'?'selected':''}>Pendant appel</option><option value="outside" ${scope==='outside'?'selected':''}>Hors appel</option></select></label>${status?`<label>Qualification<select name="diagnosis">${supportOptions(supportDiagnoses)}</select></label><label>Suivi<select name="status">${supportOptions(supportStatuses)}</select></label>`:''}</div><p class="diag-policy-note">Les exclusions horaires durables sont gérées dans Administration → Policies Nelyio.</p></details>
  </div>`;
}

function diagnosticKpiCard(icon,label,value,tone='teal',sub=''){
  return `<article class="diag-kpi"><span class="diag-kpi-icon ${esc(tone)}">${icon}</span><div><span>${esc(label)}</span><strong>${esc(value)}</strong>${sub?`<small>${esc(sub)}</small>`:''}</div></article>`;
}
function diagnosticAgentSortValue(r,key,policies=[]){
  if(key==='agent')return String(r.name||r.agent||'').toLowerCase();
  if(key==='priority')return Number((policies.find(p=>String(p.priority||'')===String(r.priority||''))||{}).rank||0);
  if(key==='incidents')return Number(r.deco||0);if(key==='during')return Number(r.deco_call||0);if(key==='lost')return Number(r.lost_seconds||0);return 0;
}
function diagnosticRenderAgentTable(stats,d){
  const host=$('#diagnostic-agent-table');if(!host)return;const policies=stats.priority_policy||[];
  let rows=(stats.agents||[]).slice();const key=diagnosticAgentSort.key||'priority',direction=diagnosticAgentSort.key?diagnosticAgentSort.direction:'desc';rows.sort((a,b)=>{const av=diagnosticAgentSortValue(a,key,policies),bv=diagnosticAgentSortValue(b,key,policies),am=av===null||av===undefined||av==='',bm=bv===null||bv===undefined||bv==='';if(am||bm){if(am&&bm)return 0;return am?1:-1;}const cmp=typeof av==='string'?av.localeCompare(bv,'fr',{sensitivity:'base'}):av-bv;return direction==='asc'?cmp:-cmp;});
  const pages=Math.max(1,Math.ceil(rows.length/diagnosticAgentPageSize));diagnosticAgentPage=Math.min(diagnosticAgentPage,pages-1);const start=diagnosticAgentPage*diagnosticAgentPageSize,visible=rows.slice(start,start+diagnosticAgentPageSize);
  const sortHead=(label,k)=>`<button type="button" class="diag-sort ${key===k?'active':''}" data-diag-sort="${k}">${esc(label)} <span>${key===k?(direction==='asc'?'↑':'↓'):'↕'}</span></button>`;
  host.innerHTML=`<section class="diag-table-card"><div class="diag-table-head"><div><h3>Agents — incidents de la période</h3><p>Cliquez sur un agent pour voir ses incidents en détail.</p></div><span>${rows.length} agent(s) concerné(s)</span></div><div class="diag-table-wrap"><table><thead><tr><th>${sortHead('Agent','agent')}</th><th>${sortHead('Incidents','incidents')}</th><th>${sortHead('Pendant appel','during')}</th><th>${sortHead('Temps perdu','lost')}</th><th>${sortHead('Priorité','priority')}</th><th></th></tr></thead><tbody>${visible.map(r=>`<tr><td><button type="button" class="diag-agent-link" data-diag-agent="${esc(r.agent)}"><strong>${esc(r.name||r.agent)}</strong><small>${esc(r.agent)}</small></button></td><td><strong>${Number(r.deco||0)}</strong></td><td><strong>${Number(r.deco_call||0)} / ${Number(r.deco||0)}</strong></td><td><strong>${supDuration(r.lost_seconds||0)}</strong></td><td>${supportPriorityBadge(r.priority,r.priority_reasons,policies)}</td><td><button type="button" class="diag-row-open" data-diag-agent="${esc(r.agent)}" aria-label="Ouvrir les détails">›</button></td></tr>`).join('')||'<tr><td colspan="6" class="empty">Aucun incident technique dans cette sélection.</td></tr>'}</tbody></table></div><div class="diag-table-footer"><span>${rows.length?`${start+1}–${Math.min(start+diagnosticAgentPageSize,rows.length)} sur ${rows.length}`:'0 résultat'}</span><div><button type="button" class="diag-page-btn" id="diag-agent-prev" ${diagnosticAgentPage<=0?'disabled':''}>‹</button><button type="button" class="diag-page-btn" id="diag-agent-next" ${diagnosticAgentPage+1>=pages?'disabled':''}>›</button></div></div></section>`;
  host.querySelectorAll('[data-diag-sort]').forEach(b=>b.onclick=()=>{const k=b.dataset.diagSort;if(diagnosticAgentSort.key!==k||diagnosticAgentSort.direction==='default')diagnosticAgentSort={key:k,direction:'asc'};else if(diagnosticAgentSort.direction==='asc')diagnosticAgentSort={key:k,direction:'desc'};else diagnosticAgentSort={key:'',direction:'default'};try{if(diagnosticAgentSort.key)sessionStorage.setItem('nelyio.rc29.diagnostic.sort',JSON.stringify(diagnosticAgentSort));else sessionStorage.removeItem('nelyio.rc29.diagnostic.sort');}catch(_){}diagnosticAgentPage=0;diagnosticRenderAgentTable(stats,d);});
  host.querySelectorAll('[data-diag-agent]').forEach(b=>b.onclick=()=>{const q=new URLSearchParams({agent:b.dataset.diagAgent,date_from:d.date_from,date_to:d.date_to});const group=$('#support-filters')?.elements.group?.value||'';if(group)q.set('group',group);location.hash='#disconnect-details?'+q.toString();});
  $('#diag-agent-prev')?.addEventListener('click',()=>{diagnosticAgentPage=Math.max(0,diagnosticAgentPage-1);diagnosticRenderAgentTable(stats,d);});
  $('#diag-agent-next')?.addEventListener('click',()=>{diagnosticAgentPage=Math.min(pages-1,diagnosticAgentPage+1);diagnosticRenderAgentTable(stats,d);});
}

function supportCallBadge(r){return r.during_call?'<span class="support-impact-call">Pendant appel</span>':'<span class="support-impact-out">Hors appel</span>';}
function supportEventClassBadge(r){const code=String(r.event_class||'technical_disconnect'),label=r.event_label||(code==='collective_incident'?'Incident collectif':code==='probable_closure'?'Fermeture / pause probable':'Déconnexion technique');return `<span class="support-event-class ${esc(code)}" title="${esc(r.classification_reason||'')}">${esc(label)}</span>`;}
function supportSpecialStatuses(r){const rows=r.special_statuses||[];return rows.length?`<div class="support-special-list">${rows.map(x=>`<span class="support-special ${esc(x.code||'')}">${esc(x.label)}${Number(x.count)>0?` · ${esc(x.count)}`:''}</span>`).join('')}</div>`:'';}
function supportScoreBreakdown(r){const rows=r.score_components||[];if(!rows.length)return '<small class="sub">Aucun point technique</small>';return `<details class="support-score-breakdown"><summary>Voir le calcul</summary><ul>${rows.map(x=>`<li><strong>+${esc(x.points)}</strong> ${esc(x.label)} · ${esc(x.detail||'')}</li>`).join('')}</ul></details>`;}
function importResultText(r){
  const counts=`${r.rows||0} activité(s) · ${r.calls||0} appel(s)`;
  const issue=(r.reference?.reasons||[]).join(' ');
  const seconds=Number(r.performance?.total_seconds||0);
  const timing=seconds>0?` · ${seconds.toFixed(1)} s`:'';
  return `${r.message||(r.duplicate?'Export déjà présent.':'Import terminé.')} ${counts}${timing}${issue?' '+issue:''}`;
}
async function supportAutoImportStatus(target,module='support'){
  if(!canRead(module))return;const host=$(target);if(!host)return;
  try{
    const d=await api('/api/supervision/auto-import'),counts=d.job_counts||{};
    const warnings=(counts.partial||0)+(counts.failed||0)+(counts.review||0);
    const labels={queued:'En attente',completed:'Terminé',partial:'Partiel — reprise prévue',review:'À vérifier',failed:'Échec',running:'En cours / reprise',purged:'Archivé par rétention'};
    host.innerHTML=`<div class="sup-health ${warnings?'sup-warn':'sup-ok'}"><strong>${warnings?esc(warnings+' import(s) à vérifier'):((counts.running||counts.queued)?'Import en attente / en cours':((d.jobs||[]).length?'Traitements terminés':'Aucun import suivi'))}</strong><span>${esc(d.pending.length)} fichier(s) en attente · heures Europe/Paris</span></div>
      <details><summary>Suivi des imports et références</summary><div class="table-wrap"><table><thead><tr><th>Fichier</th><th>État</th><th>Action</th></tr></thead><tbody>${(d.jobs||[]).map(j=>`<tr><td>${esc(j.filename)}<small class="sub">${esc(j.updated_at)}</small></td><td>${esc(labels[j.status]||j.status)}${j.error?`<small class="sub">${esc(j.error)}</small>`:''}${Object.entries(j.steps||{}).filter(([k,v])=>v.state==='error').map(([k,v])=>`<small class="sub">${esc(k)} : ${esc(v.message)}</small>`).join('')}</td><td>${canWrite(module)&&['partial','failed'].includes(j.status)?`<button type="button" class="button ghost" data-import-retry="${esc(j.digest)}">Reprendre</button>`:''}</td></tr>`).join('')||'<tr><td colspan="3">Aucun nouvel import suivi.</td></tr>'}</tbody></table></div>
      <p>La sélection d’une référence change les données utilisées pour la journée ; les autres imports restent conservés.</p><div class="table-wrap"><table><thead><tr><th>Jour / import</th><th>Activités / appels</th><th>Référence</th></tr></thead><tbody>${(d.references||[]).map(r=>`<tr><td>${esc(r.reference_day)} · #${esc(r.id)}</td><td>${esc(r.rows_count||0)} / ${esc(r.calls||0)}</td><td>${esc([r.activity_active?'Activités actives':'',r.calls_active?'Appels actifs':''].filter(Boolean).join(' · ')||'Non active')}${canWrite(module)&&((r.has_activities&&!r.activity_active)||(r.has_calls&&!r.calls_active))?` <button type="button" class="button ghost" data-import-reference="${esc(r.id)}">Utiliser cette référence</button>`:''}${(r.reasons||[]).length?`<small class="sub">${esc(r.reasons.join(' '))}</small>`:''}</td></tr>`).join('')}</tbody></table></div></details>`;
    host.querySelectorAll('[data-import-retry],[data-import-reference]').forEach(button=>button.onclick=async()=>{
      const reference=button.dataset.importReference;
      if(reference&&!confirm('Utiliser cet import comme référence de la journée ? Les données précédentes restent conservées.'))return;
      button.disabled=true;
      try{
        const result=await importInBackground('/api/supervision/import?action='+(reference?'reference':'retry'),{method:'POST',body:JSON.stringify(reference?{import_id:Number(reference)}:{job_id:button.dataset.importRetry})},target);
        await supportAutoImportStatus(target,module);
        const note=document.createElement('p');note.setAttribute('role','status');note.textContent=importResultText(result);host.prepend(note);
        if(module==='calls')await callsLoad();else await supportLoad();
      }catch(e){button.disabled=false;const note=document.createElement('p');note.setAttribute('role','alert');note.textContent=e.message;host.append(note);}
    });
  }catch(e){host.textContent='État des imports indisponible : '+e.message;}
}

function supportDisconnectTrend(items){
  const valid=items.filter(r=>r.total!==null),w=760,h=260,left=50,right=24,top=28,bottom=205,max=Math.max(1,...valid.flatMap(r=>[r.total||0,r.call||0]));
  const xx=i=>left+(w-left-right)*(items.length===1?0.5:i/Math.max(1,items.length-1));const yy=v=>bottom-(bottom-top)*v/max;
  const path=key=>{let d='',connected=false;items.forEach((r,i)=>{const v=r[key];if(v===null){connected=false;return;}d+=`${connected?'L':'M'}${xx(i)},${yy(v)} `;connected=true;});return d;};
  const tick=Math.max(1,Math.ceil(items.length/7));
  return `<article class="card panel sup-chart-card"><h3>Déconnexions sur la période</h3><p class="sup-chart-description">Total des coupures et part survenue pendant un appel. Une seule source est utilisée par journée pour éviter les doubles comptages.</p><div class="support-legend"><span><i class="support-dot total"></i>Total</span><span><i class="support-dot call"></i>Pendant appel</span></div><svg class="sup-chart-svg" viewBox="0 0 ${w} ${h}" role="img" aria-label="Déconnexions par jour">${[0,.5,1].map(f=>`<line x1="${left}" x2="${w-right}" y1="${yy(max*f)}" y2="${yy(max*f)}" stroke="#dce5ed"/><text x="${left-8}" y="${yy(max*f)+4}" text-anchor="end" class="sup-svg-label">${Math.round(max*f)}</text>`).join('')}<path d="${path('total')}" fill="none" stroke="#246e91" stroke-width="3"/><path d="${path('call')}" fill="none" stroke="#b24c4c" stroke-width="3"/>${items.map((r,i)=>`${r.total===null?'':`<circle cx="${xx(i)}" cy="${yy(r.total)}" r="4" fill="#246e91"><title>${esc(r.label)} : ${r.total} déconnexion(s)</title></circle><circle cx="${xx(i)}" cy="${yy(r.call)}" r="4" fill="#b24c4c"><title>${esc(r.label)} : ${r.call} pendant appel</title></circle>`}${i%tick===0||i===items.length-1?`<text x="${xx(i)}" y="${bottom+24}" text-anchor="middle" class="sup-svg-label">${esc(r.label.slice(5))}</text>`:''}`).join('')}</svg><details class="sup-chart-data"><summary>Voir les valeurs jour par jour</summary><table><thead><tr><th>Date</th><th>Source</th><th>Total</th><th>Pendant appel</th><th>Critiques</th><th>Agents</th></tr></thead><tbody>${items.map(r=>`<tr><td>${esc(r.label)}</td><td>${esc(supportSourceName(r.source))}</td><td>${r.total===null?'—':r.total}</td><td>${r.call===null?'—':r.call}</td><td>${r.critical===null?'—':r.critical}</td><td>${r.agents===null?'—':r.agents}</td></tr>`).join('')}</tbody></table></details></article>`;
}

function supportLostTrend(items){
  const mapped=items.map(r=>({...r,value:r.lost_seconds===null?null:Math.round(r.lost_seconds/60*10)/10}));
  const valid=mapped.filter(r=>r.value!==null),w=760,h=260,left=55,right=22,top=30,bottom=205,max=Math.max(1,...valid.map(r=>r.value||0));const step=(w-left-right)/Math.max(1,mapped.length),bar=Math.min(44,step*.62),tick=Math.max(1,Math.ceil(mapped.length/7));
  return `<article class="card panel sup-chart-card"><h3>Temps perdu par jour</h3><p class="sup-chart-description">Somme des durées entre déconnexion et reconnexion, en minutes. Les intervalles qui se chevauchent pour un même agent sont fusionnés.</p><svg class="sup-chart-svg" viewBox="0 0 ${w} ${h}" role="img" aria-label="Temps perdu par jour">${[0,.5,1].map(f=>`<line x1="${left}" x2="${w-right}" y1="${bottom-(bottom-top)*f}" y2="${bottom-(bottom-top)*f}" stroke="#e3eaf0"/><text x="${left-8}" y="${bottom-(bottom-top)*f+4}" text-anchor="end" class="sup-svg-label">${Math.round(max*f*10)/10}</text>`).join('')}${mapped.map((r,i)=>{const x=left+i*step+(step-bar)/2;if(r.value===null)return i%tick===0?`<text x="${x+bar/2}" y="${bottom+20}" text-anchor="middle" class="sup-svg-label">${esc(r.label.slice(5))}</text>`:'';const hh=(bottom-top)*(r.value/max);return `<rect x="${x}" y="${bottom-hh}" width="${bar}" height="${hh}" rx="4" fill="#9a6a2d"><title>${esc(r.label)} : ${r.value} min</title></rect>${r.value?`<text x="${x+bar/2}" y="${bottom-hh-7}" text-anchor="middle" class="sup-svg-value">${r.value}</text>`:''}${i%tick===0||i===mapped.length-1?`<text x="${x+bar/2}" y="${bottom+20}" text-anchor="middle" class="sup-svg-label">${esc(r.label.slice(5))}</text>`:''}`;}).join('')}</svg><details class="sup-chart-data"><summary>Voir les valeurs</summary><table><thead><tr><th>Date</th><th>Temps perdu</th></tr></thead><tbody>${items.map(r=>`<tr><td>${esc(r.label)}</td><td>${r.lost_seconds===null?'Pas de données':supDuration(r.lost_seconds)}</td></tr>`).join('')}</tbody></table></details></article>`;
}

function supportIntegrityPanel(integrity){
  const applicable=integrity.applicable!==false,cls=!applicable?'warn':(integrity.score>=85?'good':(integrity.score>=60?'warn':'bad'));
  const issues=(integrity.issues||[]).map(i=>`<div class="support-issue ${i.severity}"><strong>${esc(i.label)}</strong>${esc(i.detail)}</div>`).join('');
  const sundays=Number(integrity.excluded_sundays||0),sundayNote=sundays?` · ${sundays} dimanche(s) exclu(s) du contrôle`:'';
  const clean=!applicable?'La période contrôlée ne contient que des dimanches : aucun jour ouvré n’est évalué.':'Aucune anomalie détectée sur cette période : les chiffres ci-dessous peuvent être considérés comme fiables.';
  return `<section class="card panel support-integrity ${cls}">
    <div class="support-integrity-score"><strong>${applicable?integrity.score:'—'}</strong><span>${esc(integrity.label)}</span></div>
    <div class="support-integrity-body">
      <h3>Intégrité des données sur la période</h3>
      <p>${integrity.export_days} jour(s) sur export SIMPLIFY2 (référence) · ${integrity.capture_days} sur capture provisoire · ${integrity.missing_days} sans aucune source, sur ${integrity.total_days} jour(s) contrôlé(s)${esc(sundayNote)}.</p>
      ${issues?`<div class="support-issue-list">${issues}</div>`:`<div class="support-integrity-clean">${esc(clean)}</div>`}
    </div>
  </section>`;
}

function supportClusters(clusters){
  if(!clusters||!clusters.length)return '';
  return `<section class="card panel support-clusters"><div class="panel-head"><div><h2>Pannes collectives détectées</h2><p>Plusieurs agents déconnectés à quelques secondes d’intervalle : signe probable d’une cause partagée (réseau, Hermès, alimentation du site) plutôt que d’un problème poste par poste.</p></div><span>${clusters.length} groupe(s)</span></div>${clusters.map(cl=>`<div class="support-cluster-card"><strong>${esc(cl.start_text)} · ${cl.agent_count} agents touchés</strong><span class="sub">${esc(cl.agents.join(', '))} — ${cl.incident_count} coupure(s), ${supDuration(cl.lost_seconds)} perdu au total</span></div>`).join('')}</section>`;
}

function supportDurationAnomalies(ds){
  const rows=ds?.anomalies||[];
  return `<section class="card panel support-duration-anomalies"><div class="panel-head"><div><h2>Anomalies de durée · plus de 1 heure</h2><p>Ces déconnexions sont volontairement exclues des KPI, graphiques, temps perdu, clusters et scores de risque. Elles restent visibles ici pour vérification.</p></div><span>${rows.length} anomalie(s)</span></div>${rows.length?`<div class="support-anomaly-warning">Une durée supérieure à 1 h est traitée comme une anomalie de session ou de donnée, pas comme une coupure normale.</div><div class="table-wrap"><table><thead><tr><th>Agent</th><th>Début</th><th>Fin</th><th>Durée</th><th>Contexte</th><th>Traitement</th><th>Source</th></tr></thead><tbody>${rows.map(r=>`<tr><td><strong>${esc(r.name||r.agent)}</strong><small class="sub">${esc(r.agent)}</small>${r.group_name?`<small class="sub">Groupe : ${esc(r.group_name)}</small>`:''}</td><td>${esc(r.start_text)}</td><td>${esc(r.end_text)}</td><td><strong>${supDuration(r.seconds)}</strong></td><td>${supportCallBadge(r)}${r.call_id?`<button class="button ghost" data-support-call="${esc(r.call_id)}">Appel · indice ${esc(r.indice||'—')}</button>`:''}<small class="sub">${esc(r.detail||r.reason||'À vérifier')}</small></td><td>${r.policy_applied?`<small><strong>Policy :</strong> ${esc(r.policy_reason||'')}</small>`:''}${r.declaration_applied?`<small><strong>Déclaration :</strong> ${esc(r.declaration_reason||'')}</small>`:''}${!r.policy_applied&&!r.declaration_applied?'—':''}</td><td>${esc(supportSourceName(r.source))}</td></tr>`).join('')}</tbody></table></div>`:'<div class="support-integrity-clean">Aucune déconnexion supérieure à 1 heure sur la période sélectionnée.</div>'}</section>`;
}

function supportDiagnosisBadge(code,label){return `<span class="support-diagnosis ${esc(code||'indetermine')}">${esc(label||'À qualifier')}</span>`;}

function supportTechnicalBrief(d){
  const ds=d.disconnects,gs=ds.summary,top=(ds.agents||[])[0],peak=(ds.hourly||[]).slice().sort((a,b)=>(b.total-a.total)||(b.lost_seconds-a.lost_seconds))[0],worst=(ds.top_days||[])[0];
  const qualified=Math.max(0,(d.summary.signals||0)-(d.summary.unqualified||0)),qualifiedPct=d.summary.signals?Math.round(qualified*100/d.summary.signals):100;
  return `<section class="support-brief-grid">
    <article class="card support-brief"><span class="support-brief-label">Priorité principale</span><strong>${top?supportPriorityBadge(top.priority,top.priority_reasons,ds.priority_policy||[]):'Aucune alerte'}</strong><p>${top?`${esc(top.name||top.agent)}${top.group_name?' · '+esc(top.group_name):''} · score technique ${esc(top.technical_score??top.risk_score)} · ${top.deco_call} coupure(s) technique(s) pendant appel`:'Aucune déconnexion technique mesurée dans la sélection.'}</p>${top?supportSpecialStatuses(top):''}</article>
    <article class="card support-brief"><span class="support-brief-label">Heure la plus touchée</span><strong>${peak&&peak.total?esc(peak.label):'—'}</strong><p>${peak&&peak.total?`${peak.total} incident(s), ${supDuration(peak.lost_seconds)} perdu`:'Pas assez de données pour identifier un pic.'}</p></article>
    <article class="card support-brief"><span class="support-brief-label">Journée la plus chargée</span><strong>${worst?esc(worst.label):'—'}</strong><p>${worst?`${worst.total} incident(s) · ${worst.critical} critique(s) · ${supDuration(worst.lost_seconds)}`:'Aucune journée exploitable.'}</p></article>
    <article class="card support-brief"><span class="support-brief-label">Qualification helpdesk</span><strong>${qualifiedPct}%</strong><p>${qualified} / ${d.summary.signals||0} signal(aux) qualifié(s) · ${d.summary.unqualified||0} restant(s)</p></article>
  </section>`;
}

function supportAgentStats(stats){
  const rows=stats.agents||[],policies=stats.priority_policy||[];
  const priorityPolicy=supportPriorityPolicyText(policies);
  const priorityRank=r=>Number((policies.find(p=>String(p.priority||'')===String(r.priority||''))||{}).rank||0);
  return `<section class="card panel support-analysis"><div class="panel-head"><div><h2>Agents à surveiller</h2><p>Le score concerne uniquement le diagnostic technique. Cliquez sur un en-tête avec ⇅ pour trier le tableau ; le tri est conservé quand vous changez les filtres.</p></div><span>${rows.length} agent(s)</span></div><div class="support-rule-note"><strong>Chaîne de décision :</strong> événement brut → classification technique → Policies → Déclarations → score explicable → priorité.<br><strong>Politique active :</strong> ${esc(priorityPolicy)}<br><small>Le % de récurrence utilise les jours réellement travaillés détectés dans les données, pas tous les jours sélectionnés.</small></div><div class="table-wrap"><table class="support-rich-table support-sortable-table" data-support-sortable="agent-priority"><thead><tr><th>#</th>${supportSortHeader('Priorité','priority','number')}${supportSortHeader('Agent','agent','string')}${supportSortHeader('Technique','technical','number')}${supportSortHeader('En appel','in_call','number')}${supportSortHeader('Jours touchés / travaillés','affected_days','number')}${supportSortHeader('Temps perdu technique','lost_seconds','number')}${supportSortHeader('Score technique','score','number')}${supportSortHeader('Statuts spéciaux','special','number')}${supportSortHeader('Diagnostic','diagnosis','string')}<th></th></tr></thead><tbody>${rows.map((r,i)=>{const special=(r.collective_count||0)+(r.probable_closure_count||0)+(r.anomaly_count||0);return `<tr data-original-index="${i}"><td data-support-row-number>${i+1}</td><td data-sort-value="${priorityRank(r)}">${supportPriorityBadge(r.priority,r.priority_reasons,policies)}</td><td data-sort-value="${esc(String(r.name||r.agent||'').toLowerCase())}"><strong>${esc(r.name||r.agent)}</strong><small class="sub">${esc(r.agent)}</small>${r.group_name?`<small class="sub">Groupe : ${esc(r.group_name)}</small>`:''}</td><td data-sort-value="${Number(r.deco||0)}"><strong>${r.deco}</strong><small class="sub">${r.raw_deco!==r.deco?`${r.raw_deco} événement(s) brut(s) · `:''}${r.policy_excluded_count?`${r.policy_excluded_count} exclu(s) par Policy · `:''}${r.declaration_excluded_count?`${r.declaration_excluded_count} exclu(s) par Déclaration · `:''}${r.collective_count||0} collectif(s) · ${r.probable_closure_count||0} fermeture(s) probable(s)</small></td><td data-sort-value="${Number(r.deco_call||0)}">${r.deco_call}<small class="sub">${r.call_percent}% des coupures techniques</small></td><td data-sort-value="${Number(r.affected_worked_days_percent||0)}"><strong>${r.days_affected} / ${r.worked_days||0}</strong><small class="sub">${r.affected_worked_days_percent||0}% des jours travaillés</small></td><td data-sort-value="${Number(r.lost_seconds||0)}"><strong>${supDuration(r.lost_seconds||0)}</strong><small class="sub">${r.technical_lost_minutes_per_affected_day||0} min / jour touché</small></td><td data-sort-value="${Number(r.technical_score??r.risk_score??0)}"><strong>${r.technical_score??r.risk_score}</strong>${supportScoreBreakdown(r)}</td><td data-sort-value="${Number(special)}">${supportSpecialStatuses(r)||'<span class="muted">Aucun</span>'}</td><td class="support-diagnosis-cell" data-sort-value="${esc(String(r.likely_cause||r.diagnosis_code||'').toLowerCase())}">${supportDiagnosisBadge(r.diagnosis_code,r.likely_cause)}<small>${esc(r.suggested_action||'')}</small></td><td><button type="button" class="button ghost" data-support-stat-agent="${esc(r.agent)}">Analyser</button></td></tr>`;}).join('')||'<tr><td colspan="11" class="empty">Aucun signal mesurable dans cette sélection.</td></tr>'}</tbody></table></div></section>`;
}

function supportIncidentJournal(stats){
  const rows=(stats.recent||[]).slice(0,200);
  return `<section class="card panel support-analysis"><div class="panel-head"><div><h2>Journal détaillé des événements</h2><p>Chaque coupure reste visible, y compris une fermeture application / pause probable. La classification explique ce qui entre ou non dans le score individuel.</p></div><span>${rows.length} ligne(s)</span></div><div class="table-wrap"><table class="support-rich-table"><thead><tr><th>Début</th><th>Fin</th><th>Agent</th><th>Durée</th><th>Classification</th><th>Impact</th><th>Source</th><th>Appel associé</th></tr></thead><tbody>${rows.map(r=>`<tr><td>${esc(r.start_text)}</td><td>${esc(r.end_text)}</td><td><button type="button" class="button ghost" data-support-stat-agent="${esc(r.agent)}">${esc(r.name||r.agent)}</button><small class="sub">${esc(r.agent)}</small>${r.group_name?`<small class="sub">Groupe : ${esc(r.group_name)}</small>`:''}</td><td><strong>${supDuration(r.seconds)}</strong></td><td>${supportEventClassBadge(r)}<small class="sub">${esc(r.classification_reason||'')}</small>${r.policy_applied?`<small class="sub"><strong>Policy :</strong> ${esc(r.policy_reason||'')}</small>`:''}${r.declaration_applied?`<small class="sub"><strong>Déclaration :</strong> ${esc(r.declaration_reason||'')}</small>`:''}</td><td>${supportCallBadge(r)}</td><td>${esc(supportSourceName(r.source))}</td><td>${r.call_id?`<button class="button ghost" data-support-call="${esc(r.call_id)}">Indice ${esc(r.indice||'—')}</button><small class="sub">ANI ${esc(r.ani||'—')}</small>`:(r.during_call?'Appel détecté, ID non disponible':'—')}</td></tr>`).join('')||'<tr><td colspan="8" class="empty">Aucun événement mesuré.</td></tr>'}</tbody></table></div></section>`;
}

function supportProbableClosures(stats){
  const rows=(stats.probable_closures||[]).slice(0,100);
  if(!rows.length)return '';
  return `<section class="card panel support-analysis"><div class="panel-head"><div><h2>Fermetures application / pauses probables</h2><p>Ces événements ne sont pas supprimés : ils sont isolés du score technique individuel par défaut car plusieurs indices concordent avec une fermeture volontaire ou une pause.</p></div><span>${rows.length} événement(s)</span></div><div class="table-wrap"><table><thead><tr><th>Agent</th><th>Début</th><th>Fin</th><th>Durée</th><th>Justification</th></tr></thead><tbody>${rows.map(r=>`<tr><td><strong>${esc(r.name||r.agent)}</strong><small class="sub">${esc(r.agent)}</small></td><td>${esc(r.start_text)}</td><td>${esc(r.end_text)}</td><td>${supDuration(r.seconds)}</td><td>${esc(r.classification_reason||'')}</td></tr>`).join('')}</tbody></table></div></section>`;
}

function supportLongest(stats){
  const rows=(stats.longest||[]).slice(0,20);
  return `<section class="card panel support-analysis"><div class="panel-head"><div><h2>Top 20 des coupures les plus longues</h2><p>Pour repérer rapidement les incidents avec le plus fort impact en temps perdu.</p></div></div><div class="table-wrap"><table><thead><tr><th>Agent</th><th>Début</th><th>Fin</th><th>Durée</th><th>Impact</th><th>Source</th></tr></thead><tbody>${rows.map(r=>`<tr><td><button type="button" class="button ghost" data-support-stat-agent="${esc(r.agent)}">${esc(r.name||r.agent)}</button><small class="sub">${esc(r.agent)}</small>${r.group_name?`<small class="sub">Groupe : ${esc(r.group_name)}</small>`:''}</td><td>${esc(r.start_text)}</td><td>${esc(r.end_text)}</td><td><strong>${supDuration(r.seconds)}</strong></td><td>${supportCallBadge(r)}</td><td>${esc(supportSourceName(r.source))}</td></tr>`).join('')||'<tr><td colspan="6" class="empty">Aucune coupure mesurée.</td></tr>'}</tbody></table></div></section>`;
}

function supportImportPanel(){
  if(!canWrite('support'))return '';
  return `<details class="card panel sup-settings support-import-panel" id="support-import-panel"><summary>Importer un export SIMPLIFY2</summary><p><strong>V60 :</strong> les gros imports ne passent plus par le serveur Web. Sur le serveur Nelyio, lancer <code>OPEN_NELYIO_IMPORTER.bat</code>, sélectionner un ou plusieurs ZIP/CSV/group.har, puis lancer l'import multiple.</p><p>Le Web, Live et Analytics restent ind&#233;pendants pendant le traitement. Les groupes conservent la derni&#232;re affectation ACTIVE valide si un export incomplet ne contient pas les affectations agents/files.</p><div id="support-auto-import-status"></div></details>`;
}


async function supportLoadAgentContext(){
  const host=$('#support-agent-context');if(!host)return;const term=$('#support-filters')?.elements.agent.value.trim();
  if(!term){host.innerHTML='<section class="card panel support-context-empty"><h2>Contexte poste / agent</h2><p>Sélectionne un agent dans le tableau <strong>Agents à surveiller</strong> pour afficher son poste, IP, site, passerelle, Windows et la dernière remontée UDiagnostic.</p></section>';return;}
  host.innerHTML='<section class="card panel"><h2>Contexte poste / agent</h2><p class="sup-chart-description">Recherche du poste associé…</p></section>';
  try{
    const inv=await api('/api/inventory?q='+encodeURIComponent(term));
    const exact=(inv.rows||[]).filter(r=>[r.utilisateur,r.utilisateur_affiche].some(v=>String(v||'').toLowerCase()===term.toLowerCase()));const rows=(exact.length?exact:inv.rows||[]).slice(0,8);
    host.innerHTML=`<section class="card panel support-agent-context"><div class="panel-head"><div><h2>Contexte poste / agent · ${esc(term)}</h2><p>Données issues du dernier diagnostic du parc. Elles complètent les statistiques Hermès pour orienter le dépannage.</p></div><span>${rows.length} poste(s)</span></div>${rows.length?`<div class="support-device-grid">${rows.map(r=>`<article class="support-device"><div class="support-device-head"><div><strong>${esc(r.ordinateur)}</strong><small>${esc(r.utilisateur_affiche||r.utilisateur||'Utilisateur non renseigné')}</small></div><span class="support-site ${r.site_actuel==='TELETRAVAIL'?'remote':r.site_actuel==='SUR SITE'?'local':'unknown'}">${esc(r.site_actuel||'INCONNU')}</span></div><dl><div><dt>IP</dt><dd>${esc(r.adresse_ip||'—')}</dd></div><div><dt>Passerelle</dt><dd>${esc(r.passerelle||'—')}</dd></div><div><dt>Collecteur</dt><dd>${esc(r.collecteur||'—')}</dd></div><div><dt>Dernière vue</dt><dd>${esc(r.date_evenement||'—')}</dd></div><div><dt>Windows</dt><dd>${esc([r.windows,r.version_windows].filter(Boolean).join(' ')||'—')}</dd></div><div><dt>Matériel</dt><dd>${esc([r.fabricant,r.modele].filter(Boolean).join(' ')||'—')}</dd></div><div><dt>Groupe</dt><dd>${esc(r.groupe_utilisateur||'Non affecté')}</dd></div><div><dt>État suivi</dt><dd>${esc(r.suivi_statut||'—')}</dd></div><div><dt>État admin</dt><dd>${esc(r.statut||'—')}</dd></div></dl><a class="button ghost" href="#inventory/${encodeURIComponent(r.ordinateur)}">Ouvrir la fiche PC</a></article>`).join('')}</div>`:'<div class="empty">Aucun poste correspondant trouvé dans le parc. Vérifie l’identifiant UDiagnostic de cet agent.</div>'}</section>`;
  }catch(e){host.innerHTML=`<section class="card panel support-context-empty"><h2>Contexte poste / agent</h2><p>Impossible de charger le parc : ${esc(e.message)}</p></section>`;}
}

async function supportView(){
  clearTimeout(supTimer);supportMode='technical';supportPage=0;supportRequest++;diagnosticAgentPage=0;
  activate('support');setHead('Diagnostic Nelyio','Vue synthétique des incidents techniques par agent, groupe et période.');
  const initialQuery=new URLSearchParams(collectionDayQuery('support'));
  const hashQuery=new URLSearchParams(String(location.hash||'').split('?')[1]||'');
  for(const key of ['date_from','date_to','time_from','time_to','group','agent','call_id'])if(hashQuery.has(key))initialQuery.set(key,hashQuery.get(key));
  initialQuery.set('page','0');
  const info=await api('/api/supervision/support?'+initialQuery);if(!String(location.hash).startsWith('#support'))return;
  app.innerHTML=`<section class="diag-workspace">${diagnosticHeader()}${diagnosticInfoBanner('Vue simplifiée : les agents restent visibles ici. Le détail individuel des incidents est disponible dans le menu Détails des coupures.')}
  <form id="support-filters" class="diag-filter-card">${diagnosticFilterFields(info,'support')}<div class="diag-filter-actions"><button type="button" class="diag-reset" id="support-reset">Réinitialiser</button><button class="diag-apply">Appliquer</button></div></form>
  <div id="support-message" class="diag-message" role="status"></div><div id="support-cards" class="diag-kpi-grid"></div><div id="diagnostic-agent-table"></div>
  <details class="diag-advanced-drawer"><summary>Informations techniques avancées</summary><div class="diag-advanced-content"><div class="diag-advanced-toolbar"><span>Couverture, anomalies, incidents collectifs et signaux techniques.</span><div><button type="button" class="button ghost" id="support-refresh">Actualiser</button><button type="button" class="button ghost" id="support-stats-export">Exporter</button>${canWrite('support')?'<button type="button" class="button ghost" id="support-import-open">Importer</button>':''}</div></div><div id="support-admin-link" class="sup-health ${info.admin_directory_available?'sup-ok':'sup-warn'}"></div><div id="support-integrity"></div><div id="support-coverage"></div><div id="support-anomalies"></div><div id="support-clusters"></div><div id="support-agent-context"></div><section class="card panel support-signals"><div class="panel-head"><div><h2>Signaux techniques et suivi helpdesk</h2><p>Événements de diagnostic complémentaires, sans double comptage dans les KPI principaux.</p></div><span id="support-count"></span></div><div class="table-wrap"><table><thead id="support-head"></thead><tbody id="support-body"></tbody></table></div><div class="sup-pager"><button class="button ghost" id="support-prev">Précédent</button><span id="support-page"></span><button class="button ghost" id="support-next">Suivant</button></div></section>${supportImportPanel()}</div></details>${supportDialog()}</section>`;
  $('#sup-note-cancel').onclick=()=>$('#sup-dialog').close();
  $$('[data-call-sort-button]').forEach(b=>b.onclick=()=>callsCycleSort(b.dataset.callSortButton));
  $('#support-filters').onsubmit=e=>{e.preventDefault();supportPage=0;diagnosticAgentPage=0;supportLoad();};
  $('#support-reset').onclick=()=>{$('#support-filters').reset();supportPage=0;diagnosticAgentPage=0;supportLoad();};
  $('#support-stats-export').onclick=()=>supportExport();$('#support-refresh').onclick=()=>supportLoad();
  $('#support-prev').onclick=()=>{supportPage=Math.max(0,supportPage-1);supportLoad();};$('#support-next').onclick=()=>{supportPage++;supportLoad();};
  if($('#support-import-open'))$('#support-import-open').onclick=()=>{const d=$('#support-import-panel');d.open=true;d.scrollIntoView({behavior:'smooth',block:'center'});};
  if($('#support-import'))$('#support-import').onsubmit=supportImport;supportAutoImportStatus('#support-auto-import-status');await supportRender(info,initialQuery);
}

function supportQuery(){const q=new URLSearchParams(new FormData($('#support-filters')));q.set('page',supportPage);return q;}
async function supportImport(e){
  e.preventDefault();const f=$('#support-file').files[0];if(!f)return;if(!$('#support-offset').value){$('#support-import-result').textContent='Confirme le fuseau horaire de l’export avant l’import.';return;}const button=e.target.querySelector('button');button.disabled=true;$('#support-import-result').textContent='Import en cours…';
  try{const q=new URLSearchParams({filename:f.name,offset:$('#support-offset').value});const r=await importInBackground('/api/supervision/import?'+q,{method:'POST',headers:{'Content-Type':'application/octet-stream'},body:f},'#support-import-result');const gi=r.group_import||{},groupMsg=gi.assigned?` · ${gi.assigned} affectation(s) de groupe importée(s)${gi.created_groups?` · ${gi.created_groups} groupe(s) créé(s)`:''}`:'';$('#support-import-result').textContent=importResultText(r)+groupMsg;await supportAutoImportStatus('#support-auto-import-status');if(r.days?.length){$('#support-filters').elements.date_from.value=r.days[0];$('#support-filters').elements.date_to.value=r.days[r.days.length-1];}supportPage=0;await supportLoad();}catch(err){$('#support-import-result').textContent=err.message;}finally{button.disabled=false;}
}

async function supportRender(d,query){
    d.view_mode='technical';d.applied_filters=Array.from(query);supportCurrent=d;if($('#support-message'))$('#support-message').textContent='';
    const coverage=d.coverage||[],excludedSundayDays=new Set(d.integrity?.excluded_days||[]),effectiveCoverage=coverage.filter(r=>!excludedSundayDays.has(r.day)),missing=effectiveCoverage.filter(r=>r.source==='missing').map(r=>r.day),reference=effectiveCoverage.filter(r=>r.source==='export').length,capture=effectiveCoverage.filter(r=>r.source==='capture').length;
    if($('#support-admin-link')){const n=Number(d.excluded_agents_count||0);$('#support-admin-link').innerHTML=`<strong>${d.admin_directory_available?'Annuaire Administration lié':'Annuaire Administration indisponible'}${d.admin_directory_available?` · ${n} exclu(s)`:''}</strong><span>${d.admin_directory_available?'Les noms et groupes sont partagés avec Administration.':'Le filtrage groupe peut être limité.'}</span>`;}
    $('#support-coverage').innerHTML=`<div class="sup-health ${missing.length?'sup-warn':'sup-ok'}"><strong>Couverture ${esc(d.date_from)} → ${esc(d.date_to)} · ${reference} jour(s) SIMPLIFY2 · ${capture} capture · ${missing.length} sans données</strong><span>${missing.length?'Sans source : '+esc(missing.join(', ')):'Couverture disponible pour tous les jours contrôlés.'}</span></div>`;
    $('#support-integrity').innerHTML=d.integrity?supportIntegrityPanel(d.integrity):'';
    const ds=d.disconnects,gs=ds.summary;
    $('#support-cards').innerHTML=[
      diagnosticKpiCard('△','Incidents techniques',gs.total_deco,'red'),
      diagnosticKpiCard('◎','Agents touchés',gs.impacted_agents,'teal'),
      diagnosticKpiCard('◷','Temps perdu cumulé',supDuration(gs.total_lost),'blue'),
      diagnosticKpiCard('≋','Incidents collectifs',gs.collective_disconnects||0,'amber')
    ].join('');
    diagnosticRenderAgentTable(ds,d);
    $('#support-anomalies').innerHTML=supportDurationAnomalies(ds);$('#support-clusters').innerHTML=supportClusters(ds.clusters);await supportLoadAgentContext();
    $('#support-count').textContent=d.count+' résultat(s)';
    $('#support-head').innerHTML='<tr><th>Début / fin</th><th>Agent / poste</th><th>Signal</th><th>Durée</th><th>Source</th><th>Qualification / cause</th><th>Suivi</th></tr>';
    $('#support-body').innerHTML=d.rows.map((r,i)=>`<tr><td><strong>${esc(r.start_text)}</strong><small class="sub">Fin : ${esc(r.end_text||r.start_text)}</small></td><td><strong>${esc(r.name||r.agent||'Collecte')}</strong><small class="sub">${esc(r.collector||r.agent||'—')}</small>${r.group_name?`<small class="sub">Groupe : ${esc(r.group_name)}</small>`:''}</td><td><strong>${esc(r.state)}</strong><small class="sub">${esc(r.detail)}</small>${r.call_id?`<button class="button ghost" data-support-call="${esc(r.call_id)}">Ouvrir l’appel · indice ${esc(r.indice||'—')}</button>`:''}</td><td>${r.duration?`<strong>${supDuration(r.duration)}</strong>`:'Événement ponctuel'}</td><td>${esc(supportSourceName(r.source))}</td><td><strong>${esc(r.diagnosis)}</strong><small class="sub">${esc(r.cause)}</small></td><td><button class="button ghost" data-support-note="${i}">${esc(r.status)}</button>${r.notes?.length?`<small class="sub">${r.notes.length} note(s)</small>`:''}</td></tr>`).join('')||'<tr><td colspan="7" class="empty">Aucun résultat pour ces filtres.</td></tr>';
    $$('[data-support-note]').forEach(b=>b.onclick=()=>supNote(d.rows[Number(b.dataset.supportNote)]));$$('[data-support-call]').forEach(b=>b.onclick=()=>{const q=new URLSearchParams({call_id:b.dataset.supportCall,date_from:d.date_from,date_to:d.date_to});location.hash='#calls?'+q.toString();});
    $('#support-page').textContent=`Page ${supportPage+1} / ${Math.max(1,Math.ceil(d.count/100))}`;$('#support-prev').disabled=supportPage===0;$('#support-next').disabled=(supportPage+1)*100>=d.count;
}
async function supportLoad(){
  if(!String(location.hash).startsWith('#support')||!currentUser)return;const request=++supportRequest;
  try{
    $('#support-message').textContent='Chargement…';const query=supportQuery();const d=await api('/api/supervision/support?'+query);
    if(request!==supportRequest||!String(location.hash).startsWith('#support'))return;await supportRender(d,query);
  }catch(e){if(request===supportRequest&&$('#support-message'))$('#support-message').innerHTML=flash(e.message,'error');}
}



let analyticsCurrent=null,analyticsRequest=0;
function analyticsDeltaText(item,unit=''){
  if(!item)return '—';if(item.available===false)return 'Comparaison non interprétable';const d=Number(item.delta||0),pct=item.percent;
  const sign=d>0?'+':'';return `${sign}${unit==='time'?supDuration(Math.abs(d)):Math.abs(d)}${unit==='time'?'':unit} ${d===0?'':(d>0?'de plus':'de moins')}${pct===null||pct===undefined?'':` · ${pct>0?'+':''}${pct}%`}`;
}
function analyticsCategoryBadge(category,label){const cls=category==='offline'?'offline':category==='inactive'?'inactive':'technical';return `<span class="analytics-type ${cls}">${esc(label||category)}</span>`;}
function analyticsTrendStatus(status){return status==='appeared'?'Apparu sur la période':status==='cleared'?'Absent sur la période actuelle':status==='increased'?'Hausse':status==='decreased'?'Baisse':'Stable';}
function analyticsSignedDuration(seconds){const n=Number(seconds||0),sign=n>0?'+':n<0?'−':'';return sign+supDuration(Math.abs(n));}
function analyticsGuide(d){
  const cur=d.current,cv=cur.coverage;if(!cv)return '';
  const labels={export:'Export présent',capture:'Capture partielle',missing:'Sans source'};
  return `<section class="card panel"><div class="panel-head"><div><h2>Quoi vérifier en premier ?</h2><p>Constats et prochaines vérifications, calculés avec tes filtres.</p></div></div><div class="sup-chart-grid">${(cur.guidance||[]).map(x=>`<article class="analytics-diagnostic card"><h3>${esc(x.title)}</h3><p><strong>${esc(x.evidence)}</strong></p><p>${esc(x.action)}</p><a class="button ghost" href="#${esc(x.target)}" data-analysis-jump="${esc(x.target)}">Voir les éléments</a></article>`).join('')}</div><p>La durée fusionne les intervalles qui se chevauchent pour un même agent et jour, puis additionne les durées des agents. Un contexte inactif ne prouve pas une perte de travail.</p></section>
  <section class="card panel" id="analytics-coverage"><div class="panel-head"><div><h2>Mes données permettent-elles de conclure ?</h2><p>${esc(cv.note)}</p></div></div><p><strong>${cv.export_days}/${cv.total_days} jour(s) avec export</strong> · ${cv.capture_days} en capture · ${cv.missing_days} sans source</p><p>${esc(d.comparison_note)}</p><details><summary>Voir chaque journée et la couverture précédente</summary><p>Précédente : ${d.previous.coverage?.export_days||0}/${d.previous.coverage?.total_days||0} jour(s) avec export.</p><div class="table-wrap"><table><thead><tr><th>Journée</th><th>Source disponible</th></tr></thead><tbody>${cv.days.map(r=>`<tr><td>${esc(r.day)}</td><td>${labels[r.source]}</td></tr>`).join('')}</tbody></table></div></details><p>Les week-ends sans source restent visibles : le planning des jours travaillés n’est pas encore configuré. Les listes sont plafonnées ; les indicateurs portent sur toute la sélection.</p></section>`;
}
function analyticsOverview(d){const s=d.current.summary,c=d.comparison||{};return `<div class="sup-metrics analytics-tech-metrics">${supportMetric('Incidents techniques',s.incidents,analyticsDeltaText(c.incidents))}${supportMetric('Agents touchés',s.impacted_agents,analyticsDeltaText(c.impacted_agents))}${supportMetric('Durée des signaux sans doublons',supDuration(s.lost_seconds),analyticsDeltaText(c.lost_seconds,'time'))}${supportMetric('Incidents collectifs',s.collective_events,analyticsDeltaText(c.collective_events))}${supportMetric('Déconnexions',s.disconnects,'hors déconnexions > 1 h')}${supportMetric('Contextes inactifs',s.inactive,'intervalle sans contexte exploitable')}${supportMetric('Récurrences',s.recurring_agents,'agents avec le même signal répété')}${supportMetric('Anomalies',s.anomalies,'séparées des statistiques normales')}</div><div class="analytics-diagnostic card"><strong>Lecture du diagnostic</strong><p>Cette vue ne classe pas les agents. Elle cherche surtout les incidents simultanés, les répétitions et les postes touchés afin de distinguer un problème collectif d’un problème local.</p></div>`;}
function analyticsDailyChart(rows){return supBarChart('analytics-days','Incidents par jour','Incidents détectés par jour documenté. Les jours sans source sont listés dans la couverture, pas représentés comme zéro.',(rows||[]).map(r=>({key:r.label,label:r.label.slice(5),value:r.incidents})),n=>String(n));}
function analyticsHourlyChart(rows){return supBarChart('analytics-hours','Heures les plus touchées','Incidents regroupés selon leur heure de début sur la période sélectionnée.',(rows||[]).filter(r=>r.incidents>0).map(r=>({key:r.label,label:r.label,value:r.incidents})),n=>String(n));}
function analyticsCategoryChart(rows){return supBarChart('analytics-types','Types de signaux','Répartition des incidents techniques, sans score de performance.',(rows||[]).map(r=>({key:r.key,label:r.label,value:r.value})),n=>String(n));}
function analyticsRender(d){
  analyticsCurrent=d;const cur=d.current||{};
  $('#analytics-overview').innerHTML=analyticsGuide(d)+analyticsOverview(d)+`<div class="sup-chart-grid analytics-tech-grid">${analyticsCategoryChart(cur.categories)}</div>`;
  $('#analytics-timeline').innerHTML=`<div class="sup-chart-grid analytics-tech-grid">${analyticsDailyChart(cur.daily.filter(r=>(cur.coverage?.days||[]).find(x=>x.day===r.label)?.source!=='missing'))}${analyticsHourlyChart(cur.hourly)}</div><section class="card panel"><div class="panel-head"><div><h2>Lecture des tendances</h2><p>La chronologie détaillée reste dans Support et Détails. Ici, les événements servent uniquement aux tendances, récurrences, comparaisons et regroupements collectifs.</p></div><span>${cur.summary.incidents} événement(s) analysé(s)</span></div></section>`;
  $('#analytics-clusters').innerHTML=`<section class="card panel"><div class="panel-head"><div><h2>Incidents simultanés</h2><p>Au moins ${cur.cluster_min_agents||3} agents touchés dans une fenêtre de ${cur.cluster_window||180} secondes. Ces regroupements suggèrent une cause partagée à investiguer avant de traiter les postes séparément.</p></div><span>${(cur.clusters||[]).length} groupe(s)</span></div>${(cur.clusters||[]).map(x=>`<article class="analytics-cluster"><div><strong>${esc(x.start_text)}</strong><span>${x.agent_count} agents · ${x.incident_count} incidents</span></div><p>${(x.categories||[]).map(c=>`${esc(c.label)} : <b>${c.value}</b>`).join(' · ')}</p><small>Groupes : ${esc((x.groups||[]).join(', ')||'non renseigné')}${x.pcs?.length?' · PC : '+esc(x.pcs.join(', ')):''}</small></article>`).join('')||'<p class="empty">Aucun incident collectif détecté avec ces critères.</p>'}</section>`;
  $('#analytics-recurrence').innerHTML=`<section class="card panel"><div class="panel-head"><div><h2>Incidents récurrents</h2><p>Même type de problème observé plusieurs fois sur le même agent/poste. Ce tableau sert à repérer les problèmes locaux persistants.</p></div><span>${(cur.recurrence||[]).length} récurrence(s)</span></div><div class="table-wrap"><table><thead><tr><th>Agent / PC</th><th>Signal</th><th>Occurrences</th><th>Jours touchés</th><th>Temps cumulé</th><th>Max</th><th>Collectifs</th><th>Dernier</th></tr></thead><tbody>${(cur.recurrence||[]).map(r=>`<tr><td><strong>${esc(r.name||r.agent)}</strong><small class="sub">${esc(r.agent)}${r.pc?' · '+esc(r.pc):''}</small></td><td>${analyticsCategoryBadge(r.category,r.label)}</td><td><strong>${r.count}</strong></td><td>${r.days_affected}</td><td>${supDuration(r.lost_seconds)}</td><td>${supDuration(r.max_seconds)}</td><td>${r.collective}</td><td>${esc(r.last_text)}</td></tr>`).join('')||'<tr><td colspan="8" class="empty">Aucune récurrence détectée.</td></tr>'}</tbody></table></div></section>`;
  $('#analytics-agents').innerHTML=`<section class="card panel"><div class="panel-head"><div><h2>Concentration par agent / poste</h2><p>Vue analytique par agent. PC et IP : dernière affectation connue, à confirmer pour la date de l’incident.</p></div><span>${(cur.agents||[]).length} agent(s)</span></div><div class="table-wrap"><table><thead><tr><th>Agent</th><th>PC</th><th>Groupe</th><th>Incidents</th><th>Déconnexions</th><th>Inactif</th><th>Autres signaux</th><th>Temps identifié</th><th>Collectifs</th><th>Dernier incident</th></tr></thead><tbody>${(cur.agents||[]).map(r=>`<tr><td><button type="button" class="button ghost" data-analytics-agent="${esc(r.agent)}">${esc(r.name||r.agent)}</button><small class="sub">${esc(r.agent)}</small></td><td>${esc(r.pc||'—')}<small class="sub">${esc(r.ip||'')}</small></td><td>${esc(r.group_name||'Non affecté')}</td><td><strong>${r.incidents}</strong></td><td>${r.offline}</td><td>${r.inactive}</td><td>${r.technical}</td><td>${supDuration(r.lost_seconds)}</td><td>${r.collective}</td><td>${esc(r.last_text||'—')}</td></tr>`).join('')||'<tr><td colspan="10" class="empty">Aucune concentration détectée.</td></tr>'}</tbody></table></div></section>`;
  $('#analytics-periods').innerHTML=`<div class="analytics-period-grid"><article class="card analytics-period a"><span>PÉRIODE ANALYSÉE</span><strong>${esc(cur.date_from)} → ${esc(cur.date_to)}</strong><div><b>${cur.summary.incidents}</b> incidents · <b>${cur.summary.impacted_agents}</b> agents · <b>${supDuration(cur.summary.lost_seconds)}</b> identifié</div></article><article class="card analytics-period b"><span>PÉRIODE PRÉCÉDENTE</span><strong>${esc(d.previous.date_from)} → ${esc(d.previous.date_to)}</strong><div><b>${d.previous.summary.incidents}</b> incidents · <b>${d.previous.summary.impacted_agents}</b> agents · <b>${supDuration(d.previous.summary.lost_seconds)}</b> identifié</div></article></div><section class="card panel"><div class="panel-head"><div><h2>Évolution technique</h2><p>${esc(d.comparison_note||'Comparaison descriptive avec la période précédente de même durée.')}</p></div></div><div class="analytics-compare-list">${[['Incidents','incidents',''],['Temps identifié','lost_seconds','time'],['Agents touchés','impacted_agents',''],['Déconnexions','disconnects',''],['Contextes inactifs','inactive',''],['Incidents collectifs','collective_events',''],['Anomalies','anomalies','']].map(x=>`<div><span>${x[0]}</span><strong>${x[2]==='time'?supDuration(d.comparison[x[1]].current):d.comparison[x[1]].current}</strong><small>${analyticsDeltaText(d.comparison[x[1]],x[2])}</small></div>`).join('')}</div></section>`;
  const trendRows=(d.agent_trends||[]).filter(r=>Number(r.current_incidents||0)||Number(r.previous_incidents||0)).slice(0,200);
  $('#analytics-agent-trends').innerHTML=`<section class="card panel analytics-agent-trends"><div class="panel-head"><div><h2>Variations techniques par agent / poste</h2><p>Comparaison descriptive entre la période actuelle et la période précédente de même durée. Cette vue mesure uniquement les incidents techniques et le temps identifié ; ce n’est pas un classement de productivité.</p></div><span>${trendRows.length} ligne(s)</span></div><div class="table-wrap"><table><thead><tr><th>Agent / poste</th><th>Groupe</th><th>Incidents actuels</th><th>Avant</th><th>Écart</th><th>Temps actuel</th><th>Avant</th><th>Écart temps</th><th>Lecture</th></tr></thead><tbody>${trendRows.map(r=>`<tr><td><button type="button" class="button ghost" data-analytics-agent="${esc(r.agent)}">${esc(r.name||r.agent)}</button><small class="sub">${esc(r.agent)}${r.pc?' · '+esc(r.pc):''}</small></td><td>${esc(r.group_name||'Non affecté')}</td><td><strong>${Number(r.current_incidents||0)}</strong></td><td>${Number(r.previous_incidents||0)}</td><td><strong>${Number(r.delta_incidents||0)>0?'+':''}${Number(r.delta_incidents||0)}</strong></td><td>${supDuration(r.current_lost_seconds||0)}</td><td>${supDuration(r.previous_lost_seconds||0)}</td><td>${analyticsSignedDuration(r.delta_lost_seconds||0)}</td><td><span class="analytics-trend ${esc(r.status||'stable')}">${esc(analyticsTrendStatus(r.status))}</span></td></tr>`).join('')||'<tr><td colspan="9" class="empty">Aucune variation technique mesurable.</td></tr>'}</tbody></table></div></section>`;
  $('#analytics-anomalies').innerHTML=`<section class="card panel"><div class="panel-head"><div><h2>Anomalies séparées</h2><p>Les déconnexions supérieures à 1 heure restent visibles ici mais sont exclues des statistiques normales pour éviter de fausser le diagnostic.</p></div><span>${(cur.anomalies||[]).length} anomalie(s)</span></div><div class="table-wrap"><table><thead><tr><th>Début</th><th>Agent / PC</th><th>Durée</th><th>Groupe</th><th>Raison</th></tr></thead><tbody>${(cur.anomalies||[]).map(r=>`<tr><td>${esc(r.start_text)}</td><td><strong>${esc(r.name||r.agent)}</strong><small class="sub">${esc(r.agent||'')}${r.pc?' · '+esc(r.pc):''}</small></td><td><strong>${supDuration(r.seconds||0)}</strong></td><td>${esc(r.group_name||'Non affecté')}</td><td>${esc(r.reason||'Déconnexion supérieure à 1 heure')}<small class="sub">${esc(r.detail||'')}</small></td></tr>`).join('')||'<tr><td colspan="5" class="empty">Aucune anomalie sur cette période.</td></tr>'}</tbody></table></div></section>`;
  $$('[data-analysis-jump]').forEach(a=>a.onclick=e=>{e.preventDefault();document.getElementById(a.dataset.analysisJump)?.scrollIntoView({behavior:'smooth',block:'start'});});
  $$('[data-analytics-agent]').forEach(btn=>btn.onclick=()=>{const f=$('#analytics-filters');f.elements.agent.value=btn.dataset.analyticsAgent;analyticsLoad();window.scrollTo({top:0,behavior:'smooth'});});
}
async function analyticsLoad(){
  if(location.hash!=='#analytics'||!currentUser)return;const request=++analyticsRequest;try{$('#analytics-message').textContent='Analyse technique en cours…';const q=new URLSearchParams(new FormData($('#analytics-filters'))),d=await api('/api/supervision/analytics?'+q);if(request!==analyticsRequest||location.hash!=='#analytics')return;$('#analytics-message').innerHTML='';analyticsRender(d);}catch(e){if(request===analyticsRequest)$('#analytics-message').innerHTML=flash(e.message,'error');}
}
function analyticsExport(){const d=analyticsCurrent;if(!d)return;const lines=[['Diagnostic technique Nelyio'],['Période',d.current.date_from,d.current.date_to],['Portée','Export des événements affichés',d.current.incidents.length,'sur',d.current.summary.incidents],['Postes','Dernière affectation connue, non historique'],[],['Date/heure','Agent','ID','PC','Groupe','Type','Durée (s)','Collectif','Source','Détail']];(d.current.incidents||[]).forEach(r=>lines.push([r.start_text,r.name,r.agent,r.pc||'',r.group_name||'',r.label,r.duration||0,r.collective?'Oui':'Non',r.source||'',r.detail||'']));const cell=v=>'"'+String(v??'').replace(/"/g,'""')+'"',blob=new Blob(['\ufeff'+lines.map(r=>r.map(cell).join(';')).join('\r\n')],{type:'text/csv;charset=utf-8'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=`Nelyio_diagnostic_technique_${d.current.date_from}_${d.current.date_to}.csv`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
async function analyticsView(){
  clearTimeout(supTimer);analyticsRequest++;activate('analytics');setHead('Analyse & tendances Nelyio','Évolution, récurrence, simultanéité et comparaison des incidents techniques.');
  const info=await api('/api/supervision/analytics');if(location.hash!=='#analytics')return;analyticsCurrent=info;
  const groups=(info.admin_groups||[]).map(g=>`<option value="${g.id}">${esc(g.name)}</option>`).join('');
  app.innerHTML=`<section class="sup-hero analytics-tech-hero"><div><span class="sup-eyebrow">ANALYSE & TENDANCES · NELYIO</span><h2>Comprendre comment les incidents évoluent et où ils se concentrent.</h2><p>Cette vue complète Support sans le dupliquer : comparaison de périodes, simultanéité, récurrence, distributions et tendances techniques.</p></div><button type="button" class="button ghost" id="analytics-export">Exporter les événements d’analyse</button></section>
  <form id="analytics-filters" class="card sup-filters analytics-filters">${nelyioCommonFilterFields(info,'analytics')}<label>Fenêtre simultanée<select name="cluster_window"><option value="60">1 minute</option><option value="120">2 minutes</option><option value="180" selected>3 minutes</option><option value="300">5 minutes</option></select></label><label>Agents minimum<select name="cluster_min_agents"><option value="2">2 agents</option><option value="3" selected>3 agents</option><option value="5">5 agents</option><option value="10">10 agents</option></select></label><div class="sup-toolbar analytics-actions"><button class="button">Analyser</button><button type="button" class="button ghost" id="analytics-reset">Réinitialiser</button></div></form>
  <div id="analytics-message" role="status"></div><section id="analytics-overview"></section><section id="analytics-timeline"></section><section id="analytics-clusters"></section><section id="analytics-recurrence"></section><section id="analytics-agents"></section><section id="analytics-periods"></section><section id="analytics-agent-trends"></section><section id="analytics-anomalies"></section>`;
  const f=$('#analytics-filters');f.elements.cluster_window.value=info.filters.cluster_window||'180';f.elements.cluster_min_agents.value=info.filters.cluster_min_agents||'3';f.onsubmit=e=>{e.preventDefault();analyticsLoad();};$('#analytics-export').onclick=analyticsExport;$('#analytics-reset').onclick=()=>{f.reset();f.elements.date_from.value=info.filters.date_from;f.elements.date_to.value=info.filters.date_to;analyticsLoad();};analyticsRender(info);
}


let detailsPage=0,detailsCurrent=null,detailsRequest=0,detailsMeta=null,detailsRows=new Map();
function detailsSelectedAgents(){return $$('#details-agent-list input[type="checkbox"]:checked').map(x=>x.value);}
function detailsUpdateAgentLabel(available){
  const selected=detailsSelectedAgents(),el=$('#details-agent-summary');if(!el)return;
  el.textContent=selected.length?`Agents · ${selected.length} sélectionné(s)`:`Agents · Tous`;
  const count=$('#details-agent-count');if(count)count.textContent=`${available??0} disponible(s)`;
}
function detailsAgentOptions(){
  if(!detailsMeta)return;const group=$('#details-group')?.value||'',client=$('#details-client')?.value||'',term=($('#details-agent-search')?.value||'').trim().toLowerCase(),selected=new Set(detailsSelectedAgents());
  const rows=(detailsMeta.available_agents||[]).filter(a=>(!group||(a.group_ids||[a.group_id]).some(id=>String(id||'')===group))&&(!client||(a.clients||[]).some(c=>String(c).toLowerCase()===client.toLowerCase()))&&(!term||(`${a.name} ${a.agent} ${a.pc||''}`).toLowerCase().includes(term)));
  $('#details-agent-list').innerHTML=rows.map(a=>`<label class="details-agent-item"><input type="checkbox" name="agent" value="${esc(a.agent)}" ${selected.has(String(a.agent))?'checked':''}><span><strong>${esc(a.name||a.agent)}</strong><small>${esc(a.agent)}${a.group_name?' · '+esc(a.group_name):''}${a.pc?' · '+esc(a.pc):''}</small></span></label>`).join('')||'<div class="empty">Aucun agent.</div>';
  detailsUpdateAgentLabel(rows.length);$$('#details-agent-list input').forEach(x=>x.onchange=()=>detailsUpdateAgentLabel(rows.length));
}
function detailsQuery(){const q=new URLSearchParams();const f=$('#details-filters');q.set('day',f.elements.day.value);q.set('group',f.elements.group.value);q.set('client',f.elements.client.value);q.set('source',f.elements.source.value);q.set('q',f.elements.q.value);q.set('page',detailsPage);q.set('page_size','100');detailsSelectedAgents().forEach(a=>q.append('agent',a));return q;}
function detailsSourceBadge(r){const cls=r.source==='export'?'export':r.source==='capture'?'capture':r.source==='call'?'call':'signal';return `<span class="details-source ${cls}">${esc(r.source_label)}</span>`;}
function detailsOpenLog(r){
  const dlg=$('#details-log-dialog');if(!dlg)return;
  $('#details-dialog-title').textContent=`${r.source_label||'Log'} · ${(r.time_text||'').slice(11)}`;
  $('#details-dialog-fields').innerHTML=Object.entries(r.fields||{}).map(([k,v])=>`<div class="details-field"><dt>${esc(k)}</dt><dd>${v===null||v===undefined||v===''?'—':esc(String(v))}</dd></div>`).join('');
  if(dlg.showModal){if(!dlg.open)dlg.showModal();}else dlg.setAttribute('open','');
}
function detailsRender(d){
  if(d.details_db?.sync_pending)$('#details-message').textContent='Synchronisation en cours · dernières données validées affichées.';
  detailsCurrent=d;detailsRows=new Map((d.rows||[]).map(r=>[String(r.log_id),r]));
  $('#details-count').textContent=`${d.total.toLocaleString('fr-FR')} logs`;
  $('#details-body').innerHTML=(d.rows||[]).map(r=>`<tr class="details-log-row" tabindex="0" data-details-log="${esc(r.log_id)}"><td><strong>${esc((r.time_text||'').slice(11))}</strong></td><td><strong>${esc(r.name||r.agent||'Collecte')}</strong><small>${esc(r.agent||'—')}${r.pc?' · '+esc(r.pc):''}</small></td><td>${esc(r.group_name||'—')}</td><td>${esc(r.client||'—')}</td><td>${detailsSourceBadge(r)}</td><td><strong>${esc(r.state||r.log_type||'—')}</strong><small>${esc(r.log_type||'')}</small></td><td>${r.duration?supDuration(r.duration):'—'}</td></tr>`).join('')||`<tr><td colspan="7" class="empty">${$('#details-filters')?.elements.source.value==='export'?'Aucun événement SIMPLIFY2 pour cette sélection. Les autres sources restent accessibles dans le filtre Source.':'Aucun log pour cette sélection.'}</td></tr>`;
  $$('.details-log-row').forEach(row=>{const open=()=>detailsOpenLog(detailsRows.get(String(row.dataset.detailsLog)));row.onclick=open;row.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();open();}};});
  $('#details-page').textContent=`${d.page+1} / ${d.pages}`;$('#details-prev').disabled=d.page<=0;$('#details-next').disabled=d.page+1>=d.pages;
}
async function detailsLoad(refreshMeta=false){
  if(location.hash.split('?')[0]!=='#details'||!currentUser)return;const req=++detailsRequest;$('#details-message').textContent='Chargement…';
  try{const d=await api('/api/supervision/details?'+detailsQuery());if(req!==detailsRequest||location.hash.split('?')[0]!=='#details')return;if(refreshMeta){detailsMeta=d;const f=$('#details-filters'),oldGroup=f.elements.group.value,oldClient=f.elements.client.value;f.elements.group.innerHTML='<option value="">Tous</option>'+(d.admin_groups||[]).map(g=>`<option value="${g.id}">${esc(g.name)}</option>`).join('');f.elements.client.innerHTML='<option value="">Tous</option>'+(d.available_clients||[]).map(c=>`<option value="${esc(c)}">${esc(c)}</option>`).join('');f.elements.group.value=oldGroup;f.elements.client.value=oldClient;detailsAgentOptions();}$('#details-message').textContent='';detailsRender(d);}catch(e){if(req===detailsRequest&&$('#details-message'))$('#details-message').innerHTML=flash(e.message,'error');}
}
async function detailsView(){
  clearTimeout(supTimer);detailsPage=0;detailsRequest++;activate('details');setHead('Détails','Logs bruts Nelyio.');
  const viewTicket=captureViewTicket();const initialFilters=new URLSearchParams(location.hash.split('?')[1]||collectionDayQuery('details'));initialFilters.delete('page');
  // Default is a UI choice, not an API restriction. An explicit source (including
  // source= for all sources) from a link remains the user's requested selection.
  if(!initialFilters.has('source')||!['','export','capture','signal','call'].includes(initialFilters.get('source'))){initialFilters.set('source','export');}
  const info=await api('/api/supervision/details?'+initialFilters);if(!viewTicketIsCurrent(viewTicket))return;if(location.hash.split('?')[0]!=='#details')return;detailsMeta=info;
  app.innerHTML=`<section class="details-minimal"><div class="details-minimal-head"><h2>Détails</h2><span id="details-count"></span></div>
  <form id="details-filters" class="details-minimal-filters"><label>Jour<input type="date" name="day" value="${esc(info.day)}" required></label><label>Groupe<select name="group" id="details-group"><option value="">Tous</option>${(info.admin_groups||[]).map(g=>`<option value="${g.id}">${esc(g.name)}</option>`).join('')}</select></label>
  <div class="details-agent-filter"><details id="details-agent-dropdown"><summary id="details-agent-summary">Agents · Tous</summary><div class="details-agent-popover"><input id="details-agent-search" placeholder="Rechercher agent ou PC"><div class="details-agent-popover-head"><span id="details-agent-count"></span><button type="button" class="details-text-button" id="details-clear-agents">Tout effacer</button></div><div id="details-agent-list" class="details-agent-list"></div></div></details></div>
  <label>Client<select name="client" id="details-client"><option value="">Tous</option>${(info.available_clients||[]).map(c=>`<option value="${esc(c)}">${esc(c)}</option>`).join('')}</select></label><label>Source<select name="source"><option value="export" selected>SIMPLIFY2</option><option value="">Toutes les sources</option><option value="capture">Capture</option><option value="signal">Signaux techniques</option><option value="call">Appels</option></select></label><label class="details-search">Recherche<input name="q" placeholder="État, session, ANI, DNIS, PC…"></label><button class="button details-apply">Afficher</button><button type="button" class="details-text-button details-reset" id="details-reset">Réinitialiser</button></form>
  <div id="details-message" role="status"></div><div class="details-table-shell"><div class="details-table-wrap"><table class="details-table"><thead><tr><th>Heure</th><th>Agent / PC</th><th>Groupe</th><th>Client</th><th>Source</th><th>Événement</th><th>Durée</th></tr></thead><tbody id="details-body"></tbody></table></div><div class="details-pager"><button type="button" class="details-text-button" id="details-prev">← Précédent</button><span id="details-page"></span><button type="button" class="details-text-button" id="details-next">Suivant →</button></div></div>
  <dialog id="details-log-dialog" class="details-log-dialog"><div class="details-dialog-head"><h3 id="details-dialog-title">Détail du log</h3><button type="button" class="details-dialog-close" id="details-dialog-close" aria-label="Fermer">×</button></div><dl id="details-dialog-fields" class="details-dialog-fields"></dl></dialog></section>`;
  const f=$('#details-filters');for(const key of ['day','group','client','source','q']){if(initialFilters.has(key)&&f.elements[key])f.elements[key].value=initialFilters.get(key);}
  detailsAgentOptions();const initialAgents=[...initialFilters.getAll('agent'),...initialFilters.getAll('include_agent')];if(initialAgents.length){$$('#details-agent-list input').forEach(x=>x.checked=initialAgents.includes(x.value));detailsUpdateAgentLabel($$('#details-agent-list input').length);}
  f.onsubmit=e=>{e.preventDefault();detailsPage=0;detailsLoad();};
  f.elements.day.onchange=async()=>{detailsPage=0;f.elements.client.value='';$$('#details-agent-list input').forEach(x=>x.checked=false);await detailsLoad(true);};
  f.elements.group.onchange=()=>{detailsPage=0;$$('#details-agent-list input').forEach(x=>x.checked=false);detailsAgentOptions();};f.elements.client.onchange=()=>{detailsPage=0;$$('#details-agent-list input').forEach(x=>x.checked=false);detailsAgentOptions();};
  $('#details-agent-search').oninput=detailsAgentOptions;$('#details-clear-agents').onclick=()=>{$$('#details-agent-list input').forEach(x=>x.checked=false);detailsAgentOptions();};
  $('#details-reset').onclick=()=>{f.reset();f.elements.source.value='export';f.elements.day.value=info.day;detailsPage=0;detailsMeta=info;detailsAgentOptions();detailsLoad();};
  $('#details-prev').onclick=()=>{detailsPage=Math.max(0,detailsPage-1);detailsLoad();};$('#details-next').onclick=()=>{detailsPage++;detailsLoad();};$('#details-dialog-close').onclick=()=>$('#details-log-dialog').close();detailsRender(info);
}

let disconnectDetailsPage=0,disconnectDetailsCurrent=null,disconnectDetailsRequest=0,disconnectDetailsMeta=null,disconnectDetailsRows=new Map();
function disconnectDetailsHashParams(){const raw=String(location.hash||'');const i=raw.indexOf('?');return new URLSearchParams(i>=0?raw.slice(i+1):'');}
function disconnectDetailsQuery(){const q=new URLSearchParams(new FormData($('#disconnect-details-filters')));q.set('page',disconnectDetailsPage);q.set('page_size','25');q.set('sort',$('[name="detail_sort"]:checked')?.value||'date');return q;}
function disconnectDetailsCauseBadge(r){return r.during_call?'<span class="diag-call-badge during">Pendant appel</span>':'<span class="diag-call-badge outside">Hors appel</span>';}
async function disconnectDetailsOpenIncident(r){
  const dlg=$('#disconnect-details-log-dialog');if(!dlg||!r)return;
  const hp=new URLSearchParams(new FormData($('#disconnect-details-filters')));hp.set('incident',String(r.incident_id||''));history.replaceState(null,'','#disconnect-details?'+hp.toString());
  $('#disconnect-details-dialog-title').textContent=`${r.name||r.agent} · ${r.start_text||''}`;
  const items=[['Agent',`${r.name||r.agent} · ${r.agent||''}`],['Groupe',r.group_name||'Non affecté'],['Début',r.start_text],['Fin',r.end_text],['Durée',supDuration(r.seconds||0)],['Contexte',r.during_call?'Pendant appel':'Hors appel'],['Classification',r.event_label],['Cause / lecture',r.cause],['Justification',r.classification_reason],['Source',supportSourceName(r.source)],['Policy',r.policy_applied?r.policy_reason:'—'],['Déclaration',r.declaration_applied?r.declaration_reason:'—'],['Appel associé',r.call_id?`${r.call_id}${r.indice?' · indice '+r.indice:''}`:'—']];
  $('#disconnect-details-dialog-fields').innerHTML=items.map(([k,v])=>`<div class="details-field"><dt>${esc(k)}</dt><dd>${esc(v||'—')}</dd></div>`).join('')+`<div class="details-evidence" id="disconnect-details-evidence"><h4>Logs détaillés liés à cette coupure</h4><p class="sub">Recherche des logs SIMPLIFY2 autour de cette coupure…</p></div>`;
  if(dlg.showModal&&!dlg.open)dlg.showModal();else dlg.setAttribute('open','');
  try{
    const q=new URLSearchParams({agent:r.agent||'',start:String(r.start||0),end:String(r.end||r.start||0),source:'export'}),d=await api('/api/supervision/incident-evidence?'+q),host=$('#disconnect-details-evidence');if(!host)return;
    const rows=d.rows||[];
    host.innerHTML=`<h4>Logs détaillés liés à cette coupure</h4>${rows.length?`<p class="sub">${rows.length} log(s) SIMPLIFY2. Ouvrez une ligne pour voir les champs source.</p><div class="details-evidence-list">${rows.map(x=>`<details class="details-evidence-row"><summary><strong>${esc(x.time_text||'—')}</strong><span>${esc(x.source_label||x.source||'Log')}</span><span>${esc(x.state||x.kind||x.log_type||'—')}</span><span>${x.duration?supDuration(x.duration):'—'}</span></summary><dl>${Object.entries(x.fields||{}).map(([k,v])=>`<div class="details-field"><dt>${esc(k)}</dt><dd>${v===null||v===undefined||v===''?'—':esc(String(v))}</dd></div>`).join('')}</dl></details>`).join('')}</div>`:'<p class="empty">Aucun log SIMPLIFY2 lié trouvé dans la fenêtre ±90 s. Les autres sources ne sont pas affichées dans ce bloc.</p>'}`;
  }catch(e){const host=$('#disconnect-details-evidence');if(host)host.innerHTML=`<h4>Logs détaillés liés à cette coupure</h4>${flash(e.message,'error')}`;}
}
function disconnectDetailsRender(d){
  disconnectDetailsCurrent=d;disconnectDetailsRows=new Map((d.rows||[]).map(r=>[String(r.incident_id),r]));$('#disconnect-details-count').textContent=`${d.total.toLocaleString('fr-FR')} incident(s)`;
  $('#disconnect-details-body').innerHTML=(d.rows||[]).map(r=>`<tr class="details-log-row" tabindex="0" data-details-log="${esc(r.incident_id)}"><td><strong>${esc(r.start_text||'—')}</strong></td><td><strong>${esc(r.name||r.agent||'—')}</strong><small>${esc(r.agent||'—')}</small></td><td><strong>${supDuration(r.seconds||0)}</strong></td><td>${disconnectDetailsCauseBadge(r)}</td><td><strong>${esc(r.cause||r.event_label||'À qualifier')}</strong>${r.governance_exclude_statistics?'<small>Exclu des KPI par gouvernance</small>':''}</td><td><span class="diag-row-open">›</span></td></tr>`).join('')||'<tr><td colspan="6" class="empty">Aucun incident pour cette sélection.</td></tr>';
  $$('.details-log-row').forEach(row=>{const open=()=>disconnectDetailsOpenIncident(disconnectDetailsRows.get(String(row.dataset.detailsLog)));row.onclick=open;row.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();open();}};});
  const wanted=disconnectDetailsHashParams().get('incident');if(wanted&&disconnectDetailsRows.has(wanted)){const row=document.querySelector(`[data-details-log="${CSS.escape(wanted)}"]`);if(row)row.classList.add('details-linked-highlight');setTimeout(()=>disconnectDetailsOpenIncident(disconnectDetailsRows.get(wanted)),0);}
  $('#disconnect-details-page').textContent=`${d.page+1} / ${d.pages}`;$('#disconnect-details-prev').disabled=d.page<=0;$('#disconnect-details-next').disabled=d.page+1>=d.pages;
}
async function disconnectDetailsLoad(refreshMeta=false){
  if(!String(location.hash).startsWith('#disconnect-details')||!currentUser)return;const req=++disconnectDetailsRequest;$('#disconnect-details-message').textContent='Chargement…';
  try{const d=await api('/api/supervision/diagnostic-incidents?'+disconnectDetailsQuery());if(req!==disconnectDetailsRequest||!String(location.hash).startsWith('#disconnect-details'))return;disconnectDetailsMeta=d;$('#disconnect-details-message').textContent='';disconnectDetailsRender(d);}catch(e){if(req===disconnectDetailsRequest)$('#disconnect-details-message').innerHTML=flash(e.message,'error');}
}
async function disconnectDetailsExport(){
  const base=disconnectDetailsQuery();base.set('page_size','100');base.set('page','0');const first=await api('/api/supervision/diagnostic-incidents?'+base),rows=[...(first.rows||[])];for(let p=1;p<Math.min(first.pages||1,100);p++){base.set('page',String(p));const next=await api('/api/supervision/diagnostic-incidents?'+base);rows.push(...(next.rows||[]));}
  const lines=[['Date / heure','Agent','Identifiant','Durée (s)','Contexte','Cause probable','Groupe','Source'],...rows.map(r=>[r.start_text,r.name,r.agent,r.seconds,r.during_call?'Pendant appel':'Hors appel',r.cause,r.group_name,supportSourceName(r.source)])],cell=v=>'"'+String(v??'').replace(/"/g,'""')+'"',blob=new Blob(['\ufeff'+lines.map(r=>r.map(cell).join(';')).join('\r\n')],{type:'text/csv;charset=utf-8'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=`Nelyio_incidents_${first.date_from}_${first.date_to}.csv`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
async function disconnectDetailsView(){
  clearTimeout(supTimer);disconnectDetailsPage=0;disconnectDetailsRequest++;activate('disconnect-details');setHead('Détails des coupures','Incidents techniques individuels, séparés des logs bruts.');
  const hp=disconnectDetailsHashParams(),initial=new URLSearchParams(hp);initial.set('page','0');initial.set('page_size','25');const info=await api('/api/supervision/diagnostic-incidents?'+initial);if(!String(location.hash).startsWith('#disconnect-details'))return;disconnectDetailsMeta=info;
  const f=info.common_filters||{},groups=(info.admin_groups||[]).map(g=>`<option value="${esc(g.id)}" ${String(g.id)===String(f.group||'')?'selected':''}>${esc(g.name)}</option>`).join(''),agents=(info.available_agents||[]).map(r=>`<option value="${esc(r.agent)}">${esc(r.name||r.agent)}${(r.group_names&&r.group_names.length)?' · '+esc(r.group_names.join(' / ')):(r.group_name?' · '+esc(r.group_name):'')}</option>`).join('');
  app.innerHTML=`<section class="diag-workspace">${diagnosticPageHeader('Détails des coupures','Consultez les incidents techniques individuellement, séparément des logs bruts Nelyio.')}${diagnosticInfoBanner('Chaque ligne représente un incident technique individuel. Cliquez sur une ligne pour ouvrir sa justification complète.')}
  <form id="disconnect-details-filters" class="diag-details-controls"><label class="diag-details-agent">Agent<input name="agent" list="disconnect-details-agent-list" value="${esc(f.agent||'')}" placeholder="Tous les agents"><datalist id="disconnect-details-agent-list">${agents}</datalist></label><details class="diag-more-filters"><summary>Filtres</summary><div class="diag-advanced-grid"><label>Du<input type="date" name="date_from" value="${esc(f.date_from||info.date_from)}"></label><label>Au<input type="date" name="date_to" value="${esc(f.date_to||info.date_to)}"></label><label>Groupe<select name="group"><option value="">Tous les groupes</option>${groups}</select></label><label>Heure début<input type="time" name="time_from" value="${esc(f.time_from||'00:00')}"></label><label>Heure fin<input type="time" name="time_to" value="${esc((f.time_to==='24:00'?'23:59':(f.time_to||'23:59')))}"></label><label>Durée minimum<select name="min_disconnect"><option value="0">Toutes</option><option value="10" ${Number(f.min_disconnect)===10?'selected':''}>≥ 10 s</option><option value="20" ${Number(f.min_disconnect)===20?'selected':''}>≥ 20 s</option><option value="60" ${Number(f.min_disconnect)===60?'selected':''}>≥ 1 min</option><option value="300" ${Number(f.min_disconnect)===300?'selected':''}>≥ 5 min</option></select></label><label>Contexte<select name="call_scope"><option value="all">Tous</option><option value="during" ${f.call_scope==='during'?'selected':''}>Pendant appel</option><option value="outside" ${f.call_scope==='outside'?'selected':''}>Hors appel</option></select></label></div></details><button class="diag-apply">Afficher</button><button type="button" class="diag-reset" id="disconnect-details-reset">Réinitialiser</button><button type="button" class="diag-export" id="disconnect-details-export">Exporter</button></form>
  <div id="disconnect-details-message" class="diag-message" role="status"></div><section class="diag-table-card diag-incidents-card"><div class="diag-table-head"><div><h3>Détails des coupures</h3><p>Chaque ligne est une coupure individuelle.</p></div><div class="diag-sort-toggle"><label><input type="radio" name="detail_sort" value="date" checked> Par date/heure</label><label><input type="radio" name="detail_sort" value="duration"> Par durée</label></div></div><div class="diag-table-wrap"><table><thead><tr><th>Date / heure</th><th>Agent</th><th>Durée</th><th>Pendant appel</th><th>Cause probable</th><th></th></tr></thead><tbody id="disconnect-details-body"></tbody></table></div><div class="diag-table-footer"><span id="disconnect-details-count"></span><div class="diag-pager"><button type="button" id="disconnect-details-prev">‹</button><span id="disconnect-details-page"></span><button type="button" id="disconnect-details-next">›</button></div></div></section><dialog id="disconnect-details-log-dialog" class="details-log-dialog diag-incident-dialog"><div class="details-dialog-head"><h3 id="disconnect-details-dialog-title">Détail de l’incident</h3><button type="button" class="details-dialog-close" id="disconnect-details-dialog-close" aria-label="Fermer">×</button></div><dl id="disconnect-details-dialog-fields" class="details-dialog-fields"></dl></dialog></section>`;
  const form=$('#disconnect-details-filters');form.onsubmit=e=>{e.preventDefault();disconnectDetailsPage=0;disconnectDetailsLoad();};form.elements.agent.onchange=()=>{disconnectDetailsPage=0;disconnectDetailsLoad();};document.querySelectorAll('[name="detail_sort"]').forEach(r=>r.onchange=()=>{disconnectDetailsPage=0;disconnectDetailsLoad();});
  $('#disconnect-details-reset').onclick=()=>{form.reset();disconnectDetailsPage=0;history.replaceState(null,'','#disconnect-details');disconnectDetailsLoad();};$('#disconnect-details-export').onclick=()=>disconnectDetailsExport();$('#disconnect-details-prev').onclick=()=>{disconnectDetailsPage=Math.max(0,disconnectDetailsPage-1);disconnectDetailsLoad();};$('#disconnect-details-next').onclick=()=>{disconnectDetailsPage++;disconnectDetailsLoad();};$('#disconnect-details-dialog-close').onclick=()=>{const dlg=$('#disconnect-details-log-dialog');dlg.close();const hp=disconnectDetailsHashParams();hp.delete('incident');history.replaceState(null,'','#disconnect-details'+(hp.toString()?'?'+hp.toString():''));};disconnectDetailsRender(info);
}

let callsPage=0,callsCurrent=null,callsRequest=0;
let callsSortState={key:'',direction:'default'};
try{const v=JSON.parse(sessionStorage.getItem('nelyio.rc29.calls.sort')||'null');if(v&&['asc','desc'].includes(v.direction))callsSortState=v;}catch(_){}
function callsSortHeader(label,key,type='string',required=false){const active=callsSortState.key===key&&callsSortState.direction!=='default';return `<th ${required?'data-required-column ':''}data-call-sort="${esc(key)}" data-sort-type="${esc(type)}" aria-sort="${active?(callsSortState.direction==='asc'?'ascending':'descending'):'none'}"><button type="button" class="quality-sort-button" data-call-sort-button="${esc(key)}">${esc(label)}${active?(callsSortState.direction==='asc'?' ↑':' ↓'):' ↕'}</button></th>`;}
function callsCycleSort(key){if(callsSortState.key!==key||callsSortState.direction==='default')callsSortState={key,direction:'asc'};else if(callsSortState.direction==='asc')callsSortState={key,direction:'desc'};else callsSortState={key:'',direction:'default'};try{if(callsSortState.key)sessionStorage.setItem('nelyio.rc29.calls.sort',JSON.stringify(callsSortState));else sessionStorage.removeItem('nelyio.rc29.calls.sort');}catch(_){}callsPage=0;callsLoad();}


// Call facts come directly from ODCalls: never infer wait = total - conversation.
function callsFormatDuration(value){
  if(value===null||value===undefined||String(value).trim()==='')return 'Non disponible';
  const seconds=Number(value);
  if(!Number.isFinite(seconds))return 'Non disponible';
  return seconds<0?`Invalide (${seconds} s)`:supDuration(seconds);
}
function callsResultsFocus(){
  document.querySelector('#app button[data-ui-workspace="results"]')?.click();
  document.querySelector('#calls-results')?.classList.remove('ui-panel-collapsed');
}
function callResultRow(r,index){
  const when=callDateTime(r.start_text);
  return `<tr data-call-index="${index}">
    <td data-call-field="when"><strong>${esc(when.date)}</strong><small class="sub">${esc(when.time)}</small></td>
    <td data-call-field="agent">${callAgentCell(r)}</td>
    <td data-call-field="ani"><strong>${esc(r.ani||'Non fourni')}</strong>${r.ani_masked?'<small class="sub">masqué selon vos droits</small>':''}</td>
    <td data-call-field="duration">${esc(callsFormatDuration(r.duration))}</td>
    <td data-call-field="conversation">${esc(callsFormatDuration(r.conversation))}</td>
    <td data-call-field="wait"><strong>${esc(callsFormatDuration(r.wait))}</strong></td>
    <td data-call-field="indice">${esc(r.indice||'\u2014')}</td>
    <td><button type="button" class="button ghost small" data-call-details="${index}" aria-label="D\u00e9tails de l'appel ${esc(r.call_id)}">D\u00e9tails</button></td>
  </tr>`;
}
function callsDetailDialog(){
  return `<dialog id="calls-detail-dialog" class="details-log-dialog" aria-labelledby="calls-detail-title">
    <div class="details-dialog-head"><h3 id="calls-detail-title">D\u00e9tail de l'appel</h3><button type="button" class="details-dialog-close" id="calls-detail-close" aria-label="Fermer">\u00d7</button></div>
    <dl id="calls-detail-fields" class="details-dialog-fields"></dl>
    <div id="calls-detail-notes" class="calls-detail-notes"></div>
    <div class="ui-dialog-actions"><button type="button" class="button" id="calls-detail-note">Qualifier / ajouter une note</button></div>
  </dialog>`;
}
function callsOpenDetail(index){
  const r=callsCurrent?.rows?.[index];if(!r)return;
  const when=callDateTime(r.start_text);
  const agent=(id,name)=>[name,id&&id!=='0'?id:''].filter(Boolean).join(' \u00b7 ')||'Non fourni';
  const boolean=value=>value===null||value===undefined||value===''?'Non disponible':Number(value)?'Oui':'Non';
  const types={'1':'Entrant','2':'Sortant','3':'Manuel','4':'Consultation','5':'Renvoi','6':'Interne'};
  const fields=[
    ['Num\u00e9ro patient (ANI)',(r.ani||'Non fourni dans l\u2019export')+(r.ani_masked?' · masqué selon vos droits':'')],
    ['Date / heure',`${when.date} ${when.time}`],
    ['Dur\u00e9e totale',callsFormatDuration(r.duration)],
    ['Conversation',callsFormatDuration(r.conversation)],
    ['Temps d\u2019attente',callsFormatDuration(r.wait)],
    ['Indice',r.indice],['ID appel',r.call_id],['DNIS / num\u00e9ro appel\u00e9',r.dnis],
    ['Premier agent',agent(r.first_agent,r.first_name)],['Groupe actuel du premier agent',r.first_group_name],
    ['Dernier agent',agent(r.last_agent,r.last_name)],['Groupe actuel du dernier agent',r.last_group_name],
    ['Campagne / SDA',r.campaign],['Type d\u2019appel',types[String(r.call_type)]||r.call_type],
    ['EndReason',r.end_reason],['Num\u00e9ro sortant',r.outtel],['Num\u00e9ro compos\u00e9',r.outdialed],
    ['Abandon d\u00e9clar\u00e9',boolean(r.abandon)],['Sans agent d\u00e9clar\u00e9',boolean(r.no_agent)],
    ['Appel clos',boolean(r.closed)],['Fin par agent',boolean(r.end_by_agent)],
    ['Qualification',r.diagnosis],['Cause',r.cause],['Suivi',r.status],
    ['Source','Export ODCalls (valeurs brutes)']
  ];
  $('#calls-detail-title').textContent='D\u00e9tail de l\u2019appel \u00b7 '+(r.indice||r.call_id);
  $('#calls-detail-fields').innerHTML=fields.map(([key,value])=>`<div class="details-field"><dt>${esc(key)}</dt><dd>${esc(value===null||value===undefined||value===''?'\u2014':value)}</dd></div>`).join('');
  $('#calls-detail-notes').innerHTML=(r.notes||[]).length?'<h4>Notes</h4>'+(r.notes||[]).map(n=>`<p>${esc(n.comment||n.note||n.text||'')}<small class="sub">${esc(n.author||'')} \u00b7 ${esc(n.stamp||'')} \u00b7 ${esc(n.diagnosis||'')} \u00b7 ${esc(n.status||'')}</small></p>`).join(''):'';
  const dialog=$('#calls-detail-dialog'),note=$('#calls-detail-note');
  note.hidden=!canWrite('calls');
  note.onclick=()=>{dialog.close();supNote({...r,state:'Appel \u00b7 indice '+r.indice,agent:r.last_agent||r.first_agent,name:r.last_name||r.first_name});};
  $('#calls-detail-close').onclick=()=>dialog.close();
  dialog.showModal();
}

function callsHashParams(){const raw=String(location.hash||'');const i=raw.indexOf('?');return new URLSearchParams(i>=0?raw.slice(i+1):'');}
function callsImportPanel(){
  if(!canWrite('calls'))return '';
  return `<details class="card panel sup-settings support-import-panel" id="calls-import-panel"><summary>Importer un export SIMPLIFY2</summary><p><strong>V60 :</strong> utiliser <code>OPEN_NELYIO_IMPORTER.bat</code> directement sur le serveur Nelyio. Le nouvel importer accepte plusieurs ZIP/CSV/HAR en une sélection et répare aussi les affectations Agents.csv → files. L'import n'est plus ex&#233;cut&#233; dans cette page afin de garder Recherche d'appels et le login r&#233;actifs.</p><div id="calls-auto-import-status"></div></details>`;
}

let callsObservationPage=0;
async function callsView(){
  callsObservationPage=0;
  clearTimeout(supTimer);callsPage=0;callsRequest++;
  activate('calls');setHead('Recherche d’appels Nelyio','Numéro patient, agent, durée et attente. Détail complet en un clic.');
  const initialQuery=new URLSearchParams(collectionDayQuery('calls'));initialQuery.set('page','0');initialQuery.set('live_page','0');if(callsSortState.key&&callsSortState.direction!=='default'){initialQuery.set('sort',callsSortState.key);initialQuery.set('sort_dir',callsSortState.direction);}
  const info=await api('/api/supervision/calls?'+initialQuery);if(!String(location.hash).startsWith('#calls'))return;
  const hp=callsHashParams(),prefillCall=hp.get('call_id')||'',prefillFrom=hp.get('date_from')||info.date_from,prefillTo=hp.get('date_to')||info.date_to;
  app.innerHTML=`<section class="sup-hero"><div><span class="sup-eyebrow">RECHERCHE APPELS · V56.2</span><h2>Rechercher un ANI, retrouver l’appel.</h2><p>Cette interface est indépendante du support technique. Entre un numéro ANI complet ou partiel pour retrouver l’agent, la date, l’heure et l’indice de l’appel.</p></div>${canWrite('calls')?'<button type="button" class="button ghost" id="calls-import-open">Importer un export</button>':''}</section>
  <form id="calls-filters" class="card sup-filters support-filters"><label>Du<input type="date" name="date_from" value="${esc(prefillFrom)}" required></label><label>Au<input type="date" name="date_to" value="${esc(prefillTo)}" required></label><label>Plage horaire<select id="calls-time-preset"><option value="all">Journée complète</option><option value="work">Plage de travail · ${esc(info.config.work_start)}–${esc(info.config.work_end)}</option><option value="12:00-13:00">12:00 – 13:00</option><option value="13:00-14:00">13:00 – 14:00</option><option value="custom">Personnalisée</option></select></label><label>Heure de début<input type="time" name="time_from" step="60" aria-describedby="calls-time-active"></label><label>Heure de fin<input type="time" name="time_to" step="60" aria-describedby="calls-time-active"></label><input type="hidden" name="full_day" value="1">${canRead('ani')?'<label>ANI · numéro appelant<input name="phone" inputmode="tel" autocomplete="off" placeholder="Numéro complet ou partiel"></label>':'<label>ANI · numéro appelant<input disabled placeholder="Droit Voir ANI complet requis"></label>'}<input type="hidden" name="phone_field" value="ani"><label>Indice exact<input name="indice" inputmode="numeric" placeholder="Indice de l’appel"></label><label>Agent<input name="agent" placeholder="Identifiant ou nom"></label><label>ID d’appel exact<input name="call_id" value="${esc(prefillCall)}" placeholder="Identifiant unique ODCalls"></label><label>Campagne / SDA<input name="campaign" placeholder="Code campagne"></label><label>Code EndReason<input name="reason" placeholder="Ex. -486"></label><label>Type d’appel<select name="call_type"><option value="">Tous</option><option value="1">Entrant</option><option value="2">Sortant</option><option value="3">Manuel</option><option value="4">Consultation</option><option value="5">Renvoi</option><option value="6">Interne</option></select></label><label>Critère d’appel<select name="call_issue"><option value="">Tous</option><option value="end_code">Code de fin non nul</option><option value="short">Conversation &gt;0 et &lt;10 s</option><option value="invalid">Durée incohérente</option><option value="abandon">Abandon déclaré</option><option value="no_agent">Sans agent déclaré</option></select></label><label>Qualification<select name="diagnosis">${supportOptions(supportDiagnoses)}</select></label><label>Suivi<select name="status">${supportOptions(supportStatuses)}</select></label><div class="sup-toolbar"><button class="button">Rechercher</button><button type="button" class="button ghost" id="calls-reset">Réinitialiser</button></div></form>
  <div id="calls-time-active" role="status" class="calls-time-active"></div><div id="calls-message" role="status"></div><div id="calls-coverage"></div><div id="calls-cards"></div><section id="calls-results" class="card panel"><div class="panel-head"><div><h2>Résultats de la recherche</h2><p>Numéro, durée totale, conversation et attente issus de l’export. Les autres informations restent dans Détails.</p></div><div class="calls-result-actions"><span id="calls-count"></span><button type="button" class="button ghost" id="calls-export">Exporter les événements affichés</button><button type="button" class="button ghost" id="calls-refresh">Actualiser</button></div></div><div class="table-wrap"><table id="calls-table" class="calls-results-table"><thead><tr>${callsSortHeader('Date / heure','date','date')}${callsSortHeader('Agent','agent','string')}${callsSortHeader('Numéro patient (ANI)','ani','string',true)}${callsSortHeader('Durée totale','duration','duration',true)}${callsSortHeader('Conversation','conversation','duration',true)}${callsSortHeader('Attente','wait','duration',true)}${callsSortHeader('Indice','indice','string')}<th data-required-column>Détails</th></tr></thead><tbody id="calls-body"></tbody></table></div><div class="sup-pager"><button class="button ghost" id="calls-prev">Précédent</button><span id="calls-page"></span><button class="button ghost" id="calls-next">Suivant</button></div></section>${callsImportPanel()}${callsDetailDialog()}${supportDialog()}`;
  $('#sup-note-cancel').onclick=()=>$('#sup-dialog').close();
  callsBindTimeFilter(info.config,hp);
  $('#calls-filters').onsubmit=e=>{e.preventDefault();if(!callsValidateTime(true))return;callsPage=0;callsObservationPage=0;callsResultsFocus();callsLoad();};
  $('#calls-reset').onclick=()=>{$('#calls-filters').reset();$('#calls-filters').elements.call_id.value='';callsClearTime();callsPage=0;callsObservationPage=0;history.replaceState(null,'','#calls');callsResultsFocus();callsLoad();};
  $('#calls-export').onclick=()=>callsExport();$('#calls-refresh').onclick=()=>callsLoad();
  $('#calls-prev').onclick=()=>{callsPage=Math.max(0,callsPage-1);callsLoad();};$('#calls-next').onclick=()=>{callsPage++;callsLoad();};
  if($('#calls-import-open'))$('#calls-import-open').onclick=()=>{document.querySelector('#app button[data-ui-workspace="import"]')?.click();const d=$('#calls-import-panel');d.open=true;d.scrollIntoView({behavior:'smooth',block:'center'});};
  if($('#calls-import'))$('#calls-import').onsubmit=callsImport;
  supportAutoImportStatus('#calls-auto-import-status','calls');
  callsRender(info,initialQuery);
}

// One daily time window, in the same timezone as the displayed call timestamps.
function callsValidateTime(report=false){
  const form=$('#calls-filters');if(!form)return false;
  const start=form.elements.time_from,end=form.elements.time_to;
  start.setCustomValidity('');end.setCustomValidity('');
  if(Boolean(start.value)!==Boolean(end.value)){
    (start.value?end:start).setCustomValidity('Renseigner les deux heures, ou choisir Journée complète.');
  }else if(start.value && start.value>=end.value){
    end.setCustomValidity('La fin doit être après le début, dans la même journée.');
  }
  const valid=form.checkValidity();if(!valid&&report)form.reportValidity();return valid;
}
function callsClearTime(){
  const f=$('#calls-filters');f.elements.time_from.value='';f.elements.time_to.value='';
  f.elements.full_day.value='1';$('#calls-time-preset').value='all';callsValidateTime();
}
function callsBindTimeFilter(cfg,hp){
  const f=$('#calls-filters'),preset=$('#calls-time-preset'),start=f.elements.time_from,end=f.elements.time_to;
  const changed=()=>{callsRequest++;callsCurrent=null;$('#calls-export').disabled=true;$('#calls-time-active').textContent='Filtres modifiés · cliquer sur Rechercher.';};
  preset.onchange=()=>{
    if(preset.value==='all')callsClearTime();
    else {
      const pair=preset.value==='work'||preset.value==='custom'?[cfg.work_start||'08:00',cfg.work_end||'19:00']:preset.value.split('-');
      start.value=pair[0];end.value=pair[1];f.elements.full_day.value=preset.value==='work'?'0':'1';
      callsValidateTime();
    }
    changed();
  };
  for(const input of [start,end])input.oninput=()=>{
    preset.value=start.value||end.value?'custom':'all';f.elements.full_day.value='1';callsValidateTime();
  };
  // Do not export the previous page while new, unapplied filters are shown.
  f.addEventListener('input',changed);f.addEventListener('change',changed);
  if(hp.has('time_from')||hp.has('time_to')){
    start.value=hp.get('time_from')||'';end.value=hp.get('time_to')||'';preset.value='custom';callsValidateTime();
  }else if(hp.get('full_day')==='0'){
    preset.value='work';start.value=cfg.work_start;end.value=cfg.work_end;f.elements.full_day.value='0';
  }
}
function callsQuery(){const q=new URLSearchParams(new FormData($('#calls-filters')));q.set('page',callsPage);q.set('live_page',callsObservationPage);if(callsSortState.key&&callsSortState.direction!=='default'){q.set('sort',callsSortState.key);q.set('sort_dir',callsSortState.direction);}return q;}
async function callsImport(e){
  e.preventDefault();const f=$('#calls-file').files[0];if(!f)return;if(!$('#calls-offset').value){$('#calls-import-result').textContent='Confirme le fuseau horaire de l’export avant l’import.';return;}const button=e.target.querySelector('button');button.disabled=true;$('#calls-import-result').textContent='Import en cours…';
  try{const q=new URLSearchParams({filename:f.name,offset:$('#calls-offset').value});const r=await importInBackground('/api/supervision/import?'+q,{method:'POST',headers:{'Content-Type':'application/octet-stream'},body:f},'#calls-import-result');const gi=r.group_import||{},groupMsg=gi.assigned?` · ${gi.assigned} affectation(s) de groupe importée(s)`:'';$('#calls-import-result').textContent=importResultText(r)+groupMsg;await supportAutoImportStatus('#calls-auto-import-status','calls');if(r.days?.length){$('#calls-filters').elements.date_from.value=r.days[0];$('#calls-filters').elements.date_to.value=r.days[r.days.length-1];}callsPage=0;await callsLoad();}catch(err){$('#calls-import-result').textContent=err.message;}finally{button.disabled=false;}
}
function callDateTime(text){const parts=String(text||'').trim().split(/\s+/),raw=parts[0]||'—',time=parts[1]||'—',d=raw.split('-');return {date:d.length===3?`${d[2]}/${d[1]}/${d[0]}`:raw,time};}
function callAgentCell(r){const firstName=r.first_name||'',lastName=r.last_name||'',firstId=r.first_agent||'',lastId=r.last_agent||'',primaryName=lastName||firstName||'',primaryId=lastId||firstId||'',primaryGroup=r.last_group_name||r.first_group_name||'';let html=`<strong>${esc(primaryName||primaryId||'—')}</strong>`;if(primaryName&&primaryId)html+=`<small class="sub">ID agent : ${esc(primaryId)}</small>`;if(primaryGroup)html+=`<small class="sub">Groupe : ${esc(primaryGroup)}</small>`;if(firstId&&lastId&&firstId!==lastId)html+=`<small class="sub">Premier : ${esc(firstName||firstId)} · ${esc(firstId)}</small><small class="sub">Dernier : ${esc(lastName||lastId)} · ${esc(lastId)}</small>`;return html;}

function callsRefreshSortHeaders(){document.querySelectorAll('#calls-table th[data-call-sort]').forEach(h=>{const key=h.dataset.callSort,active=callsSortState.key===key&&callsSortState.direction!=='default';h.setAttribute('aria-sort',active?(callsSortState.direction==='asc'?'ascending':'descending'):'none');const b=h.querySelector('button');if(b){const base=b.textContent.replace(/[ ↕↑↓]+$/,'');b.textContent=base+(active?(callsSortState.direction==='asc'?' ↑':' ↓'):' ↕');b.onclick=()=>callsCycleSort(key);}});}
function callsRender(d,query){
    if(d.calls_revision!=='V56.2-CALLS-TIME-1')throw new Error('Backend Appels non actualisé. Redémarrer Nelyio depuis le dossier mis à jour, puis recharger avec Ctrl + F5.');
    const slot=d.time_filter;$('#calls-time-active').textContent=(slot.mode==='all'?'Journée complète':slot.start+' → '+slot.end)+' · chaque jour · heure de début de l’appel (France) · V56.2.';
    $('#calls-export').disabled=false;d.view_mode='calls';d.applied_filters=Array.from(query);callsCurrent=d;$('#calls-message').innerHTML='';
    const coverage=d.coverage||[],missing=coverage.filter(r=>r.source==='missing').map(r=>r.day),reference=coverage.filter(r=>r.source==='export').length;
    $('#calls-coverage').innerHTML=`<div class="sup-health ${missing.length?'sup-warn':'sup-ok'}"><strong>${esc(d.date_from)} → ${esc(d.date_to)} · ${reference} jour(s) avec appels · ${missing.length} sans export</strong><span>${missing.length?'Pas de données ODCalls pour : '+esc(missing.join(', ')):'Données d’appels disponibles sur toute la période.'}</span></div>`;
    const s=d.summary;$('#calls-cards').innerHTML='<div class="sup-metrics">'+[
      ['Appels exportés trouvés',s.records],['Indices distincts',s.indices],['Codes de fin non nuls',s.end_codes],['Conversations < 10 s',s.short],['Sans agent déclaré',s.no_agent],['Conversation moyenne',s.average_conversation===null?'—':supDuration(s.average_conversation)]
    ].map(([k,v])=>supportMetric(k,v)).join('')+'</div>';
    $('#calls-count').textContent=d.count+' résultat(s)';
    $('#calls-body').innerHTML=d.rows.map(callResultRow).join('')||'<tr><td colspan="8" class="empty">Aucun appel exporté trouvé avec ces critères.</td></tr>';
    $$('[data-call-details]').forEach(button=>button.onclick=()=>callsOpenDetail(Number(button.dataset.callDetails)));
    callsRefreshSortHeaders();
    $('#calls-page').textContent=`Page ${callsPage+1} / ${Math.max(1,Math.ceil(d.count/100))}`;$('#calls-prev').disabled=callsPage===0;$('#calls-next').disabled=(callsPage+1)*100>=d.count;
}
async function callsLoad(){
  if(!String(location.hash).startsWith('#calls')||!currentUser)return;if(!callsValidateTime(true))return;const request=++callsRequest;callsCurrent=null;$('#calls-export').disabled=true;
  try{
    $('#calls-message').textContent='Recherche en cours…';const query=callsQuery(),d=await api('/api/supervision/calls?'+query);
    if(request!==callsRequest||!String(location.hash).startsWith('#calls'))return;callsRender(d,query);
  }catch(e){if(request===callsRequest&&$('#calls-message')){
    callsCurrent=null;$('#calls-export').disabled=true;
    $('#calls-message').innerHTML=flash(e.message,'error');$('#calls-count').textContent='Recherche non aboutie';
    $('#calls-body').innerHTML='<tr><td colspan="8" class="empty">Corriger le filtre ou l’erreur, puis relancer la recherche.</td></tr>';
    $('#calls-prev').disabled=true;$('#calls-next').disabled=true;
    $('#calls-cards').innerHTML='';$('#calls-coverage').innerHTML='';
    $('#calls-time-active').textContent='Filtre non appliqué.';
  }}
}
function callsExport(){
  const d=callsCurrent;if(!d)return;const lines=[['Vue','Recherche d’appels'],['Du',d.date_from],['Au',d.date_to]];for(const [key,value] of d.applied_filters)if(key!=='page')lines.push(['Filtre '+key,value]);
  lines.push([],['INDICATEUR APPELS','Valeur']);const labels={records:'Appels distincts',indices:'Indices distincts',end_codes:'Code de fin non nul',short:'Conversation positive <10 s',abandons:'Abandons déclarés',no_agent:'Sans agent déclaré',invalid_durations:'Durées incohérentes',conversation:'Conversation positive totale (s)',average_conversation:'Conversation positive moyenne (s)'};for(const [key,value] of Object.entries(d.summary))lines.push([labels[key]||key,value??'Non disponible']);
  lines.push([],['Agent','Date','Heure','ANI','Indice','ID appel','DNIS','Durée (s)','Conversation (s)','Attente (s)','EndReason','Campagne']);for(const r of d.rows){const w=callDateTime(r.start_text),agent=r.last_name||r.first_name||r.last_agent||r.first_agent||'';lines.push([agent,w.date,w.time,r.ani,r.indice,r.call_id,r.dnis,r.duration,r.conversation,r.wait,r.end_reason,r.campaign]);}
  const cell=value=>{let s=String(value??'');if(/^[=+@\-\t\r]/.test(s))s="'"+s;return '"'+s.replace(/"/g,'""')+'"';};const blob=new Blob(['\ufeff'+lines.map(r=>r.map(cell).join(';')).join('\r\n')],{type:'text/csv;charset=utf-8'});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=`Nelyio_recherche_appels_${d.date_from}_${d.date_to}.csv`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}

function supportExport(){
  const d=supportCurrent;if(!d)return;const title=d.view_mode==='calls'?'Appels exportés':'Support technique';const lines=[['Vue',title],['Du',d.date_from],['Au',d.date_to]];for(const [key,value] of d.applied_filters)if(key!=='page')lines.push(['Filtre '+key,value]);
  if(d.view_mode==='technical'){
    const s=d.disconnects.summary;lines.push([],['INDICATEURS DECONNEXIONS','Valeur'],['Incidents techniques bruts',s.raw_total_deco??s.total_deco],['Incidents techniques corrigés',s.total_deco],['Événements normaux bruts',s.raw_normal_disconnects||0],['Fermetures / pauses probables',s.probable_closures||0],['Incidents collectifs',s.collective_disconnects||0],['Déconnexions pendant appel',s.total_deco_call],['Pourcentage pendant appel',s.total_call_percent+'%'],['Agents signalés',s.impacted_agents],['Temps perdu brut (s)',s.raw_total_lost??s.total_lost],['Temps perdu technique corrigé (s)',s.total_lost],['Durée moyenne (s)',s.avg_seconds],['Durée médiane (s)',s.median_seconds],['95e percentile (s)',s.p95_seconds],['Durée max normale (s)',s.max_seconds],['Coupures au-delà du seuil',s.critical],['Anomalies > 1 h',s.anomalies_over_1h||0],['Exclus par Policies',s.policy_excluded_events||0],['Autorisés par Policies',s.policy_authorized_events||0],['Déclarations appliquées',s.declaration_applied_events||0],['Exclus par Déclarations',s.declaration_excluded_events||0],['Autorisés par Déclarations',s.declaration_authorized_events||0],['Anciennes exclusions horaires',(s.excluded_slots||[]).join(' + ')||((d.common_filters?.legacy_exclusion_mode||'compat')==='policy_only'?'Désactivées — Policies utilisées':'Aucune')],['Jours couverts',s.active_days],['Incidents / jour couvert',s.incidents_per_active_day]);
    lines.push([],['STATISTIQUES PAR AGENT','Identifiant','Nom','Groupe','Priorité','Score technique','Déconnexions techniques','Pendant appel','Jours touchés','Jours travaillés','% jours travaillés touchés','Temps perdu technique (s)','Collectifs','Fermetures probables','Anomalies','Dernière coupure']);d.disconnects.agents.forEach(r=>lines.push(['Agent',r.agent,r.name,r.group_name||'',r.priority,r.technical_score??r.risk_score,r.deco,r.deco_call,r.days_affected,r.worked_days||0,r.affected_worked_days_percent||0,r.lost_seconds,r.collective_count||0,r.probable_closure_count||0,r.anomaly_count||0,r.last_text]));
    lines.push([],['JOURNAL DES ÉVÉNEMENTS','Agent','Groupe','Début','Fin','Durée (s)','Classification','Justification','Pendant appel','Source','Indice','ANI','ID appel']);d.disconnects.recent.slice(0,500).forEach(r=>lines.push(['Événement',r.agent,r.group_name||'',r.start_text,r.end_text,r.seconds,r.event_label||r.event_class||'Déconnexion technique',r.classification_reason||'',r.during_call?'Oui':'Non',r.source,r.indice||'',r.ani||'',r.call_id||'']));
    lines.push([],['ANOMALIES > 1 H','Agent','Groupe','Début','Fin','Durée (s)','Pendant appel','Source','Motif']);(d.disconnects.anomalies||[]).forEach(r=>lines.push(['Anomalie',r.agent,r.group_name||'',r.start_text,r.end_text,r.seconds,r.during_call?'Oui':'Non',r.source,r.reason||'Déconnexion > 1 h']));
    lines.push([],['SIGNAUX HELPDESK','Valeur']);const labels={signals:'Signaux',agents:'Agents concernés',confirmed:'Confirmés techniques',unqualified:'À qualifier',normal:'Non techniques',resolved:'Résolus'};for(const [key,value] of Object.entries(d.summary))lines.push([labels[key]||key,value]);
  }else{
    lines.push([],['INDICATEUR APPELS','Valeur']);const labels={records:'ID d’appel distincts',indices:'Indices distincts',end_codes:'Code de fin non nul',short:'Conversation positive <10 s',abandons:'Abandons déclarés',no_agent:'Sans agent déclaré',invalid_durations:'Durées incohérentes',conversation:'Conversation positive totale (s)',average_conversation:'Conversation positive moyenne (s)'};for(const [key,value] of Object.entries(d.summary))lines.push([labels[key]||key,value??'Non disponible']);lines.push([],['Code EndReason','Nombre']);d.reasons.forEach(r=>lines.push([r.label,r.value]));
  }
  const cell=value=>{let s=String(value??'');if(/^[=+@\-\t\r]/.test(s))s="'"+s;return '"'+s.replace(/"/g,'""')+'"';};const blob=new Blob(['\ufeff'+lines.map(r=>r.map(cell).join(';')).join('\r\n')],{type:'text/csv;charset=utf-8'});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=`Nelyio_support_${d.view_mode}_${d.date_from}_${d.date_to}.csv`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}

/* === Rapports PDF - synthèse lisible + preuves complètes v22.5.1 ========== */
let weeklyReportCurrent=null,weeklyReportRequest=0,weeklyReportCurrentQuery='';
function reportDuration(v){return supDuration(Number(v||0));}
function reportGroupChecks(groups){return (groups||[]).map(g=>{const label=String(g.name||g.id);return `<label class="report-check-row" data-search="${esc((label+' '+g.id).toLowerCase())}"><input type="checkbox" name="group" value="${esc(g.id)}" data-label="${esc(label)}"><span class="report-check-main"><strong>${esc(label)}</strong><small>Groupe #${esc(g.id)}</small></span><span class="report-check-mark">✓</span></label>`;}).join('');}
function reportAgentChecks(rows,name){return (rows||[]).map(r=>{const agent=String(r.agent||''),label=String(r.name||r.agent||''),group=String(r.group_name||'Non affecté'),search=(label+' '+agent+' '+group).toLowerCase();return `<label class="report-check-row" data-search="${esc(search)}"><input type="checkbox" name="${esc(name)}" value="${esc(agent)}" data-label="${esc(label+' ('+agent+')')}"><span class="report-check-main"><strong>${esc(label)}</strong><small>ID ${esc(agent)} · ${esc(group)}</small></span><span class="report-check-mark">✓</span></label>`;}).join('');}
function reportTrendLabel(code){return code==='improved'?'Amélioration':code==='degraded'?'Dégradation':code==='stable'?'Stable / mixte':'Comparaison indisponible';}
function reportMetricValue(m,key){const v=m?.[key];if(v==null)return '—';if(['lost_minutes_per_day','inactive_minutes_per_day'].includes(m.key))return `${Number(v).toFixed(1)} min/j`;if(m.key==='short_per_1000')return `${Number(v).toFixed(1)}/1000`;return `${Number(v).toFixed(2)}/j`;}
function reportTypeName(type){return type==='comparison'?'Comparaison de périodes':type==='detailed'?'Rapport technique détaillé':'Vue d’ensemble · Priorités Support';}
function reportPolicyHtml(d){
  const a=d.priority_audit||{},policies=d.disconnects?.priority_policy||[];
  const criteria=p=>p.is_fallback?'Niveau par défaut':(p.conditions||[]).map(c=>`${c.label||c.metric} ${c.operator} ${c.value}${c.unit?' '+c.unit:''}`).join(p.match_mode==='ALL'?' ET ':' OU ');
  return `<details class="card report-policy-audit"><summary>Priorités Support appliquées · ${Number(a.policy_count||0)} niveau(x) actif(s)</summary><p>${esc(a.method||'Même moteur que Support technique Nelyio.')}</p><p>Configuration au ${esc(a.captured_at||d.generated_at)} · référence <code>${esc(a.fingerprint||'')}</code>. Les deux périodes sont recalculées avec ces mêmes règles.</p><div class="table-wrap"><table><thead><tr><th>Niveau</th><th>Rang</th><th>Logique</th><th>Conditions</th><th>État</th></tr></thead><tbody>${policies.map(p=>`<tr><td>${supportPriorityBadge(p.priority,[],policies)}</td><td>${Number(p.rank||0)}</td><td>${p.is_fallback?'Défaut':p.match_mode==='ALL'?'ET':'OU'}</td><td>${esc(criteria(p))}</td><td>${p.enabled?'Actif':'Désactivé'}</td></tr>`).join('')}</tbody></table></div><p>Le PDF contient aussi les paramètres du score et les règles de classification utilisés. Une absence de données n’est pas une preuve d’absence d’incident.</p></details>`;
}
function reportScoreText(value){return value==null?'—':Number(value).toFixed(2);}
function reportSharedSummaryHtml(d){
  const ws=d.web_summary||{},items=ws.overview||d.overview||[],coverage=ws.coverage||d.disconnects?.source_by_day||[],integ=d.integrity||{},active=Number(d.disconnects?.summary?.active_days||0),missing=coverage.filter(r=>r.source==='missing').length,exportDays=coverage.filter(r=>r.source==='export').length,captureDays=coverage.filter(r=>r.source==='capture').length;
  const daily=(ws.daily||d.disconnects?.daily||[]).filter(r=>r.total!=null);
  return `<section class="card report-web-summary"><div class="panel-head"><div><span class="sup-eyebrow">SYNTHÈSE WEB</span><h2>Résumé du rapport</h2><p>Mêmes données, mêmes filtres et mêmes calculs que le PDF. Les preuves détaillées sont chargées à la demande.</p></div></div><div class="report-summary-grid"><div><span>Jours exploitables</span><strong>${active}</strong><small>${exportDays} SIMPLIFY2 · ${captureDays} Capture · ${missing} manquant(s)</small></div><div><span>Fiabilité données</span><strong>${esc(integ.score??'—')}/100</strong><small>${esc(integ.label||integ.status||'contrôle automatique')}</small></div><div><span>Agents du périmètre</span><strong>${Number(d.scope_agent_count||0)}</strong><small>${esc(d.scope_label||'Global')}</small></div><div><span>Gouvernance horaire</span><strong>${(d.common_filters?.legacy_exclusion_mode||'compat')==='policy_only'?'Policies':(d.filters?.excluded_slots||[]).length}</strong><small>${esc((d.common_filters?.legacy_exclusion_mode||'compat')==='policy_only'?'Anciennes exclusions désactivées':((d.filters?.excluded_slots||[]).join(', ')||'Aucune'))}</small></div></div>${items.length?`<div class="report-reading"><strong>Points à retenir</strong><ul>${items.map(x=>`<li>${esc(x)}</li>`).join('')}</ul></div>`:''}${daily.length?`<div class="sup-chart-grid report-web-chart">${supBarChart('report-web-daily','Déconnexions par jour','Lecture synthétique de la période sélectionnée.',daily.map(r=>({key:r.label,label:String(r.label).slice(5),value:Number(r.total||0)})),n=>String(n))}</div>`:''}</section>`;
}
function reportDeclarationsHtml(d){const rows=d.disconnects?.declarations||[];if(!rows.length)return '';return `<details class="card panel report-policy-audit"><summary>Déclarations prises en compte · ${rows.length}</summary><p>Ces périodes ponctuelles sont appliquées après les Policies. Elles ne suppriment jamais les logs bruts.</p><div class="table-wrap"><table><thead><tr><th>ID</th><th>Type</th><th>Cible</th><th>Période</th><th>Auteur</th><th>Commentaire</th></tr></thead><tbody>${rows.map(r=>`<tr><td>#${Number(r.id||0)}</td><td>${esc(r.type_label||r.declaration_type||'Autre')}</td><td>${esc((r.targets||[]).map(t=>(t.target_type==='AGENT'?'Agent ':'Groupe ')+(t.target_key||'')).join(', ')||'—')}</td><td>${esc(r.start_at||'—')} → ${esc(r.end_at||'—')}</td><td>${esc(r.created_by||'—')}</td><td>${esc(r.comment||'—')}</td></tr>`).join('')}</tbody></table></div></details>`;}
function reportComparisonDailyHtml(d){const rows=d.comparison?.daily||[];if(!rows.length)return '';return `<section class="card panel report-comparison-daily"><div class="panel-head"><div><h2>Jour par jour</h2><p>Période actuelle et période précédente de même durée. Les journées sans source restent explicitement signalées.</p></div></div><div class="table-wrap"><table><thead><tr><th>Jour</th><th>Actuel</th><th>Avant</th><th>Temps actuel</th><th>Temps avant</th><th>Source actuelle</th><th>Source avant</th></tr></thead><tbody>${rows.map(r=>`<tr><td><strong>${esc(r.label)}</strong><small class="sub">${esc(r.day)} vs ${esc(r.previous_day)}</small></td><td>${r.current==null?'—':Number(r.current)}</td><td>${r.previous==null?'—':Number(r.previous)}</td><td>${r.current_lost_seconds==null?'—':supDuration(r.current_lost_seconds)}</td><td>${r.previous_lost_seconds==null?'—':supDuration(r.previous_lost_seconds)}</td><td>${esc(r.current_source||'missing')}</td><td>${esc(r.previous_source||'missing')}</td></tr>`).join('')}</tbody></table></div></section>`;}
function reportDetailChooserHtml(d){const c=d.detail_counts||{};return `<section class="card panel report-web-details"><div class="panel-head"><div><span class="sup-eyebrow">PREUVES À LA DEMANDE</span><h2>Détails techniques du rapport</h2><p>Charge uniquement la catégorie ouverte afin de garder le site rapide, même sur 30 jours.</p></div></div><div class="report-detail-tabs"><button type="button" class="button ghost" data-report-detail-kind="disconnects">Déconnexions <b>${Number(c.disconnects||0)}</b></button><button type="button" class="button ghost" data-report-detail-kind="anomalies">Anomalies &gt;1h <b>${Number(c.anomalies||0)}</b></button><button type="button" class="button ghost" data-report-detail-kind="inactive">Contextes inactifs <b>${Number(c.inactive||0)}</b></button><button type="button" class="button ghost" data-report-detail-kind="technical">Autres signaux <b>${Number(c.technical||0)}</b></button><button type="button" class="button ghost" data-report-detail-kind="agents">Agents <b>${Number(c.agents||0)}</b></button></div><div id="report-detail-host"><p class="empty">Choisir une catégorie pour afficher les preuves correspondantes.</p></div></section>`;}
function reportDetailTableHtml(d){const rows=d.rows||[],kind=d.kind||'disconnects';let head='',body='';if(kind==='agents'){head='<tr><th>Agent</th><th>Groupe</th><th>Priorité</th><th>Score</th><th>Décos</th><th>En appel</th><th>Temps coupure</th><th>Inactif</th><th>Anomalies</th></tr>';body=rows.map(r=>`<tr><td><strong>${esc(r.name||r.agent)}</strong><small class="sub">${esc(r.agent||'')}</small></td><td>${esc(r.group_name||'Non affecté')}</td><td>${esc(r.priority||'—')}</td><td>${reportScoreText(r.technical_score)}</td><td>${Number(r.deco||0)}</td><td>${Number(r.deco_call||0)}</td><td>${reportDuration(r.lost_seconds||0)}</td><td>${reportDuration(r.inactive_seconds||0)}</td><td>${Number(r.anomaly_count||0)}</td></tr>`).join('');}
else if(kind==='technical'){head='<tr><th>Début</th><th>Agent</th><th>Groupe</th><th>Signal</th><th>Détail</th><th>Source</th></tr>';body=rows.map(r=>`<tr><td>${esc(r.start_text||'')}</td><td><strong>${esc(r.name||r.agent)}</strong><small class="sub">${esc(r.agent||'')}</small></td><td>${esc(r.group_name||'Non affecté')}</td><td>${esc(r.label||r.category||'Signal technique')}</td><td>${esc(r.detail||'')}</td><td>${esc(r.source||'')}</td></tr>`).join('');}
else if(kind==='inactive'){head='<tr><th>Début</th><th>Fin</th><th>Agent</th><th>Groupe</th><th>Durée</th><th>Détail</th><th>Source</th></tr>';body=rows.map(r=>`<tr><td>${esc(r.start_text||'')}</td><td>${esc(r.end_text||'')}</td><td><strong>${esc(r.name||r.agent)}</strong><small class="sub">${esc(r.agent||'')}</small></td><td>${esc(r.group_name||'Non affecté')}</td><td>${reportDuration(r.seconds||r.duration||0)}</td><td>${esc(r.detail||'')}</td><td>${esc(r.source||'')}</td></tr>`).join('');}
else if(kind==='anomalies'){head='<tr><th>Début</th><th>Agent</th><th>Groupe</th><th>Durée</th><th>Raison / détail</th><th>Traitement</th></tr>';body=rows.map(r=>`<tr><td>${esc(r.start_text||'')}</td><td><strong>${esc(r.name||r.agent)}</strong><small class="sub">${esc(r.agent||'')}</small></td><td>${esc(r.group_name||'Non affecté')}</td><td>${reportDuration(r.seconds||0)}</td><td>${esc(r.reason||r.detail||'Déconnexion > 1 h')}</td><td>${r.policy_applied?`<small><strong>Policy :</strong> ${esc(r.policy_reason||'')}</small>`:''}${r.declaration_applied?`<small><strong>Déclaration :</strong> ${esc(r.declaration_reason||'')}</small>`:''}${!r.policy_applied&&!r.declaration_applied?'—':''}</td></tr>`).join('');}
else{head='<tr><th>Début</th><th>Fin</th><th>Agent</th><th>Groupe</th><th>Durée</th><th>Contexte</th><th>Classe</th><th>Traitement</th><th>Source</th></tr>';body=rows.map(r=>`<tr><td>${esc(r.start_text||'')}</td><td>${esc(r.end_text||'')}</td><td><strong>${esc(r.name||r.agent)}</strong><small class="sub">${esc(r.agent||'')}</small></td><td>${esc(r.group_name||'Non affecté')}</td><td>${reportDuration(r.seconds||0)}</td><td>${r.during_call?'Pendant appel':'Hors appel'}</td><td>${esc(r.event_class||'déconnexion')}</td><td>${r.policy_applied?`<small><strong>Policy :</strong> ${esc(r.policy_reason||'')}</small>`:''}${r.declaration_applied?`<small><strong>Déclaration :</strong> ${esc(r.declaration_reason||'')}</small>`:''}${!r.policy_applied&&!r.declaration_applied?'—':''}</td><td>${esc(r.source||'')}</td></tr>`).join('');}
const pager=d.pages>1?`<div class="report-detail-pager"><button type="button" class="button ghost tiny" data-report-detail-page="${Math.max(1,d.page-1)}" ${d.page<=1?'disabled':''}>Précédent</button><span>Page ${d.page} / ${d.pages} · ${d.total} ligne(s)</span><button type="button" class="button ghost tiny" data-report-detail-page="${Math.min(d.pages,d.page+1)}" ${d.page>=d.pages?'disabled':''}>Suivant</button></div>`:`<div class="report-detail-pager"><span>${d.total} ligne(s)</span></div>`;return `<div class="table-wrap"><table><thead>${head}</thead><tbody>${body||`<tr><td colspan="9" class="empty">Aucune donnée dans cette catégorie.</td></tr>`}</tbody></table></div>${pager}`;}
async function reportLoadDetail(kind,page=1){const host=$('#report-detail-host');if(!host)return;host.innerHTML='<div class="loading">Chargement des preuves du rapport…</div>';try{const q=new URLSearchParams(weeklyReportCurrentQuery||reportFormQuery());q.set('detail_kind',kind);q.set('page',String(page));q.set('page_size','50');const d=await api('/api/supervision/report-details?'+q);host.innerHTML=reportDetailTableHtml(d);$$('[data-report-detail-page]').forEach(b=>b.onclick=()=>reportLoadDetail(kind,Number(b.dataset.reportDetailPage||1)));$$('[data-report-detail-kind]').forEach(b=>b.classList.toggle('active',b.dataset.reportDetailKind===kind));}catch(e){host.innerHTML=flash(e.message,'error');}}
function reportBindPreview(){ $$('[data-report-detail-kind]').forEach(b=>b.onclick=()=>reportLoadDetail(b.dataset.reportDetailKind,1)); }
function reportPreviewHtml(d){
  const s=d.disconnects?.summary||{},sig=d.signals?.summary||{},integ=d.integrity||{},cmp=d.comparison||{},type=d.report_type||'overview',policies=d.disconnects?.priority_policy||[];
  const head=`<section class="report-preview-head"><div><span class="sup-eyebrow">${esc(d.period_label||d.week_label)}</span><h2>${esc(reportTypeName(type))}</h2><p>${esc(d.scope_label)} · ${esc(d.date_from)} → ${esc(d.date_to)} · ${Number(d.period_days||7)} jour(s), dates incluses</p><p>${esc(d.time_label)} · ${esc(d.source_label)} · ${esc(d.disconnect_context_label||'Toutes les déconnexions')}</p></div><span class="report-ready ${d.reportlab_available?'ok':'warn'}">${d.reportlab_available?'PDF prêt':'ReportLab manquant'}</span></section>`+reportPolicyHtml(d);
  const rawDeco=Number(s.raw_total_deco??s.total_deco??0),rawLost=Number(s.raw_total_lost??s.total_lost??0);
  const kpis=`<div class="report-exec-kpis"><div><span>Temps corrigé</span><strong>${esc(reportDuration(s.total_lost||0))}</strong><small>Brut ${esc(reportDuration(rawLost))} · ${rawDeco} → ${Number(s.total_deco||0)} déconnexion(s)</small></div><div><span>Coupures en appel</span><strong>${Number(s.total_deco_call||0)}</strong><small>${Number(s.total_call_percent||0).toFixed(1)} %</small></div><div><span>Anomalies &gt;1h</span><strong>${Number(s.anomalies_over_1h||0)}</strong><small>signal séparé</small></div><div><span>Contexte inactif</span><strong>${esc(reportDuration(sig.inactive_seconds||0))}</strong><small>${Number(sig.inactive_count||0)} épisode(s)</small></div><div><span>Policies appliquées</span><strong>${Number(s.policy_excluded_events||0)}</strong><small>événement(s) exclus · ${Number(s.policy_authorized_events||0)} autorisé(s)</small></div><div><span>Déclarations</span><strong>${Number(s.declaration_applied_events||0)}</strong><small>${Number(s.declaration_excluded_events||0)} exclu(s) des KPI · ${Number(s.declaration_authorized_events||0)} autorisé(s)</small></div></div>`;
  if(type==='overview'){
    const top=(d.top_unstable||[]).slice(0,20);
    return head+reportSharedSummaryHtml(d)+reportDeclarationsHtml(d)+`<section class="card panel report-overview-preview"><div class="panel-head"><div><span class="sup-eyebrow">VUE D’ENSEMBLE</span><h2>Les 20 agents/postes à examiner en priorité</h2><p>Même classement que Support : rang de la policy, puis score technique. Les anomalies et les pauses probables restent visibles séparément. Ce n’est pas une note de performance.</p></div><span>${top.length} affiché(s)</span></div>${kpis}<div class="table-wrap"><table><thead><tr><th>#</th><th>Agent</th><th>Groupe</th><th>Priorité</th><th>Score Support</th><th>Temps coupure</th><th>Décos</th><th>En appel</th><th>Anomalies</th><th>Contexte inactif</th></tr></thead><tbody>${top.map((r,i)=>`<tr><td><strong>${i+1}</strong></td><td><strong>${esc(r.name||r.agent)}</strong><small class="sub">${esc(r.agent||'')}</small></td><td>${esc(r.group_name||'Non affecté')}</td><td>${supportPriorityBadge(r.priority,r.priority_reasons,policies)}</td><td><strong>${reportScoreText(r.technical_score)}</strong></td><td>${reportDuration(r.lost_seconds)}</td><td>${Number(r.deco||0)}</td><td>${Number(r.deco_call||0)}</td><td>${Number(r.anomaly_count||0)}</td><td>${reportDuration(r.inactive_seconds)}</td></tr>`).join('')||'<tr><td colspan="10" class="empty">Aucun signal technique retenu.</td></tr>'}</tbody></table></div></section>`;
  }
  if(type==='comparison'){
    const cmpRows=(cmp.metrics||[]).map(m=>`<tr><td><strong>${esc(m.label)}</strong></td><td>${esc(reportMetricValue(m,'current'))}</td><td>${esc(reportMetricValue(m,'previous'))}</td><td>${m.delta_pct==null?'n/a':`${Number(m.delta_pct)>0?'+':''}${Number(m.delta_pct).toFixed(1)}%`}</td><td><span class="report-trend ${esc(m.status||'unknown')}">${esc(reportTrendLabel(m.status))}</span></td></tr>`).join('');
    const worse=(d.agent_comparison||[]).filter(r=>Number(r.delta_score)>0).slice(0,10);
    return head+reportSharedSummaryHtml(d)+reportDeclarationsHtml(d)+`<section class="report-executive card"><div class="report-executive-top"><div><span class="sup-eyebrow">COMPARAISON</span><h2>Cette période vs ${esc(cmp.label||'période précédente')}</h2><p>Les deux périodes utilisent exactement les mêmes filtres.</p></div><div class="report-verdict ${esc(cmp.verdict?.code||'unavailable')}"><strong>${esc(cmp.verdict?.label||'Indisponible')}</strong><small>${esc(cmp.verdict?.detail||'')}</small></div></div>${kpis}<div class="table-wrap"><table><thead><tr><th>Indicateur</th><th>Actuel</th><th>Avant</th><th>Écart</th><th>Lecture</th></tr></thead><tbody>${cmpRows||'<tr><td colspan="5" class="empty">Comparaison indisponible.</td></tr>'}</tbody></table></div></section><section class="card panel"><div class="panel-head"><div><h2>Agents dont la situation technique se dégrade le plus</h2><p>Variation du score Support, avec la même configuration sur les deux périodes de même durée. Les agents sans données comparables ne sont pas classés comme améliorés ou dégradés.</p></div></div><div class="table-wrap"><table><thead><tr><th>Agent</th><th>Groupe</th><th>Priorité actuelle</th><th>Priorité avant</th><th>Score actuel</th><th>Avant</th><th>Écart</th><th>Temps actuel</th><th>Temps avant</th></tr></thead><tbody>${worse.map(r=>`<tr><td><strong>${esc(r.name||r.agent)}</strong></td><td>${esc(r.group_name||'')}</td><td>${supportPriorityBadge(r.current_priority,[],policies)}</td><td>${supportPriorityBadge(r.previous_priority,[],policies)}</td><td>${reportScoreText(r.current_score)}</td><td>${Number(r.previous_score||0).toFixed(1)}</td><td><strong>+${Number(r.delta_score||0).toFixed(1)}</strong></td><td>${reportDuration(r.current_lost)}</td><td>${reportDuration(r.previous_lost)}</td></tr>`).join('')||'<tr><td colspan="9" class="empty">Aucune dégradation nette détectée.</td></tr>'}</tbody></table></div></section>`+reportComparisonDailyHtml(d);
  }
  const countInc=(d.disconnects?.incidents||[]).length,countAnom=(d.disconnects?.all_anomalies||d.disconnects?.anomalies||[]).length;
  return head+reportSharedSummaryHtml(d)+reportDeclarationsHtml(d)+`<section class="card panel report-detailed-preview"><div class="panel-head"><div><span class="sup-eyebrow">AUDIT TECHNIQUE</span><h2>Rapport détaillé complet</h2><p>Ce rapport privilégie la traçabilité : tous les agents du périmètre, toutes les coupures retenues, anomalies, contextes inactifs et autres signaux techniques sont placés dans les annexes.</p></div><span>${Number(d.scope_agent_count||0)} agent(s)</span></div>${kpis}<div class="report-detail-cards"><div><span>Agents du périmètre</span><strong>${Number(d.scope_agent_count||0)}</strong></div><div><span>Coupures normales</span><strong>${Number(s.total_deco||0)}</strong></div><div><span>Anomalies &gt;1h</span><strong>${Number(s.anomalies_over_1h||0)}</strong></div><div><span>Contextes inactifs</span><strong>${Number(sig.inactive_count||0)}</strong></div><div><span>Autres signaux</span><strong>${Number(sig.technical_count||0)}</strong></div><div><span>Fiabilité données</span><strong>${esc(integ.score??'—')}/100</strong></div></div><div class="flash info">Le PDF détaillé peut être long : c’est volontaire. Les premières pages restent lisibles, puis les annexes donnent la preuve complète événement par événement.</div></section>`+reportDetailChooserHtml(d);
}
function reportDateUtc(value){
  if(!/^\d{4}-\d{2}-\d{2}$/.test(value||''))return null;
  const d=new Date(value+'T00:00:00Z');return Number.isFinite(d.getTime())&&d.toISOString().slice(0,10)===value?d:null;
}
function reportValidatePeriod(){
  const mode=$('#report-period-mode')?.value||'week',max=Number(weeklyReportCurrent?.max_report_days||30);
  if(mode==='week')return {valid:!!$('#report-week')?.value,days:7,message:'Semaine ISO : 7 jours, dates incluses.'};
  const to=reportDateUtc(mode==='last30'?$('#report-last30-end')?.value:$('#report-date-to')?.value);
  const from=mode==='last30'&&to?new Date(to.getTime()-(max-1)*86400000):reportDateUtc($('#report-date-from')?.value);
  if(!from||!to)return {valid:false,message:'Choisir des dates valides.'};
  const days=Math.round((to-from)/86400000)+1;
  if(days<1)return {valid:false,message:'La date de fin doit être le même jour ou après la date de début.'};
  if(days>max)return {valid:false,days,message:`${days} jours sélectionnés : maximum ${max} jours, dates incluses. Un mois de 31 jours doit être scindé.`};
  return {valid:true,days,message:`${days} jour(s), dates incluses : ${from.toISOString().slice(0,10)} → ${to.toISOString().slice(0,10)}. Maximum ${max} jours.`};
}
function reportPeriodFeedback(){
  const v=reportValidatePeriod(),note=$('#report-period-feedback');
  if(note){note.textContent=v.message;note.classList.toggle('report-period-error',!v.valid);}
  const btn=$('#weekly-report-download');if(btn)btn.disabled=!v.valid||!weeklyReportCurrent?.reportlab_available;
  return v;
}
function reportFormQuery(){
  const f=$('#weekly-report-form'),validation=reportValidatePeriod();
  if(!validation.valid)throw new Error(validation.message);
  return new URLSearchParams(new FormData(f));
}
function reportResolveAgentConflict(input){if(!input?.checked||!['include_agent','exclude_agent'].includes(input.name))return;const other=input.name==='include_agent'?'exclude_agent':'include_agent';document.querySelectorAll(`input[name="${other}"]`).forEach(o=>{if(o.value===input.value)o.checked=false;});}
function reportPickerRefresh(root){if(!root)return;const selected=[...root.querySelectorAll('.report-check-row input[type=checkbox]:checked')],count=root.querySelector('[data-picker-count]'),chips=root.querySelector('[data-picker-chips]');if(count)count.textContent=`${selected.length} sélectionné${selected.length>1?'s':''}`;if(chips){const shown=selected.slice(0,8);chips.innerHTML=shown.map(i=>`<button type="button" class="report-chip" data-picker-remove="${esc(i.value)}" title="Retirer ${esc(i.dataset.label||i.value)}">${esc(i.dataset.label||i.value)} <span>×</span></button>`).join('')+(selected.length>shown.length?`<span class="report-chip-more">+${selected.length-shown.length}</span>`:'');chips.querySelectorAll('[data-picker-remove]').forEach(b=>b.onclick=()=>{const val=b.dataset.pickerRemove;root.querySelectorAll('.report-check-row input[type=checkbox]').forEach(i=>{if(i.value===val)i.checked=false;});reportPickerRefresh(root);});}}
function reportPickerRefreshAll(){document.querySelectorAll('.report-picker').forEach(reportPickerRefresh);}
function reportInitPicker(rootId,searchId){const root=$(rootId),search=$(searchId);if(!root)return;const rows=()=>[...root.querySelectorAll('.report-check-row')],inputs=()=>[...root.querySelectorAll('.report-check-row input[type=checkbox]')];if(search)search.oninput=()=>{const q=search.value.trim().toLowerCase();rows().forEach(row=>row.hidden=!!q&&!String(row.dataset.search||'').includes(q));};inputs().forEach(i=>i.onchange=()=>{reportResolveAgentConflict(i);reportPickerRefreshAll();});root.querySelectorAll('[data-picker-action]').forEach(btn=>btn.onclick=()=>{const action=btn.dataset.pickerAction;if(action==='clear'){inputs().forEach(i=>i.checked=false);}else if(action==='select-visible'){rows().filter(r=>!r.hidden).forEach(r=>{const i=r.querySelector('input[type=checkbox]');if(i){i.checked=true;reportResolveAgentConflict(i);}});}reportPickerRefreshAll();});reportPickerRefresh(root);}
function reportResetPickers(){document.querySelectorAll('.report-picker .report-check-row').forEach(r=>r.hidden=false);document.querySelectorAll('.report-picker input[type=search]').forEach(i=>i.value='');reportPickerRefreshAll();}
function reportSyncPeriodMode(){
  const mode=$('#report-period-mode')?.value||'week';
  for(const [id,active] of [['report-week-wrap',mode==='week'],['report-custom-period',mode==='custom'],['report-last30-wrap',mode==='last30']]){
    const el=$('#'+id);if(!el)continue;el.hidden=!active;el.querySelectorAll('input').forEach(i=>{i.disabled=!active;i.required=active;});
  }
  reportPeriodFeedback();
}
async function reportLoadPreview(){
  if(location.hash!=='#reports'||!currentUser)return;const req=++weeklyReportRequest,host=$('#weekly-report-preview');$('#weekly-report-download').disabled=true;host.innerHTML='<div class="loading">Calcul du rapport avec les filtres sélectionnés…</div>';
  try{const q=reportFormQuery();$('#weekly-report-status').textContent='Calcul de l’aperçu…';const d=await api('/api/supervision/report-preview?'+q);if(req!==weeklyReportRequest||location.hash!=='#reports')return;weeklyReportCurrent=d;weeklyReportCurrentQuery=q;host.innerHTML=reportPreviewHtml(d);reportBindPreview();$('#weekly-report-download').disabled=!d.reportlab_available;$('#weekly-report-status').textContent=d.reportlab_available?'Rapport prêt à générer.':'ReportLab est requis sur le serveur pour générer le PDF.';}
  catch(e){if(req===weeklyReportRequest){host.innerHTML=flash(e.message,'error');$('#weekly-report-download').disabled=true;$('#weekly-report-status').textContent=e.message;}}
}
async function reportDownload(){
  const btn=$('#weekly-report-download'),status=$('#weekly-report-status');btn.disabled=true;status.textContent='Génération du PDF…';
  try{const q=reportFormQuery(),r=await fetch('/api/supervision/report.pdf?'+q,{credentials:'same-origin'});if(!r.ok){let msg='Impossible de générer le PDF';try{const j=await r.json();msg=j.error||msg;}catch{}throw new Error(msg);}const blob=await r.blob(),cd=r.headers.get('Content-Disposition')||'',m=cd.match(/filename="?([^";]+)"?/i),name=m?m[1]:'Nelyio_Rapport.pdf',url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=name;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1500);status.textContent='PDF généré avec succès.';}
  catch(e){status.textContent=e.message;}finally{btn.disabled=!weeklyReportCurrent?.reportlab_available||!reportValidatePeriod().valid;}
}
async function reportsView(){
  clearTimeout(supTimer);activate('reports');setHead('Rapports Nelyio','Aperçu web structuré, comparaison de périodes et audit technique détaillé avec PDF. Jusqu’à 30 jours par rapport.');
  app.innerHTML='<div class="loading">Préparation du module de rapports…</div>';
  let info;try{info=await api('/api/supervision/report-preview?report_type=overview');}catch(e){app.innerHTML=flash(e.message,'error');return;}if(location.hash!=='#reports')return;weeklyReportCurrent=info;
  app.innerHTML=`<section class="sup-hero report-hero"><div><span class="sup-eyebrow">RAPPORTS · NELYIO</span><h2>Un rapport pour chaque besoin.</h2><p>La vue d’ensemble applique vos Priorités Support aux agents/postes à examiner. La comparaison utilise la période précédente de même durée, avec les mêmes filtres et policies. Le rapport détaillé conserve toutes les preuves techniques en annexes.</p></div></section>
  <form id="weekly-report-form" class="card report-form">
    <fieldset class="report-type-selector"><legend>Choisir le rapport à générer</legend><div class="report-type-grid">
      <label class="report-type-card selected"><input type="radio" name="report_type" value="overview" checked><span class="report-type-icon">01</span><strong>Vue d’ensemble</strong><small>Top 20 Support · score configuré · priorités</small></label>
      <label class="report-type-card"><input type="radio" name="report_type" value="comparison"><span class="report-type-icon">02</span><strong>Comparaison de périodes</strong><small>Périodes de même durée · tendances · graphiques</small></label>
      <label class="report-type-card"><input type="radio" name="report_type" value="detailed"><span class="report-type-icon">03</span><strong>Rapport détaillé</strong><small>Tous les agents · toutes les coupures · anomalies · inactifs · signaux</small></label>
    </div></fieldset>
    <label>Type de période<select name="period_mode" id="report-period-mode"><option value="week">Semaine ISO</option><option value="last30">30 jours glissants</option><option value="custom">Dates personnalisées (max 30 jours)</option></select></label>
    <label id="report-week-wrap">Semaine ISO<input type="week" name="week" id="report-week" value="${esc(info.week)}"></label>
    <label id="report-last30-wrap" hidden>30 jours jusqu’au<input type="date" name="date_to" id="report-last30-end" value="${esc(info.reference_day||info.date_to)}" disabled></label>
    <div id="report-custom-period" class="report-custom-period" hidden><label>Du<input type="date" name="date_from" id="report-date-from" value="${esc(info.date_from)}"></label><label>Au<input type="date" name="date_to" id="report-date-to" value="${esc(info.date_to)}"></label></div>
    <p id="report-period-feedback" class="report-period-feedback" role="status" aria-live="polite"></p>
    ${nelyioCommonFilterFields(info,'reports',{includeDates:false,includeAgentGroup:false})}
    <label>Filtre appels ODCalls<select name="call_issue"><option value="all">Tous les appels</option><option value="short">Conversations courtes 1–10 s</option><option value="end_code">EndReason non nul</option><option value="abandon">Abandons</option><option value="no_agent">Sans agent</option><option value="invalid">Durées incohérentes</option></select></label>
    <fieldset class="report-filter-wide report-picker" id="report-group-picker"><legend>Filtrer par groupe(s)</legend><p>Sans sélection = tous les groupes.</p><div class="report-picker-toolbar"><input type="search" id="report-group-search" placeholder="Rechercher un groupe…"><div class="report-picker-buttons"><button type="button" class="button ghost tiny" data-picker-action="select-visible">Tout visible</button><button type="button" class="button ghost tiny" data-picker-action="clear">Effacer</button></div></div><div class="report-picker-state"><strong data-picker-count>0 sélectionné</strong><div class="report-picker-chips" data-picker-chips></div></div><div class="report-check-list">${reportGroupChecks(info.available_groups)}</div></fieldset>
    <fieldset class="report-filter-wide report-picker" id="report-include-picker"><legend>Agents à inclure</legend><p>Sans sélection = tous les agents du/des groupe(s).</p><div class="report-picker-toolbar"><input type="search" id="report-include-search" placeholder="Rechercher nom, identifiant ou groupe…"><div class="report-picker-buttons"><button type="button" class="button ghost tiny" data-picker-action="select-visible">Tout visible</button><button type="button" class="button ghost tiny" data-picker-action="clear">Effacer</button></div></div><div class="report-picker-state"><strong data-picker-count>0 sélectionné</strong><div class="report-picker-chips" data-picker-chips></div></div><div class="report-check-list">${reportAgentChecks(info.available_agents,'include_agent')}</div></fieldset>
    <fieldset class="report-filter-wide report-picker report-picker-danger" id="report-exclude-picker"><legend>Agents à exclure</legend><p>Ils sont retirés de tous les calculs et de toutes les annexes.</p><div class="report-picker-toolbar"><input type="search" id="report-exclude-search" placeholder="Rechercher nom, identifiant ou groupe…"><div class="report-picker-buttons"><button type="button" class="button ghost tiny" data-picker-action="select-visible">Tout visible</button><button type="button" class="button ghost tiny" data-picker-action="clear">Effacer</button></div></div><div class="report-picker-state"><strong data-picker-count>0 sélectionné</strong><div class="report-picker-chips" data-picker-chips></div></div><div class="report-check-list">${reportAgentChecks(info.available_agents,'exclude_agent')}</div></fieldset>
    <div class="report-actions"><button class="button" type="submit">Actualiser l’aperçu</button><button class="button ghost" type="button" id="weekly-report-download">Générer le rapport PDF</button><button class="button ghost" type="reset" id="report-reset">Réinitialiser les filtres</button><span id="weekly-report-status"></span></div>
  </form><div id="weekly-report-preview">${reportPreviewHtml(info)}</div>`;
  weeklyReportCurrentQuery=reportFormQuery();reportBindPreview();
  $('#weekly-report-form').onsubmit=e=>{e.preventDefault();reportLoadPreview();};$('#weekly-report-download').onclick=reportDownload;
  $('#report-period-mode').onchange=()=>{weeklyReportRequest++;reportSyncPeriodMode();$('#weekly-report-status').textContent='Période modifiée : actualiser l’aperçu.';};reportSyncPeriodMode();
  for(const id of ['report-week','report-date-from','report-date-to','report-last30-end'])$('#'+id).oninput=()=>{weeklyReportRequest++;reportPeriodFeedback();$('#weekly-report-status').textContent='Période modifiée : actualiser l’aperçu.';};
  reportInitPicker('#report-group-picker','#report-group-search');reportInitPicker('#report-include-picker','#report-include-search');reportInitPicker('#report-exclude-picker','#report-exclude-search');
  const syncType=()=>{document.querySelectorAll('.report-type-card').forEach(card=>card.classList.toggle('selected',!!card.querySelector('input:checked')));};
  document.querySelectorAll('input[name="report_type"]').forEach(i=>i.onchange=()=>{syncType();reportLoadPreview();});syncType();
  $('#report-reset').onclick=()=>setTimeout(()=>{reportSyncPeriodMode();reportResetPickers();syncType();reportLoadPreview();},0);
  $('#weekly-report-download').disabled=!info.reportlab_available;
}
