/* F4.2. Agents and files, two analyses, one source. Never mix routing levels with agent levels. */
const qualityDefaultState = view => ({view, data:null, search:'', group:'', campaign:'', agent:'', line:'', status:'', kind:view==='bases'?'queue':'', range:'', source:'', includeUnknown:view==='bases', divisor:100, page:0, size:25, sort:'', direction:'default', open:null});
const qualityStates = {agents:qualityDefaultState('agents'), bases:qualityDefaultState('bases')};
let qualityState=qualityStates.agents, qualityGeneration=0;
function qualitySortPersist(view,state){try{if(state.sort&&state.direction!=='default')sessionStorage.setItem('nelyio.rc29.quality-config.'+view,JSON.stringify({key:state.sort,direction:state.direction}));else sessionStorage.removeItem('nelyio.rc29.quality-config.'+view);}catch(_){}}
function qualitySortRestore(view,state){try{const v=JSON.parse(sessionStorage.getItem('nelyio.rc29.quality-config.'+view)||'null');if(v&&v.key&&['asc','desc'].includes(v.direction)){state.sort=v.key;state.direction=v.direction;}}catch(_){}}
const qualityDefined=v=>v!==null&&v!==undefined&&v!=='';
const qualityText=v=>qualityDefined(v)?String(v):'\u2014';
const qualityFold=v=>String(v||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLocaleLowerCase('fr');
const qualityCampaignKey=c=>String(c.campaign_id||'name:'+String(c.campaign_name||'').toLocaleLowerCase('fr'));
function qualityAgentName(a){return a?(a.directory_name||[a.agent_last_name,a.agent_first_name].filter(Boolean).join(' ')||a.login||a.agent_id):'Affectation non fournie';}
function qualityCampaignName(c){return c.display_name||c.campaign_name||`Campagne ${c.campaign_id} (nom non fourni)`;}
function qualityDate(day){return /^\d{4}-\d{2}-\d{2}$/.test(day||'')?day.split('-').reverse().join('/'):day||'date non fournie';}
function qualitySourceDay(scope){const d=qualityState.data;return qualityDate(d.scope_sources?.[scope]?.day||d.source_day);}
function qualityGroupLabel(g){return g.name+(g.supervision_id?` \u00b7 ID ${g.supervision_id}`:'');}
// scope_groups are labelled analysis links; groups remain registered memberships.
function qualityGroups(r){
  if(qualityState.view==='agents')return r.assignment?.scope_groups??r.agent?.scope_groups??r.agent?.groups??(r.agent?.group_id?[{group_id:r.agent.group_id,group_name:r.agent.group_name,supervision_id:r.agent.supervision_group_id}]:[]);
  return r.target.scope_groups??r.target.groups??[];
}
function qualityGroupOrigin(g){return g.automatic?(g.linked?'Automatique par file':'Manuel + automatique'):(g.linked?'Li\u00e9 depuis les bases':'Enregistr\u00e9');}
function qualityRelatedCampaigns(r){return r.kind==='queue'?(r.target.campaigns||[]):r.kind==='campaign'?[r.target]:[];}
function qualityTargetName(r){
  // Explicit file names remain authoritative; linked campaign names are only fallback labels.
  if(r.kind==='queue'&&r.target.line_name)return r.target.line_name;
  if(r.kind==='queue'&&qualityState.view==='agents'&&qualityState.campaign){const c=qualityRelatedCampaigns(r).find(c=>qualityCampaignKey(c)===qualityState.campaign);if(c)return qualityCampaignName(c);}
  return r.kind==='queue'?(r.target.display_name||'Nom de file non fourni'):r.kind==='campaign'?qualityCampaignName(r.target):'Affectations non fournies';
}
function qualityObserved(r){
  const obs=(r.target.observations||[]).filter(o=>qualityState.view==='bases'||!qualityState.campaign||String(o.campaign_id)===qualityState.campaign);
  const values=[...new Set(obs.flatMap(o=>(o.raw_priorities||[]).map(p=>Number(p.value)/qualityState.divisor)))].sort((a,b)=>a-b);
  return {values,observations:obs};
}
function qualityBase(r){const o=qualityObserved(r);return qualityDefined(r.target.base_priority_level)?{values:[r.target.base_priority_level],source:'configured',label:'Configur\u00e9e',observations:o.observations}:{...o,source:o.values.length?'observed':'missing',label:o.values.length?(qualityState.divisor===1?'Observ\u00e9e brute':'Observ\u00e9e \u00f7 100*'):'Non fournie'};}
function qualityRows(){
  const d=qualityState.data, rows=[], queues=new Map((d.queues||[]).map(q=>[String(q.line_id),q]));
  const campaigns=new Map((d.campaigns||[]).map(c=>[qualityCampaignKey(c),c]));
  const members=new Map();
  for(const a of d.agents||[]){
    for(const [kind,assignments] of [['queue',a.queues||[]],['campaign',a.campaign_assignments||[]]]){
      for(const x of assignments){
        const id=kind==='queue'?String(x.line_id):qualityCampaignKey(x), key=`${kind}:${id}`;
        const target=(kind==='queue'?queues:campaigns).get(id)||x;
        const row={key:`${key}:${a.agent_id}`,kind,agent:a,target,assignment:x};
        rows.push(row);if(!members.has(key))members.set(key,[]);members.get(key).push(row);
      }
    }
    if(!a.queues?.length&&!a.campaign_assignments?.length)rows.push({key:`agent:${a.agent_id}`,kind:'agent',agent:a,target:{},assignment:{}});
  }
  if(qualityState.view==='agents')return rows;
  const bases=[];
  // Keep every catalogue entry accessible, without manufacturing memberships.
  // One row per file, independent of the number of assigned agents.
  for(const [kind,catalogue] of [['queue',queues]])for(const [id,t] of catalogue){
    const target={...t};
    if(kind==='campaign')target.observations=(d.queues||[]).flatMap(q=>(q.observations||[]).filter(o=>String(o.campaign_id)===id).map(o=>({...o,line_id:q.line_id})));
    const key=`${kind}:${id}`;bases.push({key,kind,agent:null,target,assignment:{},members:members.get(key)||[]});
  }
  return bases;
}
function qualityStatus(r){return r.assignment.activation_state||'unknown';}
function qualityStatusLabel(r){return ({active:'Actif',inactive:'Inactif',partial:'Partiel',unknown:'Non fourni'})[qualityStatus(r)]||'Non fourni';}
function qualityFilteredRows(){
  const s=qualityState,needle=qualityFold(s.search);
  const rows=qualityRows().filter(r=>{
    const p=r.assignment.agent_priority_level,b=qualityBase(r),groups=qualityGroups(r);
    if(!s.includeUnknown&&(s.view==='agents'?!qualityDefined(p):!b.values.length))return false;
    if(s.view==='agents'&&s.kind&&r.kind!==s.kind)return false;
    if(s.line&&(r.kind!=='queue'||String(r.target.line_id)!==s.line))return false;
    if(s.view==='agents'&&s.agent&&String(r.agent?.agent_id)!==s.agent)return false;
    if(s.group==='none'&&groups.length)return false;
    if(s.group&&s.group!=='none'&&!groups.some(g=>String(g.group_id)===s.group))return false;
    if(s.view==='agents'&&s.campaign&&!qualityRelatedCampaigns(r).some(c=>qualityCampaignKey(c)===s.campaign))return false;
    if(s.view==='agents'&&s.status&&qualityStatus(r)!==s.status)return false;
    if(s.view==='agents'&&s.range&&(!qualityDefined(p)||(s.range==='high'?p<90:s.range==='medium'?(p<50||p>89):p>=50)))return false;
    if(s.view==='bases'&&s.source&&b.source!==s.source)return false;
    return !needle||qualityFold([qualityAgentName(r.agent),r.agent?.agent_id,r.agent?.login,qualityTargetName(r),r.target.line_id,r.target.campaign_id,...qualityRelatedCampaigns(r).map(qualityCampaignName)].join(' ')).includes(needle);
  });
  const effectiveSort=s.sort||(s.view==='bases'?'target':'agent'),effectiveDirection=s.sort?s.direction:'asc';
  const val=r=>({agent:()=>qualityAgentName(r.agent),target:()=>qualityTargetName(r),group:()=>qualityGroups(r).map(g=>g.group_name).join(' / '),base:()=>r.target.base_priority_level??null,observed:()=>qualityObserved(r).values[0]??null,status:()=>({active:3,partial:2,inactive:1,unknown:null}[qualityStatus(r)]??null),count:()=>r.members?.length||0,agentPriority:()=>r.assignment.agent_priority_level??null}[effectiveSort]||(()=>qualityTargetName(r)))();
  rows.sort((a,b)=>{const x=val(a),y=val(b),xm=x===null||x===undefined||x==='',ym=y===null||y===undefined||y==='';if(xm||ym){if(xm&&ym)return 0;return xm?1:-1;}const cmp=typeof x==='number'&&typeof y==='number'?x-y:String(x).localeCompare(String(y),'fr',{numeric:true,sensitivity:'base'});return (effectiveDirection==='desc'?-cmp:cmp)||qualityTargetName(a).localeCompare(qualityTargetName(b),'fr',{numeric:true})||String(a.agent?.agent_id||'').localeCompare(String(b.agent?.agent_id||''),'fr',{numeric:true});});
  return rows;
}
function qualityAgentPill(v){return !qualityDefined(v)?'<span class="q-muted">\u2014</span>':`<span class="q-priority ${v>=90?'high':v>=50?'medium':'low'}">${esc(v)}</span>`;}
function qualitySortHeader(key,label){const active=qualityState.sort===key&&qualityState.direction!=='default';return `<button type="button" class="q-sort" data-sort="${key}">${label}${active?(qualityState.direction==='asc'?' \u2191':' \u2193'):' \u2195'}</button>`;}
function qualityObservedHtml(r){const o=qualityObserved(r);return o.values.length?`<span class="q-base">${esc(o.values.length<=3?o.values.join(' / '):`${o.values[0]}\u2013${o.values.at(-1)}`)}</span><small class="q-source observed">${qualityState.divisor===1?'Brut':'\u00f7 100, \u00e0 confirmer'}${o.values.length>1?' \u00b7 variable':''}</small>`:'<span class="q-muted">\u2014</span>';}
function qualityDetail(r){
  const a=r.assignment,o=qualityObserved(r),agentView=qualityState.view==='agents';
  return `<tr class="q-detail"><td colspan="6"><div class="q-detail-content"><div><strong>${esc(qualityTargetName(r))}</strong><p>Priorit\u00e9 base configur\u00e9e : <b>${esc(qualityText(r.target.base_priority_level))}</b></p>${agentView?`<p>Priorit\u00e9 agent : <b>${esc(qualityText(a.agent_priority_level))}</b> \u00b7 ${esc(qualityStatusLabel(r))}</p><p>Activation au d\u00e9marrage des contextes, pas la pr\u00e9sence en ligne. D\u00e9lai : ${esc(qualityText(a.delay_seconds))} s. Contextes : ${esc((a.start_contexts||[]).join(', ')||'non fournis')}.</p>`:`<p>${r.members.length} affectation(s) configur\u00e9e(s). Le tableau ci-dessous n'utilise pas l'activit\u00e9 observ\u00e9e comme preuve d'affectation.</p><div class="q-members-scroll"><table class="q-observations"><thead><tr><th>Agent</th><th>Priorit\u00e9 agent</th><th>Activation</th></tr></thead><tbody>${r.members.map(m=>`<tr><td>${esc(qualityAgentName(m.agent))}<small>${esc(m.agent.login)}</small></td><td>${qualityAgentPill(m.assignment.agent_priority_level)}</td><td>${esc(qualityStatusLabel(m))}</td></tr>`).join('')||'<tr><td colspan="3">Aucune affectation fournie.</td></tr>'}</tbody></table></div>`}<p>Groupes : ${esc(qualityGroups(r).map(g=>g.group_name+' ('+qualityGroupOrigin(g)+')').join(', ')||'Non affect\u00e9')}</p><p>Campagnes li\u00e9es : ${esc(qualityRelatedCampaigns(r).map(qualityCampaignName).join(' \u00b7 ')||'Non fournies')}</p></div><div><strong>Observations d'appels \u00b7 ${qualitySourceDay('observations')}</strong><table class="q-observations"><thead><tr><th>File / campagne</th><th>InitPriority brut</th><th>Brut \u00f7 ${qualityState.divisor}</th></tr></thead><tbody>${o.observations.map(x=>`<tr><td>${esc([x.line_id,x.display_name||x.campaign_name||x.campaign_id].filter(Boolean).join(' \u00b7 '))}</td><td>${esc(x.raw_priorities.map(v=>v.value).join(' / '))}</td><td>${esc(x.raw_priorities.map(v=>v.value/qualityState.divisor).join(' / '))}</td></tr>`).join('')||'<tr><td colspan="3">Aucune observation fournie.</td></tr>'}</tbody></table><p>Ces observations ne prouvent pas la configuration actuelle. Aucune priorit\u00e9 agent n'en est d\u00e9duite.</p></div></div></td></tr>`;
}
function qualityGroupHtml(r){
  const groups=qualityGroups(r);return groups.length?groups.map(g=>`<span class="q-group-badge ${g.linked?'q-group-linked':''}" title="${esc(qualityGroupOrigin(g)+(g.supervision_id?' \u00b7 ID supervision '+g.supervision_id:'')+(g.linked?' : affectation configur\u00e9e, pas appartenance officielle.':''))}">${esc(g.group_name)}${g.automatic?' <small>Auto</small>':g.linked?' <small>Li\u00e9</small>':''}</span>`).join(' '):'<span class="q-muted">Sans lien de groupe</span>';
}
function qualityGroupOption(g){
  const d=qualityState.data,agentView=qualityState.view==='agents';
  const count=agentView?(d.agents||[]).filter(a=>(a.scope_groups??a.groups??[{group_id:a.group_id}]).some(x=>String(x.group_id)===String(g.id))).length:(d.queues||[]).filter(q=>(q.scope_groups??q.groups??[]).some(x=>String(x.group_id)===String(g.id))).length;
  return qualityGroupLabel(g)+` \u00b7 ${count} ${agentView?'agents':'files'}${count?'':' (\u00e0 compl\u00e9ter)'}`;
}
function qualityGroupHint(){
  const el=$('#q-group-hint');if(!el)return;
  const s=qualityState,d=s.data,agentView=s.view==='agents',g=(d.groups||[]).find(g=>String(g.id)===s.group);
  const catalogue=agentView?(d.agents||[]):(d.queues||[]),groups=x=>x.scope_groups??x.groups??[];
  let message='Automatique : file class\u00e9e dans un groupe \u2192 agents affect\u00e9s. Plusieurs groupes possibles ; seules les affectations ACTIVE sont incluses.';
  if(!(d.groups||[]).length)message='Aucun groupe enregistr\u00e9. La reprise des groupes au d\u00e9marrage est \u00e0 v\u00e9rifier.';
  else if(g&&!catalogue.some(x=>groups(x).some(t=>String(t.group_id)===s.group)))message=`${g.name} : aucune affectation pour les files connues. Dans Administration \u2192 Groupes, rattacher les files de ce groupe ; les agents suivront automatiquement.`;
  else if(s.group==='none')message='Affectations sans lien de groupe connu. Elles restent consultables, sans rattachement arbitraire.';
  el.hidden=!message;
  el.innerHTML=message?`<span>${esc(message)}</span>${canRead('classification')?'<a href="#classification-groups">Voir les groupes</a>':''}`:'';
}
function qualityRender(){
  const host=$('#quality-results');if(!host||!qualityState.data)return;
  const s=qualityState,rows=qualityFilteredRows(),agentView=s.view==='agents',pages=Math.max(1,Math.ceil(rows.length/s.size));s.page=Math.max(0,Math.min(s.page,pages-1));
  const start=s.page*s.size,shown=rows.slice(start,start+s.size);
  const headers=agentView?[['agent','Agent'],['target','File / campagne'],['agentPriority','Priorit\u00e9 agent'],['status','Activation'],['detail','D\u00e9tail']]:[['target','File'],['group','Groupe'],['base','Priorit\u00e9 de la file'],['observed','Observ\u00e9e*'],['count','Agents affect\u00e9s'],['detail','D\u00e9tail']];
  const target=r=>`<strong class="q-target">${esc(qualityTargetName(r))}</strong><small>${r.kind==='queue'?`File ${esc(r.target.line_id)}`:r.kind==='campaign'?`Campagne ${esc(r.target.campaign_id||'sans ID')}`:'Annuaire'}</small>`;
  host.innerHTML=`<div class="table-wrap q-table-wrap"><table class="q-table q-${s.view}-table"><thead><tr>${headers.map(([key,label])=>`<th>${key==='detail'?label:qualitySortHeader(key,label)}</th>`).join('')}</tr></thead><tbody>${shown.map(r=>`<tr>${agentView?`<td><strong>${esc(qualityAgentName(r.agent))}</strong><small>${esc(r.agent?.login||'')}</small>${qualityGroupHtml(r)}</td><td>${target(r)}</td><td>${qualityAgentPill(r.assignment.agent_priority_level)}</td><td><span class="q-status ${qualityStatus(r)}" title="Configuration au d\u00e9marrage, pas le statut en ligne">${esc(qualityStatusLabel(r))}</span></td>`:`<td>${target(r)}</td><td>${qualityGroupHtml(r)}</td><td><strong>${esc(qualityText(r.target.base_priority_level))}</strong><small>${qualityDefined(r.target.base_priority_level)?'Configur\u00e9e':'Non fournie'}</small></td><td>${qualityObservedHtml(r)}</td><td>${r.members.length}</td>`}<td><button type="button" class="button ghost small q-open" data-key="${esc(r.key)}" aria-expanded="${s.open===r.key}">${s.open===r.key?'Fermer':'D\u00e9tail'}</button></td></tr>${s.open===r.key?qualityDetail(r).replace('colspan="6"',`colspan="${headers.length}"`):''}`).join('')||`<tr><td colspan="${headers.length}" class="q-empty">Aucune ligne pour ces filtres. R\u00e9initialiser ou afficher aussi les lignes sans priorit\u00e9.</td></tr>`}</tbody></table></div><div class="q-footer"><span>${rows.length?`${start+1}\u2013${Math.min(start+s.size,rows.length)} sur ${rows.length}`:'0'} ${agentView?'affectations':'files'}</span><div><label class="q-page-size">Par page<select id="q-size"><option>25</option><option>50</option><option>100</option></select></label><button id="q-prev" class="button ghost small" ${s.page===0?'disabled':''}>Pr\u00e9c\u00e9dent</button><span>${s.page+1} / ${pages}</span><button id="q-next" class="button ghost small" ${s.page>=pages-1?'disabled':''}>Suivant</button></div></div>`;
  host.querySelectorAll('[data-sort]').forEach(btn=>btn.onclick=()=>{const key=btn.dataset.sort;if(s.sort!==key||s.direction==='default'){s.sort=key;s.direction='asc';}else if(s.direction==='asc'){s.direction='desc';}else{s.sort='';s.direction='default';}qualitySortPersist(s.view,s);s.page=0;qualityRender();});
  host.querySelectorAll('.q-open').forEach(btn=>btn.onclick=()=>{s.open=s.open===btn.dataset.key?null:btn.dataset.key;qualityRender();});
  $('#q-prev').onclick=()=>{s.page--;qualityRender();};$('#q-next').onclick=()=>{s.page++;qualityRender();};$('#q-size').value=s.size;$('#q-size').onchange=e=>{s.size=Number(e.target.value);s.page=0;qualityRender();};
  $('#q-filter-note').textContent=agentView?'Les valeurs restent celles de la configuration import\u00e9e. Inactif ne signifie pas priorit\u00e9 z\u00e9ro.':'* Observation d\u2019appels distincte de la priorit\u00e9 configur\u00e9e. Conversion \u00f7 100 \u00e0 confirmer ; valeurs brutes dans D\u00e9tail.';
  qualityGroupHint();
}
function qualityDownload(blob,name){const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
function qualityExportRows(){return qualityFilteredRows().map(r=>{
  const common=qualityState.view==='agents'?{'File / campagne':qualityTargetName(r),'Type':r.kind,'LineId':r.target.line_id??'','CampaignId':r.target.campaign_id||'','Groupes':qualityGroups(r).map(g=>g.group_name).join(' | '),'Origine des groupes':qualityGroups(r).map(g=>g.group_name+' : '+qualityGroupOrigin(g)).join(' | ')}:{'File':qualityTargetName(r),'LineId':r.target.line_id??'','Groupes':qualityGroups(r).map(g=>g.group_name).join(' | '),'Origine des groupes':qualityGroups(r).map(g=>g.group_name+' : '+qualityGroupOrigin(g)).join(' | ')};
  if(qualityState.view==='agents')return {'Agent':qualityAgentName(r.agent),'Agent ID':r.agent?.agent_id||'','Login':r.agent?.login||'',...common,'Priorit\u00e9 agent':r.assignment.agent_priority_level??'','Activation':qualityStatusLabel(r),'Contextes':(r.assignment.start_contexts||[]).join(' | '),'Source activation':r.assignment.activation_source||'','Date configuration':qualitySourceDay('agent_queues')};
  const o=qualityObserved(r);return {...common,'Priorit\u00e9 base configur\u00e9e':r.target.base_priority_level??'','Valeur observee':o.values.join(' | '),'Diviseur observation':qualityState.divisor,'InitPriority brut':o.observations.map(x=>`${x.line_id||r.target.line_id||''}/${x.campaign_id}: ${x.raw_priorities.map(v=>v.value).join('/')}`).join(' | '),'Agents affectes':r.members.length,'Date observations':qualitySourceDay('observations')};
});}
function qualityExportCsv(){const rows=qualityExportRows();if(!rows.length)return;const h=Object.keys(rows[0]),cell=v=>{let t=String(v??'');if(/^[=+@\-\t\r\n]/.test(t))t="'"+t;return '"'+t.replace(/"/g,'""')+'"';};qualityDownload(new Blob(['\ufeff'+[h,...rows.map(r=>h.map(k=>r[k]))].map(r=>r.map(cell).join(';')).join('\r\n')],{type:'text/csv;charset=utf-8'}),`nelyio_priorites_${qualityState.view==='bases'?'files':'agents'}.csv`);}
function qualityExportExcel(){const rows=qualityExportRows();if(!rows.length)return;const h=Object.keys(rows[0]),xml=v=>String(v??'').replace(/[<>&"']/g,c=>({'<':'&lt;','>':'&gt;','&':'&amp;','"':'&quot;',"'":'&apos;'}[c]));const data=[h,...rows.map(r=>h.map(k=>r[k]))].map(r=>'<Row>'+r.map(v=>`<Cell><Data ss:Type="String">${xml(v)}</Data></Cell>`).join('')+'</Row>').join('');qualityDownload(new Blob([`<?xml version="1.0" encoding="UTF-8"?><Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet" xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet"><Worksheet ss:Name="Priorites"><Table>${data}</Table></Worksheet></Workbook>`],{type:'application/vnd.ms-excel'}),`nelyio_priorites_${qualityState.view==='bases'?'files':'agents'}.xml`);}
async function qualityImport(file){
  if(!file)return;const view=qualityState.view;
  if(file.size>100*1024*1024){$('#q-notice').innerHTML=flash('Fichier trop volumineux : 100 Mo maximum.','error');return;}
  $('#q-import').disabled=true;$('#q-notice').innerHTML=flash('Lecture de la configuration\u2026');
  try{const r=await api('/api/quality/import?filename='+encodeURIComponent(file.name),{method:'POST',body:file,headers:{'Content-Type':'application/octet-stream'}});if(!location.hash.startsWith('#quality-'))return;await qualityPrioritiesView(view);$('#q-notice').innerHTML=flash(r.updated?'Import termin\u00e9. Catalogues actualis\u00e9s ; groupes manuels conserv\u00e9s.':r.message||'Source plus ancienne, donn\u00e9es conserv\u00e9es.',r.updated?'success':'warn');}
  catch(e){if($('#q-notice'))$('#q-notice').innerHTML=flash(e.message,'error');}finally{if($('#q-import'))$('#q-import').disabled=false;}
}
async function qualityPrioritiesView(view='agents'){
  if(!canRead('quality')){redirectAllowed();return;}
  qualityState=qualityStates[view]||qualityStates.agents;qualitySortRestore(qualityState.view,qualityState);
  const s=qualityState,agentView=s.view==='agents',generation=++qualityGeneration;
  // Old file/campaign bookmarks must never resurrect campaign rows or filters.
  if(!agentView){s.campaign='';s.kind='queue';}
  activate('quality-'+s.view);setHead(agentView?'Priorit\u00e9s des agents':'Priorit\u00e9s des files',agentView?'Niveau et activation de chaque agent sur ses affectations.':'Une ligne par file : groupe, priorit\u00e9 et agents affect\u00e9s.');app.innerHTML='<div class="loading">Chargement\u2026</div>';
  try{
    const d=await api('/api/quality/priorities');if(generation!==qualityGeneration||!location.hash.startsWith('#quality-'))return;s.data=d;s.open=null;
    const opt=(v,t)=>`<option value="${esc(v)}">${esc(t)}</option>`;
    const fileOptions=opt('','Toutes les files')+(d.queues||[]).map(q=>opt(q.line_id,`${q.line_id} \u00b7 ${q.display_name}`)).join('');
    app.innerHTML=`<section class="q-page"><div class="q-toolbar"><div class="q-main-filters"><label>Rechercher<input id="quality-search" placeholder="${agentView?'Agent, nom de file ou identifiant':'Nom de file ou identifiant'}" value="${esc(s.search)}"></label><label>${agentView?'Groupe des agents':'Groupe des files'}<select id="quality-group">${opt('','Tous les groupes')}${opt('none','Sans lien de groupe')}${(d.groups||[]).map(g=>opt(g.id,qualityGroupOption(g))).join('')}</select></label>${agentView?`<label>Campagne<select id="quality-campaign">${opt('','Toutes les campagnes')}${(d.campaigns||[]).map(c=>opt(qualityCampaignKey(c),qualityCampaignName(c))).join('')}</select></label>`:`<label>File<select id="quality-line">${fileOptions}</select></label>`}</div><div class="q-actions"><button class="button ghost small" id="q-reset">R\u00e9initialiser</button><button class="button ghost small" id="q-refresh">Actualiser</button><details class="q-export"><summary>Exporter</summary><button id="q-csv" class="button ghost small">CSV filtr\u00e9</button><button id="q-excel" class="button ghost small">Excel XML filtr\u00e9</button></details>${canWrite('classification')?'<span class="q-note" title="Import s\u00e9par\u00e9 du Web en V60">Import : OPEN_NELYIO_IMPORTER.bat</span>':''}${canRead('classification')?'<a class="button ghost small" href="#classification-groups">G\u00e9rer les groupes</a>':''}</div></div>
    <details class="q-more"><summary>Plus de filtres</summary><div class="q-secondary">${agentView?`<label>Agent<select id="quality-agent">${opt('','Tous les agents')}${d.agents.map(a=>opt(a.agent_id,`${qualityAgentName(a)} \u00b7 ${a.login}`)).join('')}</select></label><label>Priorit\u00e9 agent<select id="quality-priority">${opt('','Toutes')}${opt('high','90\u201399')}${opt('medium','50\u201389')}${opt('low','0\u201349')}</select></label><label>Activation<select id="quality-status">${opt('','Tous les \u00e9tats')}${opt('active','Actif')}${opt('inactive','Inactif')}${opt('partial','Partiel')}${opt('unknown','Non fourni')}</select></label><label>File<select id="quality-line">${fileOptions}</select></label><label>Type<select id="quality-kind">${opt('','Files et campagnes')}${opt('queue','Files')}${opt('campaign','Campagnes')}</select></label>`:`<label>Source de la priorit\u00e9<select id="quality-source">${opt('','Toutes')}${opt('configured','Configuration fournie')}${opt('observed','Observation uniquement')}${opt('missing','Priorit\u00e9 non fournie')}</select></label><label>Observation InitPriority<select id="quality-scale">${opt(100,'Brut \u00f7 100 (\u00e0 confirmer)')}${opt(1,'Valeur brute')}</select></label>`}<label class="q-check"><input type="checkbox" id="quality-unknown" ${s.includeUnknown?'checked':''}>Afficher aussi sans priorit\u00e9</label></div></details>
    <div class="q-info" id="quality-source-info"><span>${agentView?`${d.stats.agents} agents dans la source \u00b7 ${d.stats.queues} affectations de file`:`${d.queues.length} files \u00b7 ${d.queues.filter(q=>(q.scope_groups??q.groups)?.length).length} avec un lien de groupe`}</span><span>Configuration agents : <b>${qualitySourceDay('agent_queues')}</b> \u00b7 Observations : ${qualitySourceDay('observations')}</span></div><div id="q-notice" role="status" aria-live="polite"></div><div id="q-group-hint" class="q-group-hint" role="status" hidden></div><div id="quality-results"></div><p class="q-note" id="q-filter-note"></p>
    <details class="q-help"><summary>Comprendre les donn\u00e9es</summary><p><b>Priorit\u00e9 agent</b> : Agents.csv \u2192 Queues \u2192 Level (0\u201399). <b>Priorit\u00e9 file</b> : champ de configuration explicite, peut d\u00e9passer 99. Une observation ne remplace jamais ce champ.</p><p>L'\u00e9tat Actif / Inactif / Partiel d\u00e9crit les contextes au d\u00e9marrage, pas la connexion en direct. La conversion InitPriority \u00f7 100 est propos\u00e9e d'apr\u00e8s tes exemples, son \u00e9chelle reste \u00e0 confirmer.</p><p>La r\u00e8gle automatique distribue les agents depuis les files explicitement rattach\u00e9es aux groupes. Un agent peut appartenir \u00e0 plusieurs groupes d'analyse sans changer de groupe principal. Un agent li\u00e9 via une file ne ram\u00e8ne pas toutes ses autres files dans ce groupe. Rien n'est d\u00e9duit des appels.</p><p>Source : ${esc(d.source_file||'non fournie')}. Un import met \u00e0 jour le catalogue, sans modifier les groupes enregistr\u00e9s.</p></details></section>`;
    for(const [id,key] of [['quality-group','group'],['quality-campaign','campaign'],['quality-agent','agent'],['quality-priority','range'],['quality-status','status'],['quality-kind','kind'],['quality-line','line'],['quality-source','source']]){const el=$('#'+id);if(!el)continue;el.value=s[key];if(el.selectedIndex<0){el.value='';s[key]='';}el.onchange=()=>{s[key]=el.value;s.page=0;s.open=null;qualityRender();};}
    $('#quality-search').oninput=e=>{s.search=e.target.value;s.page=0;qualityRender();};$('#quality-unknown').onchange=e=>{s.includeUnknown=e.target.checked;s.page=0;qualityRender();};
    if($('#quality-scale')){$('#quality-scale').value=s.divisor;$('#quality-scale').onchange=e=>{s.divisor=Number(e.target.value);qualityRender();};}
    $('#q-reset').onclick=()=>{qualityStates[s.view]=qualityDefaultState(s.view);qualityPrioritiesView(s.view);};$('#q-refresh').onclick=()=>qualityPrioritiesView(s.view);$('#q-csv').onclick=qualityExportCsv;$('#q-excel').onclick=qualityExportExcel;
    if($('#q-import')){$('#q-import').onclick=()=>$('#q-file').click();$('#q-file').onchange=e=>qualityImport(e.target.files[0]);}
    if(d.last_import_attempt?.reason==='invalid_export')$('#q-notice').innerHTML=flash('Dernier import refus\u00e9 : '+d.last_import_attempt.message,'warn');
    qualityRender();
    installGroupAutoRefresh();
  }catch(e){if(generation===qualityGeneration)app.innerHTML=flash(e.message,'error');}
}
// Backward compatible bookmarks now lead to the files-only target view.
function qualityAgentsView(){return qualityPrioritiesView('agents');}
function qualityBasesView(){return qualityPrioritiesView('bases');}
function qualityQueuesView(){return qualityBasesView();}
function qualityCampaignsView(){return qualityBasesView();}
