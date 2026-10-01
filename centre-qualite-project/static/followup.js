/* Inventory follow-up: data-only rules; no automatic saves or network polling. */
window.InventoryFollowup = (() => {
  'use strict';
  const escape = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const palette = {green:'Vert',yellow:'Jaune',orange:'Orange',red:'Rouge',blue:'Bleu',purple:'Violet',gray:'Gris'};
  const adminStates = {EN_SERVICE:'En service',STOCK:'En stock',REPARATION:'En r\u00e9paration',PERDU:'Perdu',REFORME:'R\u00e9form\u00e9'};
  const base = [['EN_SERVICE','\u00c0 jour','green'],['PAS_A_JOUR','Pas \u00e0 jour','yellow'],['RETARD_7J','Retard','orange'],['CRITIQUE','Critique','red'],['STOCK','En stock','blue'],['REPARATION','R\u00e9paration','orange'],['KO','KO / perdu','red'],['REFORME','R\u00e9form\u00e9','gray']];
  const copy = value => JSON.parse(JSON.stringify(value));
  function defaults() {
    return {version:2,categories:base.map(([id,label,color])=>({id,label,color})),ranges:[{min_days:0,max_days:0,status:'EN_SERVICE'},{min_days:1,max_days:7,status:'PAS_A_JOUR'},{min_days:8,max_days:20,status:'RETARD_7J'},{min_days:21,max_days:null,status:'CRITIQUE'}],never_seen:'CRITIQUE',admin_overrides:{EN_SERVICE:null,STOCK:'STOCK',REPARATION:'REPARATION',PERDU:'KO',REFORME:'REFORME'}};
  }
  function validate(p) {
    if (!p || p.version !== 2 || !Array.isArray(p.categories) || p.categories.length < 8 || p.categories.length > 32) return 'Conservez les libell\u00e9s historiques ; 32 libell\u00e9s maximum.';
    const ids = new Set(), labels = new Set();
    for (const c of p.categories) {
      const label = String(c.label || '').trim();
      if (!/^[A-Z][A-Z0-9_]{0,39}$/.test(c.id) || ids.has(c.id)) return 'Identifiant de suivi invalide ou dupliqu\u00e9.';
      if (!label || label.length > 60 || /[\x00-\x1f]/.test(label)) return 'Chaque libell\u00e9 doit contenir de 1 \u00e0 60 caract\u00e8res.';
      const folded = label.toLocaleLowerCase('fr');
      if (labels.has(folded)) return 'Deux libell\u00e9s ne peuvent pas porter le m\u00eame nom.';
      if (!Object.hasOwn(palette,c.color)) return 'Choisissez une couleur propos\u00e9e.';
      ids.add(c.id); labels.add(folded);
    }
    if (base.some(([id])=>!ids.has(id))) return 'Les cat\u00e9gories historiques doivent \u00eatre conserv\u00e9es.';
    if (!Array.isArray(p.ranges) || !p.ranges.length || p.ranges.length > 32) return 'Choisissez entre 1 et 32 tranches de jours.';
    let next = 0;
    for (let i=0;i<p.ranges.length;i++) {
      const r=p.ranges[i];
      if (!Number.isInteger(r.min_days) || r.min_days !== next || r.min_days<0 || r.min_days>36500) return `La tranche ${i+1} doit commencer au jour ${next}.`;
      if (!ids.has(r.status)) return 'Choisissez un libell\u00e9 existant pour chaque tranche.';
      if (i === p.ranges.length-1) { if (r.max_days !== null) return 'La derni\u00e8re tranche doit \u00eatre sans limite.'; }
      else if (!Number.isInteger(r.max_days) || r.max_days<r.min_days || r.max_days>=36500) return `La fin de la tranche ${i+1} doit \u00eatre un jour entier compris entre ${r.min_days} et 36499.`;
      next = r.max_days+1;
    }
    if (!ids.has(p.never_seen)) return 'Choisissez un libell\u00e9 pour les postes sans diagnostic.';
    if (!p.admin_overrides || Object.keys(p.admin_overrides).length!==5 || Object.keys(adminStates).some(k=>!Object.hasOwn(p.admin_overrides,k)||p.admin_overrides[k]!==null&&!ids.has(p.admin_overrides[k]))) return 'Renseignez chaque \u00e9tat administratif.';
    return '';
  }
  function evaluate(p, days, state='EN_SERVICE') {
    const target=p.admin_overrides[state];
    if(target) return {status:target,reason:`L'\u00e9tat administratif \u00ab ${adminStates[state]} \u00bb est prioritaire.`};
    if(days===null) return {status:p.never_seen,reason:'Aucun diagnostic dat\u00e9 exploitable.'};
    const n=Math.max(0,Math.trunc(Number(days)));
    const range=p.ranges.find(r=>n>=r.min_days && (r.max_days===null || n<=r.max_days));
    return {status:range?.status||p.never_seen,reason:range?`Tranche appliqu\u00e9e : ${rangeText(range)}.`:'Aucun diagnostic dat\u00e9 exploitable.'};
  }
  function rangeText(r) {
    if(r.max_days===null) return `\u00c0 partir de ${r.min_days} jours`;
    if(r.min_days===0 && r.max_days===0) return "Aujourd'hui";
    if(r.min_days===r.max_days) return `${r.min_days} jour${r.min_days===1?'':'s'}`;
    return `${r.min_days} \u00e0 ${r.max_days} jours`;
  }
  function summary(p,id) {
    const lines=p.ranges.filter(r=>r.status===id).map(rangeText);
    if(p.never_seen===id) lines.push('Sans diagnostic');
    return lines.join(' / ');
  }
  function color(p,id) { const c=p?.categories.find(c=>c.id===id)?.color; return Object.hasOwn(palette,c)?c:'gray'; }
  function optionList(p,value,allowDate=false) {
    return (allowDate?`<option value="" ${!value?'selected':''}>Calculer selon la date</option>`:'') + p.categories.map(c=>`<option value="${escape(c.id)}" ${value===c.id?'selected':''}>${escape(c.label)}</option>`).join('');
  }
  function filterOptions(p) { return p.categories.map(c=>`<option value="${escape(c.id)}">${escape(c.label)}${summary(p,c.id)?' \u00b7 '+escape(summary(p,c.id)):''}</option>`).join(''); }
  function dashboard(p,counts={}) {
    const dateIds = new Set([...p.ranges.map(r=>r.status),p.never_seen]);
    const adminIds = new Set(Object.values(p.admin_overrides).filter(Boolean));
    const dateCards=p.categories.filter(c=>dateIds.has(c.id)).map(c=>`<div class="card metric metric-${color(p,c.id)}"><span>${escape(c.label)}</span><b>${Number(counts[c.id]||0)}</b><small>${escape(summary(p,c.id))}</small></div>`).join('');
    const adminCards=p.categories.filter(c=>adminIds.has(c.id)&&!dateIds.has(c.id)).map(c=>`<div><span class="fresh-badge fresh-${color(p,c.id)}">${escape(c.label)}</span><strong>${Number(counts[c.id]||0)}</strong></div>`).join('');
    return `<div class="cards status-cards followup-status-cards">${dateCards}</div>${adminCards?`<div class="park-admin-strip">${adminCards}</div>`:''}`;
  }
  function render(config,writable=true) {
    return `<section class="card panel followup-settings-panel"><div class="panel-head"><div><h2>R\u00e8gles de suivi du parc</h2><p>Choisissez les d\u00e9lais, les libell\u00e9s et les couleurs. Le suivi ne modifie pas l'\u00e9tat administratif du PC.</p></div></div>${config.warning?`<div class="flash warn">${escape(config.warning)}</div>`:''}<form id="followup-policy-form" novalidate data-writable="${writable?'1':'0'}"><div id="followup-editor-fields"></div><div class="followup-savebar"><button type="submit" class="button" id="followup-save" ${!writable?'disabled':''}>Enregistrer les r\u00e8gles</button><button type="button" class="button ghost" id="followup-reset" ${!writable?'disabled':''}>Valeurs par d\u00e9faut</button><span id="followup-policy-result" role="status" aria-live="polite">${writable?'Aucune modification.':'Lecture seule.'}</span></div></form><section class="followup-simulator" aria-labelledby="followup-test-title"><h3 id="followup-test-title">Tester un cas</h3><div class="followup-test-fields"><label>\u00c9tat administratif<select id="followup-test-state">${Object.entries(adminStates).map(([k,v])=>`<option value="${k}">${v}</option>`).join('')}</select></label><label>Jours sans diagnostic<input id="followup-test-days" type="number" min="0" max="36500" step="1" value="8"></label><label class="followup-check"><input id="followup-test-never" type="checkbox">Aucun diagnostic</label></div><div id="followup-preview" class="followup-preview" role="status" aria-live="polite"></div><small class="muted">Aper\u00e7u des r\u00e8gles affich\u00e9es, m\u00eame avant enregistrement. Aucun PC n'est modifi\u00e9.</small></section></section>`;
  }
  let activeEditor=null;
  window.addEventListener('beforeunload',e=>{if(activeEditor?.dirty()){e.preventDefault();e.returnValue='';}});
  document.addEventListener('click',e=>{
    const a=e.target.closest('a[href^="#"]');
    if(a && a.hash!==location.hash && a.hash!=='#app' && activeEditor?.dirty() && !confirm('Quitter cette page sans enregistrer les r\u00e8gles de suivi ?')){e.preventDefault();e.stopImmediatePropagation();}
  },true);
  function bind(config,{save,writable=true,onSaved=()=>{}}) {
    const form=document.getElementById('followup-policy-form'); if(!form)return;
    const host=document.getElementById('followup-editor-fields');
    const out=document.getElementById('followup-policy-result');
    let draft=copy(config.policy||defaults()),saved=JSON.stringify(draft),revision=config.revision,busy=false;
    const q=s=>form.closest('section').querySelector(s);
    const dirty=()=>writable&&form.isConnected&&JSON.stringify(draft)!==saved;
    activeEditor={dirty};
    const used=id=>draft.ranges.some(r=>r.status===id)||draft.never_seen===id||Object.values(draft.admin_overrides).includes(id);
    function fields() {
      const open=new Set([...host.querySelectorAll('details[open]')].map(el=>el.dataset.followupPanel));
      host.innerHTML=`<fieldset ${!writable?'disabled':''}><legend class="followup-legend">D\u00e9lais sans diagnostic</legend><p class="followup-hint">Les bornes sont incluses. Le d\u00e9but de chaque tranche suit automatiquement la pr\u00e9c\u00e9dente.</p><div class="followup-ranges">${draft.ranges.map((r,i)=>`<div class="followup-range" data-range="${i}"><div class="followup-range-start"><small>\u00c0 partir de</small><strong data-range-start="${i}">${r.min_days} j</strong></div><label>Jusqu'\u00e0${i===draft.ranges.length-1?'<span class="followup-unbounded">Sans limite</span>':`<input type="number" min="${r.min_days}" max="36499" step="1" data-range-end="${i}" value="${r.max_days??''}" aria-label="Fin de la tranche ${i+1} en jours">`}</label><label>Suivi affich\u00e9<select data-range-status="${i}">${optionList(draft,r.status)}</select></label><button type="button" class="button ghost followup-remove" data-remove-range="${i}" aria-label="Supprimer la tranche ${i+1}" ${draft.ranges.length===1?'disabled':''}>Retirer</button></div>`).join('')}</div><button type="button" class="button ghost" id="followup-add-range" ${draft.ranges.length>=32?'disabled':''}>Ajouter une tranche</button><label class="followup-never">Sans diagnostic exploitable<select data-never>${optionList(draft,draft.never_seen)}</select></label></fieldset><details class="followup-disclosure" data-followup-panel="labels" ${open.has('labels')?'open':''}><summary>Libell\u00e9s et couleurs <span>${draft.categories.length}</span></summary><fieldset ${!writable?'disabled':''}><div class="followup-categories">${draft.categories.map((c,i)=>`<div class="followup-category"><label>Libell\u00e9<input data-category-label="${i}" maxlength="60" value="${escape(c.label)}" aria-label="Libell\u00e9 ${i+1}"></label><label>Couleur<select data-category-color="${i}">${Object.entries(palette).map(([key,label])=>`<option value="${key}" ${c.color===key?'selected':''}>${label}</option>`).join('')}</select></label><span class="fresh-badge fresh-${color(draft,c.id)}" data-category-preview="${i}">${escape(c.label)}</span>${base.some(([id])=>id===c.id)?'<span class="followup-protected" title="Cat\u00e9gorie historique conserv\u00e9e">Standard</span>':`<button type="button" class="button ghost followup-remove" data-remove-category="${i}" ${used(c.id)?'disabled title="Ce libell\u00e9 est utilis\u00e9 par une r\u00e8gle"':''}>Retirer</button>`}</div>`).join('')}</div><button type="button" class="button ghost" id="followup-add-category" ${draft.categories.length>=32?'disabled':''}>Ajouter un libell\u00e9</button></fieldset></details><details class="followup-disclosure" data-followup-panel="states" ${open.has('states')?'open':''}><summary>Priorit\u00e9 des \u00e9tats administratifs</summary><p class="followup-hint">Un suivi choisi ici remplace le calcul par date, m\u00eame sans diagnostic.</p><fieldset class="followup-state-grid" ${!writable?'disabled':''}>${Object.entries(adminStates).map(([k,label])=>`<label>${label}<select data-admin-state="${k}">${optionList(draft,draft.admin_overrides[k],true)}</select></label>`).join('')}</fieldset></details>`;
      refresh();
    }
    function recalculate() {
      let start=0;
      draft.ranges.forEach((r,i)=>{r.min_days=start;const el=host.querySelector(`[data-range-start="${i}"]`);if(el)el.textContent=Number.isInteger(start)?`${start} j`:'\u2014';const input=host.querySelector(`[data-range-end="${i}"]`);if(input && Number.isInteger(start))input.min=String(start);start=Number.isInteger(r.max_days)?r.max_days+1:NaN;});
    }
    function preview() {
      const error=validate(draft),el=q('#followup-preview'),never=q('#followup-test-never').checked;
      q('#followup-test-days').disabled=never;
      const raw=q('#followup-test-days').value,days=never?null:Number(raw);
      if(error){el.textContent=error;el.classList.add('is-error');return;}
      if(!never && (raw===''||!Number.isInteger(days)||days<0||days>36500)){el.textContent='Indiquez un nombre entier de jours entre 0 et 36500.';el.classList.add('is-error');return;}
      const result=evaluate(draft,days,q('#followup-test-state').value),c=draft.categories.find(x=>x.id===result.status);
      el.classList.remove('is-error');el.innerHTML=`<span class="fresh-badge fresh-${color(draft,result.status)}">${escape(c.label)}</span><span>${escape(result.reason)}</span>`;el.dataset.status=result.status;
    }
    function refresh() {
      const error=validate(draft);q('#followup-save').disabled=!writable||busy||!!error||!dirty();
      if(!busy){out.textContent=error||(writable?(dirty()?'Modifications non enregistr\u00e9es.':'Aucune modification.'):'Lecture seule.');out.classList.toggle('is-error',!!error);}
      preview();
    }
    host.addEventListener('input',e=>{
      if(!writable||busy)return;
      const el=e.target,d=el.dataset;
      if(d.rangeEnd!==undefined){draft.ranges[Number(d.rangeEnd)].max_days=el.value===''?null:Number(el.value);recalculate();}
      if(d.rangeStatus!==undefined)draft.ranges[Number(d.rangeStatus)].status=el.value;
      if(d.categoryLabel!==undefined)draft.categories[Number(d.categoryLabel)].label=el.value;
      if(d.categoryColor!==undefined)draft.categories[Number(d.categoryColor)].color=el.value;
      if(d.adminState!==undefined)draft.admin_overrides[d.adminState]=el.value||null;
      if(Object.hasOwn(d,'never'))draft.never_seen=el.value;
      if(d.categoryLabel!==undefined||d.categoryColor!==undefined){
        host.querySelectorAll('select[data-range-status],select[data-admin-state],select[data-never]').forEach(select=>{const value=select.value;select.innerHTML=optionList(draft,value,Object.hasOwn(select.dataset,'adminState'));});
        draft.categories.forEach((c,i)=>{const badge=host.querySelector(`[data-category-preview="${i}"]`);if(badge){badge.textContent=c.label;badge.className=`fresh-badge fresh-${color(draft,c.id)}`;}});
      }
      host.querySelectorAll('[data-remove-category]').forEach(b=>b.disabled=used(draft.categories[Number(b.dataset.removeCategory)].id));
      refresh();
    });
    host.addEventListener('click',e=>{
      if(!writable||busy)return;
      const b=e.target.closest('button');if(!b||b.disabled)return;
      if(b.id==='followup-add-range'){
        if(validate(draft)){out.textContent='Corrigez les tranches avant d\u2019en ajouter une.';return;}
        const last=draft.ranges.at(-1);if(last.min_days>=36500){out.textContent='La limite de 36500 jours est atteinte.';return;}
        last.max_days=Math.min(36499,last.min_days+6);draft.ranges.push({min_days:last.max_days+1,max_days:null,status:last.status});fields();host.querySelector(`[data-range-end="${draft.ranges.length-2}"]`)?.focus();
      } else if(Object.hasOwn(b.dataset,'removeRange')){
        const i=Number(b.dataset.removeRange);if(draft.ranges.length<=1)return;
        draft.ranges.splice(i,1);draft.ranges.at(-1).max_days=null;recalculate();fields();
      } else if(b.id==='followup-add-category'){
        const ids=new Set(draft.categories.map(c=>c.id));let n=1;while(ids.has('PERSO_'+n)||draft.categories.some(c=>c.label==='Nouveau suivi '+n))n++;
        draft.categories.push({id:'PERSO_'+n,label:'Nouveau suivi '+n,color:'blue'});fields();host.querySelector('[data-followup-panel="labels"]').open=true;const input=host.querySelector(`[data-category-label="${draft.categories.length-1}"]`);input.focus();input.select();
      } else if(Object.hasOwn(b.dataset,'removeCategory')){
        const i=Number(b.dataset.removeCategory),c=draft.categories[i];if(used(c.id)||base.some(([id])=>id===c.id))return;
        draft.categories.splice(i,1);fields();
      }
    });
    q('#followup-reset').onclick=()=>{if(!writable||busy||!confirm('Remettre les valeurs par d\u00e9faut dans le formulaire ? Elles ne seront appliqu\u00e9es qu\u2019apr\u00e8s enregistrement.'))return;draft=defaults();fields();};
    q('.followup-simulator').addEventListener('input',preview);
    form.onsubmit=async e=>{
      e.preventDefault();if(!writable||busy)return;const error=validate(draft);if(error){out.textContent=error;return;}
      busy=true;const snapshot=copy(draft);q('#followup-save').disabled=true;q('#followup-reset').disabled=true;out.textContent='Enregistrement\u2026';
      host.querySelectorAll('fieldset').forEach(f=>f.disabled=true);
      try{const r=await save({policy:snapshot,expected_revision:revision});revision=r.followup_config.revision;draft=copy(r.followup_config.policy);saved=JSON.stringify(draft);onSaved(r.followup_config);if(!form.isConnected)return;fields();out.textContent='R\u00e8gles enregistr\u00e9es.';out.classList.remove('is-error');}
      catch(err){if(form.isConnected){out.textContent=err.message||'Enregistrement impossible.';out.classList.add('is-error');}}
      finally{busy=false;if(form.isConnected){host.querySelectorAll('fieldset').forEach(f=>f.disabled=!writable);q('#followup-reset').disabled=!writable;q('#followup-save').disabled=!writable||!!validate(draft)||!dirty();preview();}}
    };
    fields();
  }
  return {defaults,validate,evaluate,rangeText,summary,color,filterOptions,dashboard,render,bind};
})();
