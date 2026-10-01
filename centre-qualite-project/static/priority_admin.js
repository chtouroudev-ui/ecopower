let supportPrioritySettingsTab='score';
const priorityAdminStyleCache=new Set();
const priorityScoreRecommended={
  technical_disconnect_points:1,
  in_call_bonus_points:4,
  collective_disconnect_points:0,
  probable_closure_points:0,
  collective_window_seconds:60,
  collective_min_agents:4,
  burst_window_minutes:30,
  burst_min_count:3,
  burst_points:4,
  recurrence_days_threshold:3,
  recurrence_days_points:4,
  recurrence_percent_threshold:50,
  recurrence_percent_min_worked_days:3,
  recurrence_percent_points:6,
  lost_minutes_low_threshold:5,
  lost_minutes_low_points:3,
  lost_minutes_high_threshold:10,
  lost_minutes_high_points:6,
  probable_closure_enabled:true,
  probable_closure_start_from:'11:50',
  probable_closure_start_to:'13:10',
  probable_closure_min_minutes:45,
  probable_closure_max_minutes:75,
  probable_closure_activity_tolerance_minutes:10
};

function priorityAdminColorClass(color){
  const safe=/^#[0-9a-f]{6}$/i.test(String(color||''))?String(color).toLowerCase():'#667085';
  const cls=`priority-admin-color-${safe.slice(1)}`;
  if(!priorityAdminStyleCache.has(cls)){
    const rule=`.${cls}{background:${safe}!important;border-color:${safe}!important}`;
    for(const sheet of Array.from(document.styleSheets||[])){
      try{
        if(sheet.href&&sheet.href.includes('/static/style.css')){
          sheet.insertRule(rule,sheet.cssRules.length);
          priorityAdminStyleCache.add(cls);
          break;
        }
      }catch(_e){}
    }
  }
  return cls;
}

function priorityAdminMetricOptions(catalog,selected=''){
  return (catalog||[]).map(m=>`<option value="${esc(m.key)}" ${m.key===selected?'selected':''}>${esc(m.label)}${m.unit?` \u00b7 ${esc(m.unit)}`:''}</option>`).join('');
}

function priorityAdminOperatorOptions(operators,selected='>='){
  const labels={'>':'sup\u00e9rieur \u00e0','>=':'sup\u00e9rieur ou \u00e9gal','<':'inf\u00e9rieur \u00e0','<=':'inf\u00e9rieur ou \u00e9gal','==':'\u00e9gal \u00e0','!=':'diff\u00e9rent de'};
  return (operators||['>','>=','<','<=','==','!=']).map(op=>`<option value="${esc(op)}" ${op===selected?'selected':''}>${esc(op)} \u00b7 ${esc(labels[op]||op)}</option>`).join('');
}

function priorityAdminConditionRow(catalog,operators,c={}){
  const metric=c.metric||(catalog?.[0]?.key||'technical_score');
  const operator=c.operator||'>=';
  const value=c.value??5;
  return `<div class="priority-condition-row">
    <select class="priority-condition-metric" aria-label="Mesure">${priorityAdminMetricOptions(catalog,metric)}</select>
    <select class="priority-condition-operator" aria-label="Op\u00e9rateur">${priorityAdminOperatorOptions(operators,operator)}</select>
    <input class="priority-condition-value" type="number" step="0.1" min="0" value="${esc(value)}" aria-label="Seuil">
    <button type="button" class="icon-btn remove-priority-condition" title="Supprimer la condition">\u00d7</button>
  </div>`;
}

function priorityAdminConditionText(c,catalog){
  const meta=(catalog||[]).find(m=>m.key===c.metric)||{};
  const label=meta.label||c.metric||'Mesure';
  return `${label} ${c.operator||'>='} ${c.value}${meta.unit?` ${meta.unit}`:''}`;
}

function priorityAdminPolicySummary(p,catalog){
  if(p.is_fallback)return 'Niveau de repli automatique si aucune autre r\u00e8gle ne correspond.';
  const conditions=p.conditions||[];
  if(!conditions.length)return 'Aucune condition configur\u00e9e.';
  const joiner=p.match_mode==='ALL'?' ET ':' OU ';
  return conditions.map(c=>priorityAdminConditionText(c,catalog)).join(joiner);
}

function priorityAdminPolicyCard(p,catalog,operators,isNew=false){
  const fallback=!!p.is_fallback;
  const conditions=(p.conditions||[]);
  const rows=(conditions.length?conditions:[{metric:'technical_score',operator:'>=',value:5}]).map(c=>priorityAdminConditionRow(catalog,operators,c)).join('');
  const name=p.priority||'';
  const rank=p.rank??100;
  const color=/^#[0-9a-f]{6}$/i.test(String(p.color||''))?String(p.color):'#667085';
  const colorClass=priorityAdminColorClass(color);
  const summary=priorityAdminPolicySummary(p,catalog);
  return `<form class="card priority-policy-form priority-guided-level ${isNew?'priority-new-policy':''}" data-priority="${esc(name)}" data-new="${isNew?'1':'0'}">
    <div class="priority-guided-level-head">
      <div class="priority-guided-level-title"><span class="priority-admin-swatch ${colorClass}"></span><div><small>${isNew?'NOUVEAU NIVEAU':`RANG ${esc(rank)}`}</small><h3>${isNew?'Cr\u00e9er un niveau':esc(name)}</h3><p>${esc(summary)}</p></div></div>
      <div class="priority-guided-level-badges">${fallback?'<span class="priority-state-chip fallback">REPLI</span>':p.enabled===0?'<span class="priority-state-chip off">D\u00c9SACTIV\u00c9</span>':'<span class="priority-state-chip on">ACTIF</span>'}</div>
    </div>
    <details class="priority-guided-editor" ${isNew?'open':''}>
      <summary>${isNew?'Configurer ce nouveau niveau':'Modifier ce niveau'}</summary>
      <div class="priority-policy-settings">
        <label>Nom de l'\u00e9tat<input name="priority" maxlength="60" required value="${esc(name)}" placeholder="Ex. Critique, Surveillance, P1 r\u00e9seau..."><small>Nom affich\u00e9 dans le tableau Support.</small></label>
        <label>Ordre de priorit\u00e9<input name="rank" type="number" min="-10000" max="10000" step="1" value="${esc(rank)}"><small>Le rang le plus grand est test\u00e9 en premier.</small></label>
        <label>Couleur<input name="color" type="color" value="${esc(color)}"><small>Couleur du badge dans Support.</small></label>
        <label>Logique<select name="match_mode"><option value="ANY" ${p.match_mode!=='ALL'?'selected':''}>AU MOINS UNE condition (OU)</option><option value="ALL" ${p.match_mode==='ALL'?'selected':''}>TOUTES les conditions (ET)</option></select><small>OU = plus sensible. ET = plus strict.</small></label>
        <label class="switch-line"><input type="checkbox" name="enabled" ${p.enabled===0?'':'checked'} ${fallback?'disabled':''}><span class="switch"></span><span><strong>Niveau actif</strong><small>Un niveau d\u00e9sactiv\u00e9 est ignor\u00e9.</small></span></label>
        <label class="switch-line"><input type="checkbox" name="is_fallback" ${fallback?'checked':''}><span class="switch"></span><span><strong>Niveau de repli</strong><small>Utilis\u00e9 si aucune r\u00e8gle ne correspond.</small></span></label>
      </div>
      <div class="priority-conditions-editor" ${fallback?'hidden':''}>
        <div class="priority-condition-title"><div><strong>Conditions</strong><small>Commence simplement avec le score technique. Ajoute d'autres mesures seulement si tu en as besoin.</small></div><button type="button" class="button ghost small add-priority-condition">+ Condition</button></div>
        <div class="priority-condition-list">${rows}</div>
      </div>
      <div class="form-actions priority-policy-actions"><button class="button" type="submit">${isNew?'Cr\u00e9er le niveau':'Enregistrer ce niveau'}</button>${!isNew&&!fallback?'<button type="button" class="button danger small delete-priority-policy">Supprimer</button>':''}<span class="form-result priority-policy-result"></span></div>
    </details>
  </form>`;
}

function priorityAdminPayload(form){
  const isFallback=form.elements.is_fallback.checked;
  const conditions=isFallback?[]:[...form.querySelectorAll('.priority-condition-row')].map(row=>{
    const raw=row.querySelector('.priority-condition-value').value.trim();
    return {metric:row.querySelector('.priority-condition-metric').value,operator:row.querySelector('.priority-condition-operator').value,value:raw===''?NaN:Number(raw)};
  });
  return {original_priority:form.dataset.new==='1'?'':form.dataset.priority,priority:form.elements.priority.value,rank:Number(form.elements.rank.value),color:form.elements.color.value,match_mode:form.elements.match_mode.value,enabled:isFallback?true:form.elements.enabled.checked,is_fallback:isFallback,conditions};
}

function priorityScoreInput(name,label,value,help,recommended,type='number',attrs=''){
  const reco=recommended!==undefined&&recommended!==null?`<span class="priority-recommended">Recommand\u00e9 : ${esc(recommended)}</span>`:'';
  return `<label class="priority-score-field"><span class="priority-score-field-title">${esc(label)}</span><input name="${esc(name)}" type="${esc(type)}" value="${esc(value)}" ${attrs}><small>${esc(help)}</small>${reco}</label>`;
}

function priorityScoreExample(cfg){
  const worked=5,affected=4,technical=20,inCall=5,bursts=2,lost=12;
  let score=(technical/worked)*Number(cfg.technical_disconnect_points||0)+(inCall/worked)*Number(cfg.in_call_bonus_points||0)+(bursts/worked)*Number(cfg.burst_points||0);
  if(affected>=Number(cfg.recurrence_days_threshold||0))score+=Number(cfg.recurrence_days_points||0);
  const pct=affected*100/worked;
  if(worked>=Number(cfg.recurrence_percent_min_worked_days||0)&&pct>=Number(cfg.recurrence_percent_threshold||0))score+=Number(cfg.recurrence_percent_points||0);
  if(lost>=Number(cfg.lost_minutes_high_threshold||0))score+=Number(cfg.lost_minutes_high_points||0);
  else if(lost>=Number(cfg.lost_minutes_low_threshold||0))score+=Number(cfg.lost_minutes_low_points||0);
  return Math.round(score*100)/100;
}

function priorityAdminLevelRail(policies,catalog){
  const ordered=(policies||[]).slice().sort((a,b)=>(Number(b.rank)||0)-(Number(a.rank)||0));
  return ordered.map((p,i)=>{
    const cls=priorityAdminColorClass(p.color||'#667085');
    return `<div class="priority-rail-item ${p.enabled===0?'disabled':''}"><span class="priority-rail-dot ${cls}"></span><div><small>${p.is_fallback?'REPLI':`RANG ${esc(p.rank)}`}</small><strong>${esc(p.priority)}</strong><span>${esc(priorityAdminPolicySummary(p,catalog))}</span></div>${i<ordered.length-1?'<b class="priority-rail-arrow">\u2192</b>':''}</div>`;
  }).join('');
}

function priorityAdminSetTab(name){
  supportPrioritySettingsTab=name||'score';
  document.querySelectorAll('.priority-settings-tab').forEach(b=>b.classList.toggle('active',b.dataset.priorityTab===supportPrioritySettingsTab));
  document.querySelectorAll('.priority-settings-section').forEach(s=>s.hidden=s.dataset.prioritySection!==supportPrioritySettingsTab);
}

async function supportPrioritySettings(){
  const viewTicket=captureViewTicket();
  if(!canOpenInterface('support_priority')){redirectAllowed();return;}
  activate('support-priority');
  setHead('Priorit\u00e9s Support','Configure le score technique et les niveaux de priorit\u00e9 dans une interface d\u00e9di\u00e9e et guid\u00e9e.');
  const d=await api('/api/support-priority');
  const score=d.support_score_config||{};
  const policies=d.priority_policies||[];
  const metrics=d.priority_metrics||[];
  const operators=d.priority_operators||['>','>=','<','<=','==','!='];
  const nextRank=(policies.length?Math.max(...policies.map(p=>Number(p.rank)||0)):0)+100;
  const example=priorityScoreExample(score);
  const write=canWriteInterface('support_priority');
  if(!viewTicketIsCurrent(viewTicket))return;
  app.innerHTML=`
    <section class="card priority-dedicated-hero">
      <div class="priority-dedicated-copy"><span class="eyebrow">ADMINISTRATION \u00b7 SUPPORT TECHNIQUE</span><h2>Priorit\u00e9s Support</h2><p>Le moteur reste identique. Cette page le pr\u00e9sente simplement en trois \u00e9tapes pour que tu saches toujours ce que tu modifies.</p></div>
      <div class="priority-flow-guide">
        <div><span>1</span><strong>Classer l'\u00e9v\u00e9nement</strong><small>Technique, en appel, collectif ou fermeture probable.</small></div>
        <b>\u2192</b>
        <div><span>2</span><strong>Calculer le score</strong><small>Fr\u00e9quence + r\u00e9p\u00e9tition + r\u00e9currence + temps perdu.</small></div>
        <b>\u2192</b>
        <div><span>3</span><strong>Attribuer la priorit\u00e9</strong><small>Le premier niveau actif qui correspond est utilis\u00e9.</small></div>
      </div>
    </section>

    <nav class="priority-settings-tabs card" aria-label="Sections Priorit\u00e9s Support">
      <button type="button" class="priority-settings-tab" data-priority-tab="score"><span>1</span><b>Score technique</b><small>Les points et les d\u00e9tections</small></button>
      <button type="button" class="priority-settings-tab" data-priority-tab="levels"><span>2</span><b>Niveaux de priorit\u00e9</b><small>Normal, Surveillance, Critique...</small></button>
      <button type="button" class="priority-settings-tab" data-priority-tab="help"><span>?</span><b>Aide & exemples</b><small>Comprendre quoi modifier</small></button>
    </nav>

    <div class="priority-settings-section" data-priority-section="score">
      <div class="priority-config-layout">
        <form id="support-score-form" class="priority-score-form-guided">
          <details class="card priority-config-card" open>
            <summary><div><span class="priority-step-number">A</span><div><strong>Impact direct des coupures</strong><small>Les quatre multiplicateurs principaux du score.</small></div></div><span class="priority-summary-hint">Commencer ici</span></summary>
            <div class="priority-config-card-body">
              <div class="priority-field-grid two">
                ${priorityScoreInput('technical_disconnect_points','D\u00e9connexion technique / jour travaill\u00e9',score.technical_disconnect_points??1,'Poids de base. Exemple : 4 coupures/jour x 1 = 4 points.',1,'number','min="0" max="100" step="0.5"')}
                ${priorityScoreInput('in_call_bonus_points','Coupure en appel / jour travaill\u00e9',score.in_call_bonus_points??4,'Poids suppl\u00e9mentaire des coupures qui arrivent pendant un appel.',4,'number','min="0" max="100" step="0.5"')}
                ${priorityScoreInput('collective_disconnect_points','Incident collectif / jour travaill\u00e9',score.collective_disconnect_points??0,'0 signifie : visible comme incident infrastructure, mais ne p\u00e9nalise pas l\'agent.',0,'number','min="0" max="100" step="0.5"')}
                ${priorityScoreInput('probable_closure_points','Fermeture / pause probable / jour travaill\u00e9',score.probable_closure_points??0,'0 est recommand\u00e9 : l\'\u00e9v\u00e9nement reste visible sans augmenter le score individuel.',0,'number','min="0" max="100" step="0.5"')}
              </div>
            </div>
          </details>

          <details class="card priority-config-card" open>
            <summary><div><span class="priority-step-number">B</span><div><strong>R\u00e9p\u00e9tition & r\u00e9currence</strong><small>Fait monter les cas qui reviennent souvent ou plusieurs jours.</small></div></div><span class="priority-summary-hint">Important</span></summary>
            <div class="priority-config-card-body">
              <div class="priority-mini-group"><div><strong>S\u00e9ries rapproch\u00e9es</strong><small>Exemple : plusieurs coupures dans une demi-heure.</small></div><div class="priority-field-grid three">
                ${priorityScoreInput('burst_min_count','Nombre minimum',score.burst_min_count??3,'Nombre de coupures n\u00e9cessaires pour cr\u00e9er une s\u00e9rie.',3,'number','min="2" max="50" step="1"')}
                ${priorityScoreInput('burst_window_minutes','Fen\u00eatre en minutes',score.burst_window_minutes??30,'Dur\u00e9e dans laquelle les coupures sont regroup\u00e9es.',30,'number','min="1" max="240" step="1"')}
                ${priorityScoreInput('burst_points','Points par s\u00e9rie / jour travaill\u00e9',score.burst_points??4,'Poids d\u2019une s\u00e9rie r\u00e9p\u00e9titive.',4,'number','min="0" max="100" step="0.5"')}
              </div></div>
              <div class="priority-mini-group"><div><strong>R\u00e9currence en jours</strong><small>Ajoute un bonus quand le probl\u00e8me revient plusieurs jours.</small></div><div class="priority-field-grid two">
                ${priorityScoreInput('recurrence_days_threshold','Jours touch\u00e9s minimum',score.recurrence_days_threshold??3,'A partir de ce nombre de jours touch\u00e9s, le bonus s\u2019applique.',3,'number','min="1" max="366" step="1"')}
                ${priorityScoreInput('recurrence_days_points','Points ajout\u00e9s',score.recurrence_days_points??4,'Bonus fixe lorsque le seuil de jours est atteint.',4,'number','min="0" max="100" step="0.5"')}
              </div></div>
              <div class="priority-mini-group"><div><strong>R\u00e9currence en pourcentage</strong><small>Mesure la part des jours travaill\u00e9s qui sont touch\u00e9s.</small></div><div class="priority-field-grid three">
                ${priorityScoreInput('recurrence_percent_threshold','% de jours travaill\u00e9s touch\u00e9s',score.recurrence_percent_threshold??50,'Ex. 50 = un jour travaill\u00e9 sur deux est touch\u00e9.',50,'number','min="0" max="100" step="1"')}
                ${priorityScoreInput('recurrence_percent_min_worked_days','Minimum de jours travaill\u00e9s',score.recurrence_percent_min_worked_days??3,'Evite de tirer une conclusion sur une p\u00e9riode trop courte.',3,'number','min="1" max="366" step="1"')}
                ${priorityScoreInput('recurrence_percent_points','Points ajout\u00e9s',score.recurrence_percent_points??6,'Bonus fixe lorsque le pourcentage est atteint.',6,'number','min="0" max="100" step="0.5"')}
              </div></div>
            </div>
          </details>

          <details class="card priority-config-card">
            <summary><div><span class="priority-step-number">C</span><div><strong>Temps perdu technique</strong><small>Deux paliers. Seul le palier le plus haut atteint est compt\u00e9.</small></div></div><span class="priority-summary-hint">Optionnel</span></summary>
            <div class="priority-config-card-body"><div class="priority-field-grid four">
              ${priorityScoreInput('lost_minutes_low_threshold','Seuil bas (min / jour touch\u00e9)',score.lost_minutes_low_threshold??5,'Premier palier de temps perdu technique.',5,'number','min="0" max="1440" step="0.5"')}
              ${priorityScoreInput('lost_minutes_low_points','Points seuil bas',score.lost_minutes_low_points??3,'Points ajout\u00e9s si le seuil bas est atteint.',3,'number','min="0" max="100" step="0.5"')}
              ${priorityScoreInput('lost_minutes_high_threshold','Seuil haut (min / jour touch\u00e9)',score.lost_minutes_high_threshold??10,'Second palier, plus grave.',10,'number','min="0" max="1440" step="0.5"')}
              ${priorityScoreInput('lost_minutes_high_points','Points seuil haut',score.lost_minutes_high_points??6,'Remplace les points du seuil bas lorsque ce niveau est atteint.',6,'number','min="0" max="100" step="0.5"')}
            </div></div>
          </details>

          <details class="card priority-config-card">
            <summary><div><span class="priority-step-number">D</span><div><strong>Incidents collectifs</strong><small>D\u00e9tecte plusieurs agents touch\u00e9s presque au m\u00eame moment.</small></div></div><span class="priority-summary-hint">Infrastructure</span></summary>
            <div class="priority-config-card-body"><div class="priority-explain-banner"><strong>Conseil Nelyio :</strong> garde les points collectifs \u00e0 0. Le but est de signaler un incident r\u00e9seau / VPN / Herm\u00e8s sans faire monter artificiellement la priorit\u00e9 individuelle.</div><div class="priority-field-grid two">
              ${priorityScoreInput('collective_window_seconds','Fen\u00eatre de d\u00e9tection (secondes)',score.collective_window_seconds??60,'Plus la fen\u00eatre est courte, plus la d\u00e9tection est stricte.',60,'number','min="15" max="600" step="5"')}
              ${priorityScoreInput('collective_min_agents','Agents distincts minimum',score.collective_min_agents??4,'Nombre d\u2019agents n\u00e9cessaires pour consid\u00e9rer l\u2019incident comme collectif.',4,'number','min="2" max="50" step="1"')}
            </div></div>
          </details>

          <details class="card priority-config-card">
            <summary><div><span class="priority-step-number">E</span><div><strong>Fermeture application / pause probable</strong><small>Conservatrice : jamais bas\u00e9e uniquement sur l\u2019heure.</small></div></div><span class="priority-summary-hint">Contexte</span></summary>
            <div class="priority-config-card-body">
              <label class="switch-line priority-large-switch"><input name="probable_closure_enabled" type="checkbox" ${score.probable_closure_enabled===false?'':'checked'}><span class="switch"></span><span><strong>Activer cette d\u00e9tection</strong><small>Il faut aussi une dur\u00e9e compatible, aucune coupure en appel et une activit\u00e9 normale juste avant et apr\u00e8s.</small></span></label>
              <div class="priority-field-grid three">
                ${priorityScoreInput('probable_closure_start_from','D\u00e9but possible \u00e0 partir de',score.probable_closure_start_from||'11:50','D\u00e9but du cr\u00e9neau de recherche.',null,'time','')}
                ${priorityScoreInput('probable_closure_start_to','Jusqu\u2019\u00e0',score.probable_closure_start_to||'13:10','Fin du cr\u00e9neau de recherche.',null,'time','')}
                ${priorityScoreInput('probable_closure_activity_tolerance_minutes','Tol\u00e9rance activit\u00e9 avant / apr\u00e8s (min)',score.probable_closure_activity_tolerance_minutes??10,'Une activit\u00e9 normale doit exister dans cette marge avant et apr\u00e8s.',10,'number','min="0" max="60" step="1"')}
                ${priorityScoreInput('probable_closure_min_minutes','Dur\u00e9e minimum (min)',score.probable_closure_min_minutes??45,'Dur\u00e9e minimale compatible avec une fermeture / pause probable.',45,'number','min="1" max="240" step="1"')}
                ${priorityScoreInput('probable_closure_max_minutes','Dur\u00e9e maximum (min)',score.probable_closure_max_minutes??75,'Dur\u00e9e maximale compatible avec ce contexte.',75,'number','min="1" max="240" step="1"')}
              </div>
            </div>
          </details>

          <div class="priority-save-bar card"><div><strong id="support-score-save-state">Configuration charg\u00e9e</strong><small>Les changements ne sont appliqu\u00e9s qu\u2019apr\u00e8s Enregistrer.</small></div><div><button type="button" class="button ghost" id="priority-score-reload">Annuler les modifications</button><button class="button" type="submit">Enregistrer le moteur de score</button></div><span id="support-score-result" class="form-result"></span></div>
        </form>

        <aside class="priority-help-sidebar">
          <section class="card priority-help-card"><span class="eyebrow">AIDE RAPIDE</span><h3>Comment lire un multiplicateur ?</h3><p><b>4 d\u00e9connexions/jour \u00d7 1</b> donnent 4 points. <b>1 coupure en appel/jour \u00d7 4</b> ajoute 4 points.</p></section>
          <section class="card priority-help-card good"><h3>Valeurs conseill\u00e9es pour Nelyio</h3><dl><div><dt>D\u00e9connexion</dt><dd>1 pt</dd></div><div><dt>En appel</dt><dd>4 pts</dd></div><div><dt>Collectif</dt><dd>0 pt</dd></div><div><dt>Fermeture probable</dt><dd>0 pt</dd></div><div><dt>S\u00e9rie</dt><dd>3 / 30 min</dd></div><div><dt>Collectif</dt><dd>4 agents / 60 s</dd></div></dl>${write?'<button type="button" class="button ghost wide" id="priority-load-recommended">Charger les valeurs conseill\u00e9es</button><small class="priority-button-help">Cela remplit le formulaire seulement. Clique ensuite sur Enregistrer si tu veux les appliquer.</small>':''}</section>
          <section class="card priority-help-card"><h3>Exemple avec tes r\u00e9glages</h3><p>Sur 5 jours travaill\u00e9s : 20 coupures techniques, 5 en appel, 2 s\u00e9ries, 4 jours touch\u00e9s et 12 min/jour touch\u00e9.</p><div class="priority-example-score"><span>Score obtenu</span><strong>${esc(example)}</strong></div><a href="#support-priority" class="priority-help-link" data-open-priority-help>Voir le calcul expliqu\u00e9 \u2192</a></section>
        </aside>
      </div>
    </div>

    <div class="priority-settings-section" data-priority-section="levels" hidden>
      <section class="card panel priority-level-overview"><div class="panel-head"><div><h2>Ordre d\u2019\u00e9valuation</h2><p>Le moteur teste les niveaux du rang le plus grand vers le plus petit. Le premier qui correspond gagne. Si rien ne correspond, le niveau de repli est utilis\u00e9.</p></div><span>${policies.length} niveau(x)</span></div><div class="priority-level-rail">${priorityAdminLevelRail(policies,metrics)}</div></section>
      <details class="card priority-add-level"><summary>+ Ajouter un nouveau niveau de priorit\u00e9</summary><div class="priority-add-level-body">${priorityAdminPolicyCard({priority:'',rank:nextRank,color:'#667085',match_mode:'ANY',enabled:1,is_fallback:0,conditions:[{metric:'technical_score',operator:'>=',value:5}]},metrics,operators,true)}</div></details>
      <div class="priority-guided-level-grid">${policies.slice().sort((a,b)=>(Number(b.rank)||0)-(Number(a.rank)||0)).map(p=>priorityAdminPolicyCard(p,metrics,operators,false)).join('')||'<div class="card empty">Aucun niveau configur\u00e9.</div>'}</div>
    </div>

    <div class="priority-settings-section" data-priority-section="help" hidden>
      <div class="priority-help-page-grid">
        <section class="card priority-help-topic"><span class="priority-help-number">1</span><h3>Le score ne compte pas le volume brut sur toute la p\u00e9riode</h3><p>Les fr\u00e9quences principales sont divis\u00e9es par les <b>jours r\u00e9ellement travaill\u00e9s</b>. Un agent analys\u00e9 sur 10 jours n\u2019est donc pas automatiquement plus grave qu\u2019un agent analys\u00e9 sur 3 jours.</p></section>
        <section class="card priority-help-topic"><span class="priority-help-number">2</span><h3>Une coupure en appel p\u00e8se plus lourd</h3><p>Le multiplicateur <b>En appel</b> est volontairement plus fort, car l\u2019impact technique est direct sur une communication en cours.</p></section>
        <section class="card priority-help-topic"><span class="priority-help-number">3</span><h3>Les incidents collectifs sont s\u00e9par\u00e9s</h3><p>Avec <b>0 point</b>, ils restent visibles comme signaux d\u2019infrastructure sans augmenter la priorit\u00e9 individuelle des agents concern\u00e9s.</p></section>
        <section class="card priority-help-topic"><span class="priority-help-number">4</span><h3>La pause probable n\u2019est jamais d\u00e9duite de l\u2019heure seule</h3><p>Le moteur exige une dur\u00e9e compatible, aucune coupure pendant appel et une activit\u00e9 normale juste avant et apr\u00e8s. L\u2019\u00e9v\u00e9nement reste visible dans les d\u00e9tails.</p></section>
      </div>
      <section class="card panel priority-decision-guide"><div class="panel-head"><div><h2>Que modifier selon le probl\u00e8me observ\u00e9 ?</h2><p>Utilise cette table comme guide. Change un seul param\u00e8tre \u00e0 la fois puis observe le r\u00e9sultat.</p></div></div><div class="table-wrap"><table><thead><tr><th>Ce que tu observes</th><th>Param\u00e8tre \u00e0 regarder</th><th>Action prudente</th></tr></thead><tbody>
        <tr><td>Trop d\u2019agents montent en priorit\u00e9</td><td>Seuils des niveaux de priorit\u00e9</td><td>Augmenter d\u2019abord les seuils de score, plut\u00f4t que baisser tous les poids.</td></tr>
        <tr><td>Les coupures en appel ne remontent pas assez</td><td>Coupure en appel / jour travaill\u00e9</td><td>Augmenter progressivement le multiplicateur, par exemple de 4 \u00e0 5.</td></tr>
        <tr><td>Trop de faux incidents collectifs</td><td>Fen\u00eatre + agents minimum</td><td>R\u00e9duire la fen\u00eatre ou augmenter le nombre minimum d\u2019agents.</td></tr>
        <tr><td>Les petites s\u00e9ries remontent trop vite</td><td>Nombre minimum d\u2019une s\u00e9rie</td><td>Passer de 3 \u00e0 4 coupures, ou r\u00e9duire la fen\u00eatre.</td></tr>
        <tr><td>La r\u00e9currence est trop sensible</td><td>Jours minimum / % jours touch\u00e9s</td><td>Augmenter le seuil de jours ou le pourcentage, pas les deux en m\u00eame temps.</td></tr>
        <tr><td>Une fermeture de midi augmente le score</td><td>Points fermeture / pause probable</td><td>Garder la valeur \u00e0 0 et v\u00e9rifier les crit\u00e8res de d\u00e9tection.</td></tr>
      </tbody></table></div></section>
      <section class="card priority-formula-card"><h2>Formule simplifi\u00e9e</h2><div class="priority-formula"><span>D\u00e9connexions / jour \u00d7 poids</span><b>+</b><span>En appel / jour \u00d7 poids</span><b>+</b><span>S\u00e9ries / jour \u00d7 poids</span><b>+</b><span>Bonus r\u00e9currence</span><b>+</b><span>Bonus temps perdu</span></div><p>Les fermetures probables et incidents collectifs peuvent aussi recevoir des points, mais sont \u00e0 0 par d\u00e9faut dans la configuration Nelyio.</p></section>
    </div>`;

  document.querySelectorAll('.priority-settings-tab').forEach(b=>b.onclick=()=>priorityAdminSetTab(b.dataset.priorityTab));
  document.querySelectorAll('[data-open-priority-help]').forEach(a=>a.onclick=e=>{e.preventDefault();priorityAdminSetTab('help');window.scrollTo({top:0,behavior:'smooth'});});
  priorityAdminSetTab(supportPrioritySettingsTab);

  const scoreForm=document.querySelector('#support-score-form');
  if(scoreForm){
    const state=document.querySelector('#support-score-save-state');
    scoreForm.addEventListener('input',()=>{if(state){state.textContent='Modifications non enregistr\u00e9es';state.classList.add('dirty');}});
    scoreForm.onsubmit=async e=>{
      e.preventDefault();
      const fd=new FormData(scoreForm),body={};
      for(const [k,v] of fd.entries())body[k]=['probable_closure_start_from','probable_closure_start_to'].includes(k)?v:Number(v);
      body.probable_closure_enabled=scoreForm.elements.probable_closure_enabled.checked;
      const out=document.querySelector('#support-score-result');
      try{
        await api('/api/classification/support-score',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
        out.textContent='Configuration enregistr\u00e9e.';
        if(state){state.textContent='Configuration enregistr\u00e9e';state.classList.remove('dirty');}
        setTimeout(()=>out.textContent='',1800);
      }catch(err){out.textContent=err.message;}
    };
  }
  const reload=document.querySelector('#priority-score-reload');
  if(reload)reload.onclick=()=>supportPrioritySettings();
  const recommended=document.querySelector('#priority-load-recommended');
  if(recommended&&scoreForm)recommended.onclick=()=>{
    Object.entries(priorityScoreRecommended).forEach(([k,v])=>{
      const el=scoreForm.elements[k];if(!el)return;
      if(el.type==='checkbox')el.checked=!!v;else el.value=v;
    });
    const state=document.querySelector('#support-score-save-state');if(state){state.textContent='Valeurs conseill\u00e9es charg\u00e9es, non enregistr\u00e9es';state.classList.add('dirty');}
    scoreForm.querySelector('details')?.scrollIntoView({behavior:'smooth',block:'start'});
  };

  document.querySelectorAll('.priority-policy-form').forEach(f=>{
    const editor=f.querySelector('.priority-conditions-editor');
    const list=f.querySelector('.priority-condition-list');
    const fallback=f.elements.is_fallback;
    const active=f.elements.enabled;
    const color=f.elements.color;
    const preview=f.querySelector('.priority-admin-swatch');
    const syncFallback=()=>{if(editor)editor.hidden=fallback.checked;if(fallback.checked){active.checked=true;active.disabled=true;}else active.disabled=false;};
    const syncColor=()=>{if(!preview)return;[...preview.classList].filter(x=>x.startsWith('priority-admin-color-')).forEach(x=>preview.classList.remove(x));preview.classList.add(priorityAdminColorClass(color.value));};
    fallback.onchange=syncFallback;color.oninput=syncColor;syncFallback();syncColor();
    f.addEventListener('click',e=>{
      const add=e.target.closest('.add-priority-condition'),remove=e.target.closest('.remove-priority-condition');
      if(add)list.insertAdjacentHTML('beforeend',priorityAdminConditionRow(metrics,operators,{metric:'technical_score',operator:'>=',value:5}));
      if(remove)remove.closest('.priority-condition-row').remove();
    });
    f.onsubmit=async e=>{
      e.preventDefault();
      const body=priorityAdminPayload(f),out=f.querySelector('.priority-policy-result');
      if(!body.is_fallback&&!body.conditions.length){out.textContent='Ajoute au moins une condition ou choisis ce niveau comme repli.';return;}
      if(!body.is_fallback&&body.conditions.some(c=>!Number.isFinite(c.value))){out.textContent='Chaque condition doit avoir une valeur.';return;}
      try{
        await api('/api/classification/support-priority',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
        out.textContent=f.dataset.new==='1'?'Niveau cr\u00e9\u00e9.':'Niveau enregistr\u00e9.';
        supportPrioritySettingsTab='levels';setTimeout(supportPrioritySettings,450);
      }catch(err){out.textContent=err.message;}
    };
  });
  document.querySelectorAll('.delete-priority-policy').forEach(b=>b.onclick=async()=>{
    const f=b.closest('.priority-policy-form'),name=f.dataset.priority;
    if(!confirm(`Supprimer le niveau \u00ab ${name} \u00bb ?`))return;
    try{await api('/api/classification/support-priority/delete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({priority:name})});supportPrioritySettingsTab='levels';supportPrioritySettings();}catch(err){alert(err.message);}
  });

  if(!write){
    app.insertAdjacentHTML('afterbegin','<div class="flash warn">Mode lecture seule : la configuration des priorit\u00e9s est visible mais non modifiable.</div>');
    app.querySelectorAll('.priority-settings-section input,.priority-settings-section select,.priority-settings-section textarea,.priority-settings-section button').forEach(el=>el.disabled=true);
  }
}
