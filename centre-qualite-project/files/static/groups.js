/* F4.2: reference-driven editor for the SAME groups used in Administration.
   Candidate proposals are not official supervision memberships. No auto-save. */
const groupWorkspaceState={data:null,draft:null,tab:'agents',search:'',scope:'all',dirty:false,filter:'',generation:0};
function groupDraft(g){return {id:g?.id??null,name:g?.name||'',description:g?.description||'',supervision_id:g?.supervision_id||'',source_note:g?.source_note||'manual',agent_ids:new Set(g?.agent_ids||[]),line_ids:new Set((g?.line_ids||[]).map(String)),campaign_keys:new Set((g?.campaigns||[]).map(c=>c.key))};}
function groupCandidates(data,draft){
  // Exact configured relationships only. No ODCalls/observed_activity inference.
  const proposals=new Map();
  for(const a of data.agents||[]){
    if(draft.agent_ids.has(a.key))continue;
    const reason=[];
    for(const id of a.line_ids||[])if(draft.line_ids.has(String(id)))reason.push(`File ${id}`);
    for(const id of a.campaign_keys||[])if(draft.campaign_keys.has(id)){const c=data.campaigns.find(c=>c.key===id);reason.push(c?.name||id);}
    if(reason.length)proposals.set(a.key,{reason,blocked:!!a.group_id&&a.group_id!==draft.id});
  }
  return proposals;
}
// Direct navigation avoids loading unrelated network/policy configuration.
function groupWorkspaceView(){
  if(!canRead('classification')){redirectAllowed();return;}
  activate('classification-groups');setHead('Groupes','Les m\u00eames groupes dans Administration et les filtres Qualit\u00e9.');
  app.dataset.groupEditor='true';app.innerHTML='<div id="group-workspace"></div>';
  groupWorkspaceMount();
}
function groupWorkspacePending(){
  const d=groupWorkspaceState.data;if(!d)return [];
  return d.pending_templates||d.templates.filter(t=>!d.groups.some(g=>g.supervision_id===t.supervision_id||g.name.toLocaleLowerCase()===t.name.toLocaleLowerCase()));
}
function groupWorkspaceTemplate(sid){
  const s=groupWorkspaceState,t=s.data.templates.find(t=>t.supervision_id===sid);if(!t)return;
  if(s.dirty&&!confirm('Abandonner les modifications non enregistr\u00e9es ?'))return;
  const existing=s.data.groups.find(g=>g.supervision_id===sid||g.name.toLocaleLowerCase()===t.name.toLocaleLowerCase());
  s.draft=groupDraft(existing);s.draft.name=existing?.name||t.name;s.draft.supervision_id=sid;s.draft.source_note='capture_user_partial_validated';
  t.line_ids.forEach(id=>s.draft.line_ids.add(String(id)));s.dirty=true;s.tab='lines';s.scope='selected';s.search='';
  groupWorkspaceRender();groupWorkspaceMessage('Mod\u00e8le non enregistr\u00e9. V\u00e9rifie les affectations puis Enregistrer le groupe.','warn');
}
async function groupWorkspaceAddCapture(){
  const s=groupWorkspaceState,pending=groupWorkspacePending();if(!pending.length)return;
  const lines=pending.reduce((n,t)=>n+t.line_ids.length,0);
  const message=`Ajouter ${pending.length} groupe(s) de la capture ?\n${pending.map(t=>t.supervision_id+' - '+t.name).join('\n')}\n\n${lines} file(s) lisible(s) sur la capture seront li\u00e9es. Liste partielle \u00e0 compl\u00e9ter.\nAucun agent d\u00e9plac\u00e9, aucun groupe existant modifi\u00e9.${s.dirty?'\nLe brouillon non enregistr\u00e9 sera abandonn\u00e9.':''}`;
  if(!confirm(message))return;
  const button=$('#gw-add-capture');button.disabled=true;
  try{
    const result=await api('/api/groups/workspace/add-capture',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({revision:s.data.revision,supervision_ids:pending.map(t=>t.supervision_id)})});
    s.dirty=false;s.filter='';await groupWorkspaceLoad(result.created[0]?.id);
    groupWorkspaceMessage(`${result.created.length} groupe(s) ajout\u00e9(s). Choisis un groupe pour compl\u00e9ter ses agents et ses files.`);
  }catch(e){groupWorkspaceMessage(e.message,'error');if(document.contains(button))button.disabled=false;}
}
function groupWorkspaceMount(){
  const host=$('#group-workspace');if(!host||host.dataset.mounted)return;host.dataset.mounted='1';
  if(groupWorkspaceState.dirty&&groupWorkspaceState.data){groupWorkspaceRender();return;}
  groupWorkspaceLoad(groupWorkspaceState.draft?.id);
}
async function groupWorkspaceLoad(id=null){
  const host=$('#group-workspace');if(!host)return;
  const n=++groupWorkspaceState.generation;host.innerHTML='<div class="loading">Chargement des groupes et catalogues\u2026</div>';
  try{const data=await api('/api/groups/workspace');if(n!==groupWorkspaceState.generation||!document.contains(host))return;
    const s=groupWorkspaceState;s.data=data;s.dirty=false;s.draft=groupDraft(data.groups.find(g=>g.id===id)||data.groups.find(g=>g.supervision_id==='110')||data.groups.find(g=>g.scope_agent_count||g.scope_line_count)||data.groups[0]);s.search='';s.scope=s.draft.id?'database':'all';groupWorkspaceRender();
  }catch(e){if(document.contains(host)){host.innerHTML=flash(e.message,'error')+'<button class="button ghost small" id="gw-retry">Ressayer</button>';$('#gw-retry').onclick=()=>groupWorkspaceLoad(id);}}
}
function groupWorkspaceSelect(g){
  const s=groupWorkspaceState;if(s.dirty&&!confirm('Abandonner les modifications non enregistr\u00e9es de ce groupe ?'))return;
  s.draft=groupDraft(g);s.dirty=false;s.search='';s.scope=g?.id?'database':'all';s.tab='agents';groupWorkspaceRender();
}
function groupWorkspaceMessage(message,type='success'){const el=$('#gw-message');if(el)el.innerHTML=flash(message,type);}
function groupWorkspaceSetDirty(){groupWorkspaceState.dirty=true;const b=$('#gw-save');if(b)b.disabled=false;const note=$('#gw-dirty');if(note)note.textContent='Modifications non enregistr\u00e9es';}
function groupWorkspaceRender(){
  const host=$('#group-workspace'),s=groupWorkspaceState,d=s.data,g=s.draft;if(!host||!d||!g)return;
  const writable=canWrite('classification'),disabled=writable?'':'disabled';
  host.innerHTML=`<section class="gw"><div class="gw-head"><div><h2>${d.groups.length} groupes enregistr\u00e9s</h2><p>File du groupe \u2192 agents ACTIVE + campagnes + dur\u00e9es analytiques \u00b7 source du ${esc(qualityDate(d.source_day))}</p></div><button type="button" class="button ghost small" id="gw-refresh">Actualiser depuis les bases</button></div>
    ${d.assignment_warning?`<div class="flash warn"><strong>Projection des groupes incompl\u00e8te.</strong> ${esc(d.assignment_warning)}</div>`:''}
    ${groupWorkspacePending().length?`<div class="gw-pending-banner"><div><strong>${groupWorkspacePending().length} groupes de ta capture restent \u00e0 cr\u00e9er</strong><p>Ils ne sont pas encore enregistr\u00e9s et ne figurent donc pas dans les filtres Qualit\u00e9.</p></div>${writable?'<button type="button" class="button small" id="gw-add-capture">Ajouter ces groupes</button>':'<span>Demander \u00e0 un administrateur de les ajouter.</span>'}</div>`:''}
    <div class="gw-layout"><aside class="gw-sidebar"><div class="gw-side-tools"><input id="gw-group-search" placeholder="Rechercher un groupe" value="${esc(s.filter)}" aria-label="Rechercher un groupe">${writable?'<button id="gw-new" class="button small">+ Nouveau</button>':''}</div><div id="gw-groups" class="gw-group-list"></div><div id="gw-pending" class="gw-pending-list"></div></aside>
    <section class="gw-editor"><div class="gw-identity"><label>Nom du groupe<input id="gw-name" value="${esc(g.name)}" maxlength="60" placeholder="MED01, IMG2\u2026" ${disabled}></label><label>ID supervision<input id="gw-external" value="${esc(g.supervision_id)}" maxlength="64" placeholder="110 (optionnel)" ${disabled}></label></div>
    ${g.source_note.startsWith('capture_')?'<p class="gw-partial">Capture partielle : les agents et les files restent \u00e0 v\u00e9rifier. Les agents des files enregistr\u00e9es sont actualis\u00e9s depuis le dernier import.</p>':''}
    <details class="gw-options"><summary>Description</summary><label>Description<input id="gw-description" value="${esc(g.description)}" maxlength="300" ${disabled}></label><p>L'ID supervision identifie le groupe dans la t\u00e9l\u00e9phonie ; il ne remplace pas l'ID interne Nelyio.</p></details>
    <div class="gw-tabs" role="tablist">${[['agents','Agents',g.agent_ids.size],['lines','Files',g.line_ids.size],['campaigns','Campagnes',g.campaign_keys.size]].map(([key,label,count])=>`<button type="button" role="tab" aria-selected="${s.tab===key}" class="${s.tab===key?'active':''}" data-gw-tab="${key}">${label} <span>${s.scope==='database'?groupWorkspaceDbCount(key):count}</span></button>`).join('')}</div>
    <div class="gw-member-tools"><input id="gw-member-search" value="${esc(s.search)}" placeholder="Rechercher un nom ou ID" aria-label="Rechercher une affectation"><select id="gw-scope" aria-label="Filtrer les affectations">${g.id?'<option value="database">Depuis les bases</option>':''}<option value="all">Modifier les affectations</option><option value="selected">S\u00e9lectionn\u00e9s</option>${s.tab==='agents'?'<option value="suggested">Propositions \u00e0 valider</option>':''}</select></div><div id="gw-candidates-note" class="gw-hint"></div><div id="gw-members" class="gw-members" role="region" aria-label="Choix des affectations"></div>
    <div id="gw-message" role="status" aria-live="polite"></div><div class="gw-savebar"><span id="gw-dirty">${s.dirty?'Modifications non enregistr\u00e9es':'Aucune modification'}</span><div>${writable&&g.id?'<button id="gw-delete" class="button ghost small">Supprimer</button>':''}${writable?`<button id="gw-save" class="button" ${s.dirty?'':'disabled'}>Enregistrer le groupe</button>`:'<span>Lecture seule</span>'}</div></div>
    <p class="gw-footnote">R\u00e8gle active : les agents affect\u00e9s aux files enregistr\u00e9es du groupe sont ajout\u00e9s automatiquement pour l'analyse. Seules les affectations actives sont incluses. Plusieurs groupes sont possibles ; aucun groupe principal ni droit d'acc\u00e8s n'est modifi\u00e9.</p></section></div></section>`;
  groupWorkspaceGroups();groupWorkspaceMembers();installGroupAutoRefresh();
  $('#gw-group-search').oninput=e=>{s.filter=e.target.value;groupWorkspaceGroups();};
  $('#gw-new')?.addEventListener('click',()=>groupWorkspaceSelect(null));
  $('#gw-add-capture')?.addEventListener('click',groupWorkspaceAddCapture);
  $('#gw-refresh').onclick=()=>{if(!s.dirty||confirm('Abandonner le brouillon et actualiser le catalogue ?'))groupWorkspaceLoad(g.id);};
  for(const [id,key] of [['gw-name','name'],['gw-external','supervision_id'],['gw-description','description']])$('#'+id).oninput=e=>{g[key]=e.target.value;groupWorkspaceSetDirty();};
  host.querySelectorAll('[data-gw-tab]').forEach(b=>b.onclick=()=>{s.tab=b.dataset.gwTab;s.search='';s.scope=s.scope==='database'?'database':'all';groupWorkspaceRender();});
  $('#gw-member-search').oninput=e=>{s.search=e.target.value;groupWorkspaceMembers();};$('#gw-scope').value=s.scope;$('#gw-scope').onchange=e=>{s.scope=e.target.value;groupWorkspaceRender();};
  $('#gw-save')?.addEventListener('click',groupWorkspaceSave);
  $('#gw-delete')?.addEventListener('click',async()=>{if(!confirm(`Supprimer ${g.name} et ses affectations ? Les agents et donn\u00e9es de priorit\u00e9 ne seront pas supprim\u00e9s.`))return;try{await api('/api/groups/delete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:g.id})});s.dirty=false;await groupWorkspaceLoad();}catch(e){groupWorkspaceMessage(e.message,'error');}});

}
function groupWorkspaceGroups(){
  const s=groupWorkspaceState,host=$('#gw-groups');if(!host)return;const needle=qualityFold(s.filter);
  const visible=s.data.groups.filter(g=>qualityFold(g.name+' '+g.supervision_id).includes(needle));
  host.innerHTML=visible.map(g=>`<button type="button" class="gw-group ${s.draft.id===g.id?'active':''}" data-gw-id="${g.id}"><strong>${esc(g.name)}</strong><small>${g.supervision_id?'ID '+esc(g.supervision_id)+' \u00b7 ':''}${g.automatic_agent_ids?.length||0} auto \u00b7 ${g.agent_ids.length} manuels \u00b7 ${g.line_ids.length} files class\u00e9es${g.linked_lines?.length?' \u00b7 '+g.linked_lines.length+' files \u00e0 valider':''}${!(g.scope_agent_count||g.scope_line_count||g.scope_campaign_count||g.agent_ids.length||g.line_ids.length)?' \u00b7 \u00c0 compl\u00e9ter':''}</small></button>`).join('')||`<p class="gw-hint">${s.data.groups.length?'Aucun groupe pour cette recherche.':'Aucun groupe enregistr\u00e9. Cr\u00e9e un groupe ou utilise un mod\u00e8le ci-dessous.'}</p>`;
  host.querySelectorAll('[data-gw-id]').forEach(b=>b.onclick=()=>groupWorkspaceSelect(s.data.groups.find(g=>g.id===Number(b.dataset.gwId))));
  const pending=$('#gw-pending');if(!pending)return;
  const models=groupWorkspacePending().filter(t=>qualityFold(t.name+' '+t.supervision_id).includes(needle));
  pending.innerHTML=models.length?'<h3>Capture \u00b7 non enregistr\u00e9s</h3>'+models.map(t=>`<button type="button" class="gw-group gw-template" data-gw-template="${esc(t.supervision_id)}" ${canWrite('classification')?'':'disabled'}><strong>${esc(t.name)} <span class="gw-unsaved">\u00c0 cr\u00e9er</span></strong><small>ID ${esc(t.supervision_id)}</small></button>`).join(''):'';
  pending.querySelectorAll('[data-gw-template]').forEach(b=>b.onclick=()=>groupWorkspaceTemplate(b.dataset.gwTemplate));
}
function groupWorkspaceMembers(){
  const s=groupWorkspaceState,g=s.draft,d=s.data,host=$('#gw-members');if(!host)return;
  if(s.scope==='database'){groupWorkspaceDatabaseMembers();return;}
  const isAgent=s.tab==='agents',isLine=s.tab==='lines',key=isAgent?'agent_ids':isLine?'line_ids':'campaign_keys',selected=g[key],proposals=groupCandidates(d,g),needle=qualityFold(s.search);
  const dbGroup=groupWorkspaceDbGroup();
  const derivedCampaigns=new Map((dbGroup?.derived_campaigns||[]).map(c=>[String(c.key),c]));
  const choices=(isAgent?d.agents:isLine?d.lines:d.campaigns).map(x=>{
    const id=String(isAgent?x.key:isLine?x.id:x.key),derived=!isAgent&&!isLine?derivedCampaigns.get(id):null;
    return {id,name:x.name,secondary:isAgent?`${x.login||x.key}${x.group_name?' \u00b7 '+x.group_name:''}`:isLine?'File '+x.id:x.campaign_id||'Sans ID',blocked:isAgent&&!!x.group_id&&x.group_id!==g.id,imported:x.imported,automatic:!!derived,via_line_ids:derived?.via_line_ids||[]};
  });
  // A campaign observed on a file of the group must remain visible even when
  // the catalogue row is temporarily missing. It is an automatic relation,
  // never silently saved as a manual campaign assignment.
  if(!isAgent&&!isLine){for(const c of derivedCampaigns.values())if(!choices.some(x=>x.id===String(c.key)))choices.push({id:String(c.key),name:c.name||c.campaign_id||c.key,secondary:c.campaign_id||c.key,blocked:false,imported:true,automatic:true,via_line_ids:c.via_line_ids||[]});}
  const visible=choices.filter(x=>(s.scope!=='selected'||selected.has(x.id)||x.automatic)&&(s.scope!=='suggested'||proposals.has(x.id))&&(!needle||qualityFold(x.name+' '+x.id+' '+x.secondary+' '+(x.via_line_ids||[]).join(' ')).includes(needle))).sort((a,b)=>Number((selected.has(b.id)||b.automatic))-Number((selected.has(a.id)||a.automatic))||a.name.localeCompare(b.name,'fr'));
  const eligible=visible.filter(x=>!x.blocked&&!x.automatic),writable=canWrite('classification');
  const autoCampaignCount=!isAgent&&!isLine?visible.filter(x=>x.automatic).length:0;
  $('#gw-candidates-note').innerHTML=isAgent?`Membres manuels uniquement. Les agents des files enregistr\u00e9es sont d\u00e9j\u00e0 automatiques, visibles dans \u00ab Depuis les bases \u00bb.`:isLine?'S\u00e9lectionne les files du groupe.':`${autoCampaignCount} campagne(s) automatique(s) d\u00e9duite(s) des files du groupe. Les campagnes automatiques sont en lecture seule et ne sont pas enregistr\u00e9es comme liens manuels.`;
  host.innerHTML=`<div class="gw-selection-head"><span id="gw-selection-count">${visible.length} r\u00e9sultat(s) \u00b7 ${selected.size} manuel(s)${autoCampaignCount?' \u00b7 '+autoCampaignCount+' auto':''}</span>${writable?'<button id="gw-select-visible" type="button" class="button ghost small">Cocher les r\u00e9sultats</button>':''}</div>${visible.map(x=>`<label class="gw-member ${x.blocked?'blocked':''} ${x.automatic?'automatic':''}"><input type="checkbox" data-gw-item="${esc(x.id)}" ${(selected.has(x.id)||x.automatic)?'checked':''} ${!writable||x.blocked||x.automatic?'disabled':''}><span><strong>${esc(x.name)}</strong><small>${esc(x.secondary)}${!x.imported?' \u00b7 Conserv\u00e9 hors import':''}</small>${x.automatic?`<small>Automatique via file(s) ${esc((x.via_line_ids||[]).join(', ')||'du groupe')}</small>`:''}${s.scope==='suggested'&&proposals.has(x.id)?`<small>Proposition : ${esc(proposals.get(x.id).reason.slice(0,3).join(', '))}</small>`:''}</span>${x.automatic?'<small>Auto</small>':x.blocked?'<small>Autre groupe</small>':''}</label>`).join('')||'<p class="gw-hint">Aucun r\u00e9sultat.</p>'}`;
  host.querySelectorAll('[data-gw-item]').forEach(c=>c.onchange=()=>{c.checked?selected.add(c.dataset.gwItem):selected.delete(c.dataset.gwItem);groupWorkspaceSetDirty();const tab=document.querySelector(`[data-gw-tab="${s.tab}"] span`);if(tab)tab.textContent=selected.size;const count=$('#gw-selection-count');if(count)count.textContent=`${visible.length} r\u00e9sultat(s) \u00b7 ${selected.size} s\u00e9lectionn\u00e9(s)`;});
  $('#gw-select-visible')?.addEventListener('click',()=>{if(!eligible.length)return;eligible.forEach(x=>selected.add(x.id));groupWorkspaceSetDirty();groupWorkspaceRender();});
}
async function groupWorkspaceSave(){
  const s=groupWorkspaceState,g=s.draft;if(!g.name.trim()){groupWorkspaceMessage('Indique le nom du groupe.','error');return;}
  const old=s.data.groups.find(x=>x.id===g.id),diff=(a,b)=>[...a].filter(x=>!b.has(x)).length;
  const before=new Set(old?.agent_ids||[]),added=diff(g.agent_ids,before),removed=diff(before,g.agent_ids);
  if(!confirm(`Enregistrer ${g.name} ?\n${g.agent_ids.size} agents (${added} ajout(s), ${removed} retrait(s))\n${g.line_ids.size} files et ${g.campaign_keys.size} campagnes\nLes autres groupes restent inchang\u00e9s.`))return;
  const payload={...g,revision:s.data.revision,agent_ids:[...g.agent_ids],line_ids:[...g.line_ids],campaign_keys:[...g.campaign_keys]};$('#gw-save').disabled=true;
  try{const r=await api('/api/groups/workspace/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});s.dirty=false;s.filter='';await groupWorkspaceLoad(r.id);groupWorkspaceMessage('Groupe enregistr\u00e9. Les filtres Qualit\u00e9 utiliseront ces affectations au prochain chargement.');}
  catch(e){groupWorkspaceMessage(e.message,'error');if($('#gw-save'))$('#gw-save').disabled=false;}
}
window.addEventListener('beforeunload',e=>{if(groupWorkspaceState.dirty){e.preventDefault();e.returnValue='';}});


// Database scope is deliberately read-only. Switching to edit keeps the
// registered member sets; calculated links are never implicitly checked/saved.
function groupWorkspaceDbGroup(){return groupWorkspaceState.data?.groups.find(g=>g.id===groupWorkspaceState.draft?.id);}
function groupWorkspaceDbCount(tab){
  const g=groupWorkspaceDbGroup();if(!g)return 0;
  return tab==='agents'?(g.scope_agent_count??g.agent_ids.length):tab==='lines'?(g.scope_line_count??g.line_ids.length):(g.scope_campaign_count??g.campaigns.length);
}
function groupWorkspaceDatabaseMembers(){
  const s=groupWorkspaceState,g=groupWorkspaceDbGroup(),d=s.data,host=$('#gw-members');if(!host||!g)return;
  const needle=qualityFold(s.search),items=new Map();
  const normalize=k=>String(k).replace(/^s(?=\d+$)/i,'');
  function add(key,name,secondary,linked,reason,automatic=false){items.set(String(key),{key:String(key),name,secondary,linked,reason,automatic});}
  if(s.tab==='agents'){
    for(const key of g.agent_ids){const a=d.agents.find(a=>a.key===key)||{};add(key,a.name||key,a.login||key,false,'Appartenance enregistr\u00e9e');}
    for(const link of g.linked_agents||[]){const a=d.agents.find(a=>normalize(a.agent_id)===link.agent_id)||{};add(a.key||link.agent_id,a.name||link.name||link.agent_id,a.login||link.agent_id,true,[link.via_line_ids.length?'Files '+link.via_line_ids.join(', '):'',link.via_campaign_keys.length?link.via_campaign_keys.length+' campagne(s) configur\u00e9e(s)':''].filter(Boolean).join(' \u00b7 '));}
    for(const link of g.automatic_agents||[]){const a=d.agents.find(a=>normalize(a.agent_id)===link.agent_id)||{},key=a.key||link.agent_id,old=items.get(String(key));add(key,a.name||link.name||key,a.login||key,old?old.linked:true,'Files du groupe : '+link.via_line_ids.join(', '),true);}
  }else if(s.tab==='lines'){
    for(const id of g.line_ids){const q=d.lines.find(q=>q.id===id)||{};add(id,q.name||'File '+id,'File '+id,false,'Rattachement enregistr\u00e9');}
    for(const link of g.linked_lines||[]){const q=d.lines.find(q=>q.id===link.line_id)||{};add(link.line_id,q.name||'File '+link.line_id,'File '+link.line_id,true,'Affect\u00e9e aux agents '+link.via_agent_ids.join(', '));}
  }else{
    for(const c of g.campaigns)add(c.key,c.name,c.key,false,'Rattachement enregistr\u00e9');
    for(const c of g.derived_campaigns||[]){const old=items.get(String(c.key));add(c.key,c.name||c.campaign_id,c.campaign_id||c.key,old?old.linked:true,'Campagne des files du groupe'+(c.via_line_ids?.length?' : '+c.via_line_ids.join(', '):''),true);}
    for(const c of g.linked_campaigns||[])if(!items.has(String(c.key)))add(c.key,c.name,c.key,true,'Affect\u00e9e aux agents '+c.via_agent_ids.join(', '));
  }
  const visible=[...items.values()].filter(x=>!needle||qualityFold([x.name,x.secondary,x.reason].join(' ')).includes(needle)).sort((a,b)=>a.name.localeCompare(b.name,'fr',{numeric:true}));
  const linked=[...items.values()].filter(x=>x.linked&&!x.automatic).length,explicit=[...items.values()].filter(x=>!x.linked).length,automatic=[...items.values()].filter(x=>x.automatic).length;
  $('#gw-candidates-note').textContent=s.tab==='agents'?`${explicit} manuel(s) \u00b7 ${automatic} automatique(s)${linked?' \u00b7 '+linked+' lien(s) campagne':''}. Recalcul\u00e9s depuis les files du groupe \u00b7 ${qualityDate(d.source_day)}.`:s.tab==='campaigns'?`${automatic} campagne(s) d\u00e9duite(s) des files \u00b7 ${explicit} enregistr\u00e9e(s).`:`${explicit} enregistr\u00e9(s) \u00b7 ${linked} li\u00e9(s). Les files li\u00e9es ne classent pas d'autres agents avant validation.`;
  host.innerHTML=`<div class="gw-selection-head"><span>${visible.length} r\u00e9sultat(s)</span><div>${canWrite('classification')&&s.tab==='lines'&&g.linked_lines?.length?'<button id="gw-validate-lines" class="button ghost small">Valider les files li\u00e9es</button>':''}${canWrite('classification')?'<button id="gw-edit-members" class="button ghost small">Modifier</button>':''}</div></div>`+
    (visible.map(x=>`<div class="gw-member gw-db-member"><span><strong>${esc(x.name)}</strong><small>${esc(x.secondary)}</small><small>${esc(x.reason)}</small></span><span class="gw-origin ${x.linked?'linked':''}">${x.automatic?(x.linked?'Automatique':'Manuel + auto'):(x.linked?'Li\u00e9':'Manuel')}</span></div>`).join('')||`<p class="gw-db-empty">${needle?'Aucun r\u00e9sultat pour cette recherche.':(s.tab==='agents'?'Enregistre les files de ce groupe : leurs agents seront ajout\u00e9s automatiquement.':s.tab==='lines'?'Aucune file class\u00e9e. Clique Modifier pour choisir les files du groupe.':'Aucune campagne enregistr\u00e9e pour ce groupe.')}</p>`);
  $('#gw-validate-lines')?.addEventListener('click',()=>{if(!confirm('Ces files viennent des affectations des membres manuels. Confirmer leur rattachement \u00e0 '+g.name+' ? Apr\u00e8s enregistrement, tous leurs agents seront class\u00e9s automatiquement.'))return;for(const q of g.linked_lines||[])s.draft.line_ids.add(String(q.line_id));s.scope='selected';groupWorkspaceSetDirty();groupWorkspaceRender();groupWorkspaceMessage('V\u00e9rifie la s\u00e9lection puis Enregistrer le groupe.');});
  $('#gw-edit-members')?.addEventListener('click',()=>{s.scope='all';groupWorkspaceRender();});
}


// F4.2: refresh open analysis screens after imports in another tab.
// Draft edits, focus and selections are preserved; there is no periodic write.
let groupAutoRefreshTimer=null,groupAutoRefreshBusy=false;
function groupDataSignature(d){return [d?.automatic_rule?.signature||'',JSON.stringify(d?.scope_sources||{}),d?.updated_at||'',d?.last_import_attempt?.attempted_at||''].join('|');}
function installGroupAutoRefresh(){
  if(groupAutoRefreshTimer||typeof window.setInterval!=='function')return;
  groupAutoRefreshTimer=window.setInterval(refreshAutomaticGroups,30000);
}
async function refreshAutomaticGroups(){
  if(groupAutoRefreshBusy||typeof document==='undefined'||document.hidden)return;
  const onGroups=!!document.getElementById('group-workspace'),onQuality=!!document.getElementById('quality-results');
  if(!onGroups&&!onQuality)return;
  if(onGroups&&(groupWorkspaceState.dirty||groupWorkspaceState.scope!=='database'))return;
  if(onQuality&&document.getElementById('q-import')?.disabled)return;
  groupAutoRefreshBusy=true;
  const generation=onGroups?groupWorkspaceState.generation:qualityGeneration;
  const current=onGroups?groupWorkspaceState.data:qualityState.data;
  try{
    const status=await api('/api/groups/status');
    if(status?.refresh_token&&status.refresh_token===current?.refresh_token)return;
    const incoming=await api(onGroups?'/api/groups/workspace':'/api/quality/priorities');
    if(onGroups){
      const s=groupWorkspaceState;
      if(!document.getElementById('group-workspace')||s.generation!==generation||s.dirty||s.scope!=='database')return;
      if(incoming.revision!==current?.revision||groupDataSignature(incoming)!==groupDataSignature(current)){
        s.data=incoming;const selected=incoming.groups.find(g=>g.id===s.draft?.id);
        s.draft=groupDraft(selected||incoming.groups[0]);groupWorkspaceRender();
      }
    }else{
      if(!document.getElementById('quality-results')||qualityGeneration!==generation)return;
      if(groupDataSignature(incoming)!==groupDataSignature(current)){
        const s=qualityState;s.data=incoming;
        const opt=(v,t)=>`<option value="${esc(v)}">${esc(t)}</option>`;
        const sets=[['quality-group','group',opt('','Tous les groupes')+opt('none','Sans lien de groupe')+(incoming.groups||[]).map(g=>opt(g.id,qualityGroupOption(g))).join('')],
          ['quality-line','line',opt('','Toutes les files')+(incoming.queues||[]).map(q=>opt(q.line_id,q.line_id+' - '+q.display_name)).join('')],
          ['quality-agent','agent',opt('','Tous les agents')+(incoming.agents||[]).map(a=>opt(a.agent_id,qualityAgentName(a)+' - '+a.login)).join('')],
          ['quality-campaign','campaign',opt('','Toutes les campagnes')+(incoming.campaigns||[]).map(c=>opt(qualityCampaignKey(c),qualityCampaignName(c))).join('')]];
        for(const [id,key,html] of sets){const el=document.getElementById(id);if(!el)continue;el.innerHTML=html;el.value=s[key];if(el.selectedIndex<0){el.value='';s[key]='';}}
        const info=document.getElementById('quality-source-info');
        if(info)info.innerHTML='<span>'+esc(incoming.automatic_rule?.automatic_agent_count||0)+' agents class\u00e9s automatiquement</span><span>Configuration agents : <b>'+esc(qualitySourceDay('agent_queues'))+'</b> \u00b7 Observations : '+esc(qualitySourceDay('observations'))+'</span>';
        qualityRender();
      }
    }
  }catch(e){
    // Keep last valid data and a visible warning instead of clearing the table.
    const notice=document.getElementById(onGroups?'gw-message':'q-notice');
    if(notice)notice.textContent='Actualisation automatique indisponible. Les derni\u00e8res donn\u00e9es restent affich\u00e9es.';
  }finally{groupAutoRefreshBusy=false;}
}
window.addEventListener('focus',refreshAutomaticGroups);
