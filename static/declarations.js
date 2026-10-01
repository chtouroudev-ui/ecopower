/* v50 UI refresh - simple, compact declarations for responsables */
let declarationCache=null,declarationEdit=null;

function declTypeLabel(type){return (declarationCache?.types||{})[type]||type||'Autre';}
function declTargetLabel(d){
  const targets=d.targets||[],groups=new Map((declarationCache?.groups||[]).map(g=>[String(g.id),g.name]));
  const directory=new Map((declarationCache?.directory||[]).map(a=>[String(a.user_key),`${[a.first_name,a.last_name].filter(Boolean).join(' ')||a.user_identifier||a.user_key} (${a.user_identifier||a.user_key})`]));
  return targets.map(t=>t.target_type==='GROUP'?`Groupe ${groups.get(String(t.target_key))||t.target_key}`:(directory.get(String(t.target_key))||`Agent ${t.target_key}`)).join(', ');
}
function declGroupKeys(d){const directory=new Map((declarationCache?.directory||[]).map(a=>[String(a.user_key),String(a.group_id||'')]));const keys=new Set();for(const t of d.targets||[]){if(t.target_type==='GROUP')keys.add(String(t.target_key));if(t.target_type==='AGENT'){const g=directory.get(String(t.target_key));if(g)keys.add(g);}}return [...keys];}
function declAgentKeys(d){const rows=declarationCache?.directory||[],keys=new Set();for(const t of d.targets||[]){if(t.target_type==='AGENT')keys.add(String(t.target_key));if(t.target_type==='GROUP')rows.filter(a=>String(a.group_id||'')===String(t.target_key)).forEach(a=>keys.add(String(a.user_key)));}return [...keys];}
function declAuthorOptions(){const authors=[...new Set((declarationCache?.declarations||[]).map(d=>String(d.created_by||'').trim()).filter(Boolean))].sort((a,b)=>a.localeCompare(b));return authors.map(a=>`<option value="${esc(a)}">${esc(a)}</option>`).join('');}
function declDurationMinutes(d){const a=new Date(String(d.start_at||'').replace(' ','T')),b=new Date(String(d.end_at||'').replace(' ','T'));const n=Math.round((b-a)/60000);return Number.isFinite(n)&&n>0?n:Number(d.duration_minutes||30);}
function declDurationText(d){const mins=Math.max(0,declDurationMinutes(d));if(mins<60)return `${mins} min`;const h=Math.floor(mins/60),m=mins%60;return `${h} h${m?` ${m} min`:''}`;}
function declEffectText(type){
  const a=(declarationCache?.default_actions||{})[type]||{},bits=[];
  if(type==='PROBLEME_TECHNIQUE'){bits.push('visible comme incident technique');}else{bits.push('filtre automatiquement partout');}
  if(a.exclude_lost_time)bits.push('hors temps perdu');
  if(a.exclude_score)bits.push('hors score Support');
  if(a.mark_authorized)bits.push('autorise');
  return bits.join(' - ');
}
function declStatusBadge(d){return d.status==='ACTIVE'?'<span class="fresh-badge fresh-green">Active</span>':'<span class="fresh-badge fresh-gray">Annulee</span>';}
function declAgentItems(selected=[]){
  const set=new Set((selected||[]).map(String));
  return (declarationCache?.directory||[]).map(a=>{const key=String(a.user_key),name=[a.first_name,a.last_name].filter(Boolean).join(' ')||a.user_identifier||key;return {key,label:`${name} - ${a.user_identifier||key}${a.group_name?` - ${a.group_name}`:''}`,checked:set.has(key)};});
}
function declGroupItems(selected=[]){const set=new Set((selected||[]).map(String));return (declarationCache?.groups||[]).map(g=>({key:String(g.id),label:g.name,checked:set.has(String(g.id))}));}
function declPickerHtml(kind,selected=[]){
  const isAgent=kind==='agent',items=isAgent?declAgentItems(selected):declGroupItems(selected),field=isAgent?'agent_key':'group_key',id=`declaration-${kind}-picker`,title=isAgent?'Choisir un ou plusieurs agents':'Choisir un ou plusieurs groupes';
  return `<details class="entity-picker" id="${id}"><summary><span class="entity-picker-title">${title}</span><span class="entity-picker-count">${items.filter(x=>x.checked).length?items.filter(x=>x.checked).length+' selectionne(s)':'Aucune selection'}</span></summary><div class="entity-picker-body"><input class="entity-picker-search" type="search" placeholder="Rechercher..." autocomplete="off"><div class="entity-picker-list">${items.map(x=>`<label data-search="${esc(String(x.label).toLowerCase())}"><input type="checkbox" name="${field}" value="${esc(x.key)}" ${x.checked?'checked':''}><span>${esc(x.label)}</span></label>`).join('')||'<div class="empty compact">Aucun element disponible.</div>'}</div></div></details>`;
}
function declFormHtml(){
  if(!canWrite('declarations'))return `<section class="card panel"><div class="readonly-box"><strong>Declarations en lecture seule</strong><span>Vous pouvez consulter les declarations, mais pas les modifier.</span></div></section>`;
  const d=declarationEdit||{},targets=d.targets||[],targetType=targets[0]?.target_type||'AGENT',selected=targets.map(t=>String(t.target_key));
  const start=(d.start_at||'').slice(11,16)||'09:00',end=(d.end_at||'').slice(11,16)||'',date=(d.start_at||'').slice(0,10)||declarationCache.today,minutes=declDurationMinutes(d);
  const types=Object.entries(declarationCache.types||{}).map(([k,v])=>`<option value="${esc(k)}" ${k===(d.declaration_type||'AUTORISATION')?'selected':''}>${esc(v)}</option>`).join('');
  return `<section class="card panel declaration-create-card declaration-compact"><div class="panel-head compact-head"><div><span class="eyebrow">SAISIE RAPIDE</span><h2>${d.id?'Modifier la declaration':'Nouvelle declaration'}</h2><p>Qui, pourquoi et combien de temps. La période est automatiquement retirée de Support, Diagnostic, Détails, Analyse et Rapports.</p></div>${d.id?'<button class="button ghost small" type="button" id="declaration-cancel-edit">Annuler</button>':''}</div>
  <form id="declaration-form" class="declaration-form declaration-form-compact">
    <input type="hidden" name="id" value="${esc(d.id||'')}"><input type="hidden" name="time_mode" id="declaration-time-mode" value="duration">
    <div class="declaration-quick-grid">
      <label>Cible<select name="target_type" id="declaration-target-type"><option value="AGENT" ${targetType==='AGENT'?'selected':''}>Agent</option><option value="GROUP" ${targetType==='GROUP'?'selected':''}>Groupe</option></select></label>
      <label>Type<select name="declaration_type" id="declaration-type">${types}</select></label>
      <label>Date<input type="date" name="date" required value="${esc(date)}"></label>
      <label>Debut<input type="time" name="start_time" required value="${esc(start)}"></label>
    </div>
    <div id="declaration-agent-wrap">${declPickerHtml('agent',targetType==='AGENT'?selected:[])}</div>
    <div id="declaration-group-wrap">${declPickerHtml('group',targetType==='GROUP'?selected:[])}</div>
    <div class="declaration-duration-line"><span class="field-caption">Duree</span><div class="duration-presets">${[15,30,45,60].map(m=>`<button type="button" class="duration-chip ${minutes===m?'active':''}" data-minutes="${m}">${m} min</button>`).join('')}<label class="duration-custom"><span>Autre</span><input type="number" min="1" max="1440" step="1" name="duration_minutes" value="${minutes}"></label><button type="button" class="link-button" id="declaration-end-toggle">Heure de fin</button></div><label id="declaration-end-wrap" class="declaration-end-compact">Fin<input type="time" name="end_time" value="${esc(end)}"></label></div>
    <div class="declaration-effect compact-effect" id="declaration-effect"></div>
    <label class="declaration-comment-field">Commentaire <span>optionnel</span><input name="comment" maxlength="500" placeholder="Ex. rendez-vous, reunion, intervention reseau..." value="${esc(d.comment||'')}"></label>
    <div class="declaration-preview" id="declaration-preview"></div>
    <div class="form-actions compact-actions"><button class="button" type="submit">${d.id?'Enregistrer':'Declarer'}</button><span class="form-result" id="declaration-result"></span></div>
  </form></section>`;
}
function declTodayHtml(){
  const rows=(declarationCache.declarations||[]).filter(d=>String(d.start_at||'').slice(0,10)===declarationCache.today&&!d.deleted_at);
  return `<section class="card panel"><div class="panel-head compact-head"><div><h2>Aujourd'hui</h2><p>Declarations enregistrees pour ${esc(declarationCache.today)}.</p></div><span>${rows.length}</span></div><div class="declaration-today-grid compact-cards">${rows.map(declCardHtml).join('')||'<div class="empty">Aucune declaration aujourd\'hui.</div>'}</div></section>`;
}
function declCardHtml(d){
  const active=d.status==='ACTIVE';
  return `<article class="declaration-card declaration-card-compact ${active?'':'off'}"><div class="declaration-card-main"><div><div class="inline-badges">${declStatusBadge(d)}<span class="mini-tag">${esc(declTypeLabel(d.declaration_type))}</span></div><h3>${esc(declTargetLabel(d))}</h3><p><strong>${esc(String(d.start_at||'').slice(11,16))} - ${esc(String(d.end_at||'').slice(11,16))}</strong> <span>${esc(declDurationText(d))}</span>${d.comment?` - ${esc(d.comment)}`:''}</p></div><div class="declaration-card-actions">${canWrite('declarations')&&active?`<button class="button ghost small declaration-edit" data-id="${d.id}">Modifier</button><button class="button ghost small declaration-cancel" data-id="${d.id}">Annuler</button>`:''}</div></div><details class="mini-details"><summary>Effet applique</summary><span>${esc(declEffectText(d.declaration_type))}</span><small>Declare par ${esc(d.created_by||'-')}</small></details></article>`;
}
function declHistoryHtml(){
  const rows=(declarationCache.declarations||[]).filter(d=>!d.deleted_at),typeOpts=Object.entries(declarationCache.types||{}).map(([k,v])=>`<option value="${esc(k)}">${esc(v)}</option>`).join(''),groupOpts=(declarationCache.groups||[]).map(g=>`<option value="${g.id}">${esc(g.name)}</option>`).join(''),agentOpts=(declarationCache.directory||[]).map(a=>{const name=[a.first_name,a.last_name].filter(Boolean).join(' ')||a.user_identifier||a.user_key;return `<option value="${esc(String(a.user_key))}">${esc(name)} - ${esc(a.user_identifier||a.user_key)}</option>`;}).join('');
  return `<section class="card panel"><div class="panel-head compact-head"><div><h2>Historique</h2><p>Recherche rapide, avec filtres avances si necessaire.</p></div><span>${rows.length}</span></div>
  <div class="declaration-history-toolbar"><input id="decl-filter-text" type="search" placeholder="Rechercher cible, commentaire, auteur..."><select id="decl-filter-status"><option value="">Tous les statuts</option><option value="ACTIVE">Actives</option><option value="CANCELLED">Annulees</option></select><button type="button" class="button ghost small" id="decl-filter-reset">Effacer</button></div>
  <details class="compact-advanced declaration-history-advanced"><summary>Filtres avances</summary><div class="declaration-history-filters declaration-history-filters-rich"><label>Du<input type="date" id="decl-filter-from"></label><label>Au<input type="date" id="decl-filter-to"></label><label>Groupe<select id="decl-filter-group"><option value="">Tous</option>${groupOpts}</select></label><label>Agent<select id="decl-filter-agent"><option value="">Tous</option>${agentOpts}</select></label><label>Type<select id="decl-filter-type"><option value="">Tous</option>${typeOpts}</select></label><label>Auteur<select id="decl-filter-author"><option value="">Tous</option>${declAuthorOptions()}</select></label></div></details>
  <div class="table-wrap"><table id="declaration-history-table" class="compact-table"><thead><tr><th>Date</th><th>Cible</th><th>Type</th><th>Periode</th><th>Auteur</th><th>Statut</th><th></th></tr></thead><tbody>${rows.map(d=>`<tr data-decl-date="${esc(String(d.start_at||'').slice(0,10))}" data-decl-type="${esc(d.declaration_type)}" data-decl-status="${esc(d.status)}" data-decl-author="${esc(String(d.created_by||''))}" data-decl-groups="${esc(declGroupKeys(d).join(','))}" data-decl-agents="${esc(declAgentKeys(d).join(','))}" data-decl-search="${esc((declTargetLabel(d)+' '+declTypeLabel(d.declaration_type)+' '+(d.comment||'')+' '+(d.created_by||'')).toLowerCase())}"><td>${esc(String(d.start_at||'').slice(0,10))}</td><td><strong>${esc(declTargetLabel(d))}</strong></td><td>${esc(declTypeLabel(d.declaration_type))}${d.comment?`<small class="sub">${esc(d.comment)}</small>`:''}</td><td><strong>${esc(String(d.start_at||'').slice(11,16))} - ${esc(String(d.end_at||'').slice(11,16))}</strong><small class="sub">${esc(declDurationText(d))}</small></td><td>${esc(d.created_by||'-')}</td><td>${declStatusBadge(d)}</td><td>${canWrite('declarations')?`<div class="row-actions">${d.status==='ACTIVE'?`<button class="button ghost small declaration-edit" data-id="${d.id}">Modifier</button>`:''}<button class="icon-btn declaration-delete" title="Supprimer" data-id="${d.id}">x</button></div>`:''}</td></tr>`).join('')||'<tr><td colspan="7" class="empty">Aucune declaration.</td></tr>'}</tbody></table></div></section>`;
}
function declAuditHtml(){const rows=declarationCache.audit||[];return `<details class="card panel compact-advanced"><summary>Journal d'audit - ${rows.length} evenement(s)</summary><div class="table-wrap"><table><thead><tr><th>Date</th><th>Declaration</th><th>Action</th><th>Auteur</th></tr></thead><tbody>${rows.map(r=>`<tr><td>${esc(fmt(r.created_at))}</td><td>#${Number(r.declaration_id||0)}</td><td>${esc(r.action)}</td><td>${esc(r.actor||'-')}</td></tr>`).join('')||'<tr><td colspan="4">Aucun audit.</td></tr>'}</tbody></table></div></details>`;}

async function declarationsView(){
  const viewTicket=captureViewTicket();
  if(!canRead('declarations')){redirectAllowed();return;}
  activate('declarations');setHead('Declarations','Saisie rapide des autorisations, interventions et periodes ponctuelles.');app.innerHTML='<div class="loading">Chargement des declarations...</div>';
  try{const response=await api('/api/declarations');if(!viewTicketIsCurrent(viewTicket))return;declarationCache=response;app.innerHTML=declFormHtml()+declTodayHtml()+declHistoryHtml()+declAuditHtml();bindDeclarationUi();}
  catch(e){if(viewTicketIsCurrent(viewTicket))app.innerHTML=flash(e.message,'error');}
}
function bindEntityPicker(rootId){
  const root=document.querySelector(rootId);if(!root)return;
  const search=root.querySelector('.entity-picker-search'),items=[...root.querySelectorAll('.entity-picker-list label[data-search]')],count=root.querySelector('.entity-picker-count');
  const refresh=()=>{const n=items.filter(x=>x.querySelector('input')?.checked).length;count.textContent=n?`${n} selectionne(s)`:'Aucune selection';};
  if(search)search.oninput=()=>{const q=search.value.trim().toLowerCase();items.forEach(x=>x.hidden=!!q&&!x.dataset.search.includes(q));};
  items.forEach(x=>x.querySelector('input')?.addEventListener('change',refresh));refresh();
}
function bindDeclarationUi(){
  const form=document.querySelector('#declaration-form');
  if(form){
    const targetType=document.querySelector('#declaration-target-type'),agentWrap=document.querySelector('#declaration-agent-wrap'),groupWrap=document.querySelector('#declaration-group-wrap');
    const syncTarget=()=>{agentWrap.hidden=targetType.value!=='AGENT';groupWrap.hidden=targetType.value!=='GROUP';};targetType.onchange=syncTarget;syncTarget();bindEntityPicker('#declaration-agent-picker');bindEntityPicker('#declaration-group-picker');
    const type=document.querySelector('#declaration-type'),effect=document.querySelector('#declaration-effect');
    const syncEffect=()=>{effect.innerHTML=`<strong>Effet automatique</strong><span>${esc(declEffectText(type.value))}</span>`;};type.onchange=syncEffect;syncEffect();
    const mode=document.querySelector('#declaration-time-mode'),duration=form.querySelector('[name="duration_minutes"]'),endWrap=document.querySelector('#declaration-end-wrap'),endInput=form.querySelector('[name="end_time"]'),toggle=document.querySelector('#declaration-end-toggle'),preview=document.querySelector('#declaration-preview');
    const setMode=v=>{mode.value=v;const isDuration=v==='duration';endWrap.hidden=isDuration;toggle.textContent=isDuration?'Heure de fin':'Utiliser une duree';document.querySelectorAll('.duration-chip,.duration-custom').forEach(x=>x.classList.toggle('muted-mode',!isDuration));updatePreview();};
    const updatePreview=()=>{const fd=new FormData(form),date=fd.get('date'),start=fd.get('start_time');if(!date||!start){preview.textContent='';return;}if(mode.value==='duration'){const mins=Number(fd.get('duration_minutes')||0);if(mins>0){const dt=new Date(`${date}T${start}:00`);dt.setMinutes(dt.getMinutes()+mins);preview.textContent=`${start} -> ${String(dt.getHours()).padStart(2,'0')}:${String(dt.getMinutes()).padStart(2,'0')} (${mins} min)`;}}else{preview.textContent=endInput.value?`${start} -> ${endInput.value}`:'';}};
    toggle.onclick=()=>setMode(mode.value==='duration'?'end':'duration');
    document.querySelectorAll('.duration-chip').forEach(b=>b.onclick=()=>{duration.value=b.dataset.minutes;document.querySelectorAll('.duration-chip').forEach(x=>x.classList.toggle('active',x===b));setMode('duration');});
    duration.addEventListener('input',()=>{document.querySelectorAll('.duration-chip').forEach(x=>x.classList.toggle('active',String(x.dataset.minutes)===String(duration.value)));updatePreview();});
    form.querySelectorAll('input,select').forEach(el=>el.addEventListener('change',updatePreview));form.querySelectorAll('input').forEach(el=>el.addEventListener('input',updatePreview));setMode('duration');
    const cancelEdit=document.querySelector('#declaration-cancel-edit');if(cancelEdit)cancelEdit.onclick=()=>{declarationEdit=null;declarationsView();};
    form.onsubmit=async e=>{e.preventDefault();const fd=new FormData(form),target=fd.get('target_type'),keys=target==='AGENT'?fd.getAll('agent_key'):fd.getAll('group_key'),body={id:fd.get('id')||undefined,declaration_type:fd.get('declaration_type'),targets:keys.filter(Boolean).map(k=>({target_type:target,target_key:k})),date:fd.get('date'),start_time:fd.get('start_time'),comment:fd.get('comment')};if(!body.targets.length){document.querySelector('#declaration-result').textContent='Selectionnez au moins une cible.';return;}if(fd.get('time_mode')==='duration')body.duration_minutes=fd.get('duration_minutes');else body.end_time=fd.get('end_time');const out=document.querySelector('#declaration-result');try{await api('/api/declarations/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});declarationEdit=null;out.textContent='Declaration enregistree.';setTimeout(declarationsView,200);}catch(err){out.textContent=err.message;}};
  }
  document.querySelectorAll('.declaration-edit').forEach(b=>b.onclick=()=>{declarationEdit=(declarationCache.declarations||[]).find(d=>String(d.id)===String(b.dataset.id))||null;declarationsView();});
  document.querySelectorAll('.declaration-cancel').forEach(b=>b.onclick=async()=>{if(!confirm('Annuler cette declaration ? Elle restera dans l historique.'))return;try{await api('/api/declarations/cancel',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:Number(b.dataset.id)})});declarationsView();}catch(e){alert(e.message);}});
  document.querySelectorAll('.declaration-delete').forEach(b=>b.onclick=async()=>{if(!confirm('Supprimer logiquement cette declaration ? L audit restera conserve.'))return;try{await api('/api/declarations/delete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:Number(b.dataset.id)})});declarationsView();}catch(e){alert(e.message);}});
  const text=document.querySelector('#decl-filter-text'),type=document.querySelector('#decl-filter-type'),status=document.querySelector('#decl-filter-status'),from=document.querySelector('#decl-filter-from'),to=document.querySelector('#decl-filter-to'),group=document.querySelector('#decl-filter-group'),agent=document.querySelector('#decl-filter-agent'),author=document.querySelector('#decl-filter-author');
  const filter=()=>{const q=(text?.value||'').trim().toLowerCase(),t=type?.value||'',st=status?.value||'',df=from?.value||'',dt=to?.value||'',g=group?.value||'',a=agent?.value||'',au=author?.value||'';document.querySelectorAll('#declaration-history-table tbody tr[data-decl-type]').forEach(tr=>{const groups=(tr.dataset.declGroups||'').split(',').filter(Boolean),agents=(tr.dataset.declAgents||'').split(',').filter(Boolean),day=tr.dataset.declDate||'',ok=(!q||tr.dataset.declSearch.includes(q))&&(!t||tr.dataset.declType===t)&&(!st||tr.dataset.declStatus===st)&&(!df||day>=df)&&(!dt||day<=dt)&&(!g||groups.includes(g))&&(!a||agents.includes(a))&&(!au||tr.dataset.declAuthor===au);tr.hidden=!ok;});};
  [text,type,status,from,to,group,agent,author].filter(Boolean).forEach(el=>el.addEventListener(el.tagName==='INPUT'?'input':'change',filter));const reset=document.querySelector('#decl-filter-reset');if(reset)reset.onclick=()=>{[text,type,status,from,to,group,agent,author].filter(Boolean).forEach(el=>el.value='');filter();};
}
