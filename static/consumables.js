async function consumablesView(){
  const viewTicket=captureViewTicket();
  if(!canRead('consumables')){redirectAllowed();return;}
  activate('consumables');setHead('Consommables','Stock par état, entrées/sorties, bénéficiaires et traçabilité complète.');
  const today=()=>{const d=new Date(),x=new Date(d.getTime()-d.getTimezoneOffset()*60000);return x.toISOString().slice(0,10);};
  const monthStart=()=>today().slice(0,8)+'01';
  const editable=canWrite('consumables');
  let data=await api('/api/consumables');
  const conditionLabel=v=>({NEUF:'Neuf',ANCIEN:'Ancien',KO:'KO'}[v]||v);
  const movementLabel=v=>v==='ENTREE'?'<span class="movement-in">Entrée</span>':'<span class="movement-out">Sortie</span>';
  const itemOptions=()=>data.items.filter(x=>x.active).map(x=>`<option value="${x.id}">${esc(x.name)} · ${Number(x.qty_total||0)} ${esc(x.unit||'u.')}</option>`).join('');
  const directoryOptions=()=>data.directory.map(u=>`<option value="${esc(u.user_identifier)}">${esc(u.display_name)}${u.group_name?` · ${esc(u.group_name)}`:''}</option>`).join('');
  const stockChips=x=>`<div class="consumable-stock-cells"><span class="stock-chip new">Neuf ${Number(x.qty_new||0)}</span><span class="stock-chip old">Ancien ${Number(x.qty_old||0)}</span><span class="stock-chip ko">KO ${Number(x.qty_ko||0)}</span></div>`;
  if(!viewTicketIsCurrent(viewTicket))return;
  app.innerHTML=`
    <div class="consumable-summary">
      <div class="card"><span>Références actives</span><strong id="cons-stat-items">${data.stats.active_items}</strong><small>types de consommables</small></div>
      <div class="card"><span>Quantité totale</span><strong id="cons-stat-total">${data.stats.total_units}</strong><small>tous états confondus</small></div>
      <div class="card"><span>Stock bas</span><strong id="cons-stat-low">${data.stats.low_stock}</strong><small>≤ seuil minimum</small></div>
      <div class="card"><span>Unités KO</span><strong id="cons-stat-ko">${data.stats.ko_units}</strong><small>à traiter / rebut</small></div>
    </div>
    <div class="consumable-layout">
      <section class="card panel consumable-stock-panel"><div class="panel-head"><div><h2>Stock actuel</h2><p>Quantités séparées par état : neuf, ancien et KO.</p></div>${editable?'<button type="button" class="button" id="cons-new-item">+ Consommable</button>':''}</div>
        <div class="table-wrap"><table><thead><tr><th>Consommable</th><th>Catégorie</th><th>Stock</th><th>Total</th><th>Seuil</th><th>État</th>${editable?'<th></th>':''}</tr></thead><tbody id="cons-items"></tbody></table></div>
      </section>
      <aside class="consumable-forms consumable-actions-panel">
        ${editable?`<section class="card panel"><div class="panel-head"><div><h2>Entrée / sortie</h2><p>Chaque mouvement reste dans l'historique avec bénéficiaire, commentaire et auteur.</p></div></div>
          <form id="cons-movement-form" class="manage-form">
            <label class="full">Consommable<select name="consumable_id" required>${itemOptions()}</select></label>
            <label>Mouvement<select name="direction"><option value="SORTIE">Sortie</option><option value="ENTREE">Entrée</option></select></label>
            <label>État<select name="condition"><option value="NEUF">Neuf</option><option value="ANCIEN">Ancien</option><option value="KO">KO</option></select></label>
            <label>Quantité<input type="number" name="quantity" min="1" step="1" value="1" required></label>
            <label>Bénéficiaire<input name="beneficiary" list="cons-beneficiaries" placeholder="Agent / ID / service"></label>
            <datalist id="cons-beneficiaries">${directoryOptions()}</datalist>
            <label class="full">Commentaire<textarea name="comment" rows="3" placeholder="Motif de sortie, ticket, remplacement, retour, remarque…"></textarea></label>
            <div class="full form-actions"><button class="button">Enregistrer le mouvement</button><span id="cons-movement-result" class="form-result"></span></div>
          </form>
        </section>
        <dialog id="cons-item-dialog"><form id="cons-item-form" class="manage-form"><input type="hidden" name="id"><h2 id="cons-item-title">Nouveau consommable</h2><label class="full">Nom<input name="name" maxlength="100" required placeholder="Ex. Casque Jabra Biz 1500"></label><label>Catégorie<input name="category" maxlength="80" placeholder="Audio, câble, souris…"></label><label>Unité<input name="unit" maxlength="30" value="unité"></label><label>Seuil minimum<input type="number" name="min_quantity" min="0" step="1" value="0"></label><label class="switch-line"><input type="checkbox" name="active" checked><span class="switch"></span><span><strong>Actif</strong><small>Disponible pour les mouvements.</small></span></label><div class="full form-actions"><button class="button">Enregistrer</button><button type="button" class="button ghost" id="cons-item-cancel">Fermer</button><span id="cons-item-result" class="form-result"></span></div></form></dialog>`:'<div class="card panel"><div class="readonly-box"><strong>Lecture seule</strong><span>Les entrées/sorties nécessitent le droit Modification sur Consommables.</span></div></div>'}
      </aside>
    </div>
    <section class="card panel consumable-history-panel"><div class="panel-head"><div><h2>Historique des mouvements</h2><p>Filtre par date, mouvement, état, consommable, bénéficiaire ou commentaire.</p></div><a class="button ghost" id="cons-export" href="/api/consumables/export.csv">Exporter CSV</a></div>
      <form id="cons-history-filter" class="consumable-history-filters"><label>Du<input type="date" name="date_from" value="${monthStart()}"></label><label>Au<input type="date" name="date_to" value="${today()}"></label><label>Mouvement<select name="direction"><option value="">Tous</option><option value="ENTREE">Entrées</option><option value="SORTIE">Sorties</option></select></label><label>État<select name="condition"><option value="">Tous</option><option value="NEUF">Neuf</option><option value="ANCIEN">Ancien</option><option value="KO">KO</option></select></label><div class="form-actions"><button class="button">Filtrer</button><button type="button" class="button ghost" id="cons-filter-reset">Effacer</button></div><label class="consumable-full-width">Recherche<input name="q" placeholder="Consommable, bénéficiaire, commentaire, auteur…"></label></form>
      <div class="table-wrap"><table><thead><tr><th>Date</th><th>Consommable</th><th>Mouvement</th><th>État</th><th>Qté</th><th>Bénéficiaire</th><th>Commentaire</th><th>Saisi par</th></tr></thead><tbody id="cons-history"></tbody></table></div>
    </section>`;

  function render(){
    $('#cons-stat-items').textContent=data.stats.active_items;$('#cons-stat-total').textContent=data.stats.total_units;$('#cons-stat-low').textContent=data.stats.low_stock;$('#cons-stat-ko').textContent=data.stats.ko_units;
    $('#cons-items').innerHTML=data.items.map(x=>`<tr class="${Number(x.qty_total||0)<=Number(x.min_quantity||0)&&x.active?'low-stock-row':''}"><td><strong>${esc(x.name)}</strong><small class="sub">${esc(x.unit||'unité')}</small></td><td>${esc(x.category||'—')}</td><td>${stockChips(x)}</td><td><strong>${Number(x.qty_total||0)}</strong></td><td>${Number(x.min_quantity||0)}</td><td>${x.active?'<span class="fresh-badge fresh-green">Actif</span>':'<span class="fresh-badge fresh-gray">Désactivé</span>'}</td>${editable?`<td><div class="row-actions"><button class="button ghost small cons-edit" data-id="${x.id}">Modifier</button><button class="button ghost small cons-toggle" data-id="${x.id}">${x.active?'Désactiver':'Réactiver'}</button></div></td>`:''}</tr>`).join('')||`<tr><td colspan="${editable?7:6}" class="empty">Aucun consommable configuré.</td></tr>`;
    $('#cons-history').innerHTML=data.movements.map(m=>`<tr><td>${esc(m.created_at)}</td><td><strong>${esc(m.item_name)}</strong><small class="sub">${esc(m.category||'')}</small></td><td>${movementLabel(m.direction)}</td><td>${esc(conditionLabel(m.condition))}</td><td><strong>${Number(m.quantity||0)}</strong> ${esc(m.unit||'')}</td><td>${esc(m.beneficiary_name||m.beneficiary_identifier||'—')}</td><td>${esc(m.comment||'—')}</td><td>${esc(m.username||'—')}<small class="sub">${esc(m.source_ip||'')}</small></td></tr>`).join('')||'<tr><td colspan="8" class="empty">Aucun mouvement pour ces filtres.</td></tr>';
    if(editable){const sel=$('#cons-movement-form select[name="consumable_id"]');if(sel){const v=sel.value;sel.innerHTML=itemOptions();if([...sel.options].some(o=>o.value===v))sel.value=v;}}
    const p=new URLSearchParams(new FormData($('#cons-history-filter')));$('#cons-export').href='/api/consumables/export.csv?'+p.toString();
    wireRows();
  }
  async function reload(filters=true){let url='/api/consumables';if(filters)url+='?'+new URLSearchParams(new FormData($('#cons-history-filter')));data=await api(url);render();}
  function wireRows(){
    if(!editable)return;
    $$('.cons-edit').forEach(b=>b.onclick=()=>{const x=data.items.find(v=>Number(v.id)===Number(b.dataset.id));const f=$('#cons-item-form');f.elements.id.value=x.id;f.elements.name.value=x.name;f.elements.category.value=x.category||'';f.elements.unit.value=x.unit||'unité';f.elements.min_quantity.value=x.min_quantity||0;f.elements.active.checked=!!x.active;$('#cons-item-title').textContent='Modifier '+x.name;$('#cons-item-dialog').showModal();});
    $$('.cons-toggle').forEach(b=>b.onclick=async()=>{await api('/api/consumables/item/toggle',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:b.dataset.id})});reload();});
  }
  $('#cons-history-filter').onsubmit=e=>{e.preventDefault();reload(true);};
  $('#cons-filter-reset').onclick=()=>{$('#cons-history-filter').reset();reload(false);};
  $('#cons-history-filter').addEventListener('change',()=>{const p=new URLSearchParams(new FormData($('#cons-history-filter')));$('#cons-export').href='/api/consumables/export.csv?'+p.toString();});
  if(editable){
    $('#cons-new-item').onclick=()=>{const f=$('#cons-item-form');f.reset();f.elements.id.value='';f.elements.unit.value='unité';f.elements.min_quantity.value=0;f.elements.active.checked=true;$('#cons-item-title').textContent='Nouveau consommable';$('#cons-item-dialog').showModal();};
    $('#cons-item-cancel').onclick=()=>$('#cons-item-dialog').close();
    $('#cons-item-form').onsubmit=async e=>{e.preventDefault();const f=e.target,body=Object.fromEntries(new FormData(f));body.active=f.elements.active.checked;try{await api('/api/consumables/item',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});$('#cons-item-dialog').close();await reload();}catch(err){$('#cons-item-result').textContent=err.message;}};
    $('#cons-movement-form').onsubmit=async e=>{e.preventDefault();const f=e.target,body=Object.fromEntries(new FormData(f));body.quantity=Number(body.quantity);const out=$('#cons-movement-result');try{await api('/api/consumables/movement',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});out.textContent='Mouvement enregistré.';f.elements.quantity.value=1;f.elements.comment.value='';await reload();setTimeout(()=>out.textContent='',1800);}catch(err){out.textContent=err.message;}};
  }
  render();
}
