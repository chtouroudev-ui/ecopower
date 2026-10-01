let distributionGeneration=0;
const distributionDefaults=()=>({date_from:'',date_to:'',time_from:'',time_to:'',work_hours:'1',service:'',group:'',agent:'',campaign:''});
const distributionState=distributionDefaults();
async function qualityDistributionsView(){
  const ticket=++distributionGeneration,user=currentUser,s=distributionState;
  activate('quality-distributions');setHead('Distributions','Appels entrants et périmètres métier par heure');
  app.innerHTML='<div class="loading">Chargement…</div>';
  const active=()=>ticket===distributionGeneration&&currentUser===user&&location.hash==='#quality-distributions'&&canRead('quality');
  const query=new URLSearchParams(Object.entries(s).filter(([,v])=>v!==''));
  try{
    const d=await api('/api/quality/distributions?'+query);if(!active())return;
    Object.assign(s,{date_from:d.date_from,date_to:d.date_to,time_from:d.time_from,time_to:d.time_to});
    const option=(v,label,selected)=>`<option value="${esc(v)}" ${v===selected?'selected':''}>${esc(label)}</option>`;
    const num=v=>v===null||v===undefined?'—':Number(v).toLocaleString('fr-FR');
    const pct=v=>v===null||v===undefined?'—':Number(v).toLocaleString('fr-FR',{maximumFractionDigits:1})+' %';
    const callMetrics=[['received','Reçus'],['treated','Traités'],['abandoned','Abandonnés']];
    const workforceMetrics=[['active_agents','Agents ACTIVE'],['pause_agents','En pause'],['expected_agents','Attendus'],['worked_agents','A travaillé'],['not_worked_agents','N’a pas travaillé']];
    const max=Math.max(1,...d.hourly.flatMap(r=>callMetrics.map(([k])=>Number(r[k])||0)));
    const cell=(v,key)=>`<td><span>${num(v)}</span><progress class="distribution-track distribution-${key}" max="${max}" value="${Math.max(0,Number(v)||0)}" aria-label="${num(v)} ${key}"></progress></td>`;
    const group=d.groups.find(g=>g.id===s.group);
    const visibleGroups=d.groups.filter(x=>!s.service||String(x.service_name||'').toLowerCase()===s.service.toLowerCase());
    const wf=d.workforce_summary||{};
    const wfUnit=d.workforce_unit||'agents';
    const wfStatus=d.workforce_status==='reliable'
      ?`Population métier calculable · ${d.workforce_available_days}/${d.total_days} jour(s) Stats.AGENT · unité : ${esc(wfUnit)}.`
      :d.workforce_status==='partial'
        ?`Population métier partiellement calculable · ${d.workforce_available_days}/${d.total_days} jour(s) Stats.AGENT. Les jours manquants ne sont jamais transformés en absence.`
        :'Population métier non calculable : affectations ACTIVE ou couverture Stats.AGENT insuffisantes. Les absences ne sont pas déduites.';
    app.innerHTML=`<section class="q-page"><form id="distribution-filters" class="q-toolbar"><div class="q-main-filters">
      <label>Du<input name="date_from" type="date" required value="${esc(s.date_from)}"></label><label>Au<input name="date_to" type="date" required value="${esc(s.date_to)}"></label>
      <label>Service<select name="service">${option('','Tous les services',s.service)}${(d.services||[]).map(x=>option(x,x,s.service)).join('')}</select></label>
      <label>Sous-groupe<select name="group">${option('','Tous les sous-groupes',s.group)}${visibleGroups.map(g=>option(g.id,g.name,s.group)).join('')}</select></label>
      <label>Campagne<select name="campaign">${option('','Toutes les campagnes',s.campaign)}${d.campaign_choices.map(c=>option(c.campaign,(c.campaign_name||c.campaign)+' · '+c.campaign,s.campaign)).join('')}${s.campaign&&!d.campaign_choices.some(c=>c.campaign===s.campaign)?option(s.campaign,s.campaign+' · hors sélection',s.campaign):''}</select></label>
      <label>Agent<select name="agent">${option('','Tous les agents',s.agent)}${d.agent_choices.map(a=>option(a.agent,a.name+(a.agent==='__unassigned__'?'':' · '+a.agent),s.agent)).join('')}${s.agent&&!d.agent_choices.some(a=>a.agent===s.agent)?option(s.agent,s.agent+' · hors sélection',s.agent):''}</select></label>
      <label>Début<input name="time_from" type="time" value="${esc(s.time_from)}"></label><label>Fin<input name="time_to" type="time" value="${esc(s.time_to)}"></label>
      </div><div class="q-actions"><button class="button">Appliquer</button><button type="button" class="button ghost" id="distribution-day">Journée entière</button><button type="button" class="button ghost" id="distribution-reset">Réinitialiser</button></div></form>
      <p role="status">Cumul par heure · ${d.available_days} / ${d.total_days} jours Stats.INBOUND disponibles · Europe/Paris</p>
      ${d.available_days<d.total_days?'<p class="notice">Période appels incomplète : seuls les jours avec Stats.INBOUND disponible sont comptés.</p>':''}
      <p class="notice ${d.workforce_status==='not_calculable'?'danger':''}"><strong>Périmètre métier :</strong> ${wfStatus}</p>
      ${group&&group.file_count>0&&group.member_count===0?'<p class="notice danger"><strong>Aucun agent ACTIVE détecté sur les files de ce groupe.</strong> Vérifiez/importez la configuration Agents.csv.</p>':''}
      ${group&&group.campaign_count===0?'<p class="notice">Aucune campagne rattachée à ce groupe sur cette période.</p>':''}
      ${group?.ambiguous_links?'<p class="notice">Certains noms de campagne sont ambigus. Vérifiez leur rattachement par identifiant dans Groupes et équipes.</p>':''}
      ${s.agent?'<p class="notice">Filtre agent : uniquement les lignes qui lui sont attribuées dans l’export. Les abandons sans agent ne sont pas attribués à un agent.</p>':''}
      <div class="qo-cards distribution-cards">${callMetrics.map(([k,label])=>`<div class="card"><small>${label}</small><strong>${num(d.total[k])}</strong></div>`).join('')}<div class="card"><small>QoS</small><strong>${pct(d.total.qos)}</strong></div></div>
      <div class="qo-cards distribution-cards">${workforceMetrics.map(([k,label])=>`<div class="card"><small>${label}${k==='active_agents'?' · uniques':' · '+esc(wfUnit)}</small><strong>${num(wf[k])}</strong></div>`).join('')}</div>
      <div class="table-wrap"><table id="distribution-table" class="distribution-table"><thead><tr><th>Heure</th>${callMetrics.map(([,label])=>`<th>${label}</th>`).join('')}<th>QoS</th>${workforceMetrics.map(([,label])=>`<th>${label} · ${esc(wfUnit)}</th>`).join('')}<th>Détail</th></tr></thead><tbody>${d.hourly.map(r=>`<tr><td>${esc(r.label)}</td>${callMetrics.map(([k])=>cell(r[k],k)).join('')}<td>${pct(r.qos)}</td>${workforceMetrics.map(([k])=>`<td>${num(r[k])}</td>`).join('')}<td><button type="button" class="button ghost small distribution-detail" data-hour="${Number(r.hour)}" ${d.workforce_status==='not_calculable'?'disabled':''}>Voir</button></td></tr>`).join('')}</tbody></table></div>
      <div id="distribution-workforce-detail"></div>
      <details class="qo-definitions"><summary>Lecture des données</summary><p>Reçus = lignes Stats.INBOUND ; Traités = AgentId &gt; 0 ; Abandonnés = IsCallAbandonned. QoS = Traités / (Reçus - Clôturés - Raccrochés avant file d’attente) × 100 ; si le dénominateur est inférieur ou égal à 0, la valeur affichée est « — ». Heure de la ligne Stats.INBOUND, cumulée sur les dates sélectionnées. Début inclus, fin exclue.</p><p><strong>Agents ACTIVE</strong> = agents configurés ACTIVE sur au moins une file du périmètre. <strong>Attendus</strong> = cette population uniquement pour les jours où Stats.AGENT permet le calcul. <strong>A travaillé</strong> exige une preuve positive Stats.AGENT normalisée (work, inbound, manual ou hold). Offline, pause, coaching ou unknown seuls ne prouvent jamais le travail. Un agent ayant travaillé puis déconnecté reste « A travaillé ». <strong>N’a pas travaillé</strong> n’est déduit que lorsque population et couverture sont fiables ; sinon la valeur est « — / Non calculable ».</p><p><strong>En pause</strong> = COUNT DISTINCT des agents dont un intervalle Pause chevauche la tranche. Deux pauses du même agent dans la même tranche comptent 1. Une pause traversant deux tranches compte dans les deux. Les intervalles sont coupés aux limites de la journée Europe/Paris.</p><p>Sur une période de plusieurs jours, les colonnes Attendus / En pause / A travaillé / N’a pas travaillé sont des <strong>agent-jours cumulés</strong>. Le nombre d’agents ACTIVE affiché en carte reste la population unique configurée. Un agent peut appartenir à plusieurs groupes via plusieurs files ACTIVE : les groupes ne sont donc pas additionnables.</p></details></section>`;
    qualityMakeSortable(document.getElementById('distribution-table'),'distributions-hourly');
    const form=document.getElementById('distribution-filters');
    const read=()=>{for(const [k,v] of new FormData(form))s[k]=v;};
    form.onsubmit=e=>{e.preventDefault();read();qualityDistributionsView();};
    form.elements.service.onchange=()=>{read();s.group='';s.campaign='';s.agent='';qualityDistributionsView();};
    form.elements.group.onchange=()=>{read();s.campaign='';s.agent='';qualityDistributionsView();};
    form.elements.campaign.onchange=()=>{read();s.agent='';qualityDistributionsView();};
    document.getElementById('distribution-day').onclick=()=>{read();Object.assign(s,{time_from:'',time_to:'',work_hours:'0'});qualityDistributionsView();};
    document.getElementById('distribution-reset').onclick=()=>{Object.assign(s,distributionDefaults());qualityDistributionsView();};
    app.querySelectorAll('.distribution-detail').forEach(btn=>btn.onclick=async()=>{
      const target=document.getElementById('distribution-workforce-detail');if(!target)return;
      target.innerHTML='<div class="loading">Chargement du détail…</div>';
      const detailQuery=new URLSearchParams(Object.entries(s).filter(([,v])=>v!==''));detailQuery.set('detail_hour',btn.dataset.hour);
      try{
        const detail=await api('/api/quality/distributions?'+detailQuery);if(!active())return;
        const rows=(detail.workforce_detail||[]).map(day=>`<details class="card panel"><summary>${esc(day.day)} · ${String(day.hour).padStart(2,'0')}:00 · ${day.agents.length} agent(s)</summary><div class="table-wrap"><table><thead><tr><th>Agent</th><th>ID</th><th>A travaillé</th><th>En pause</th><th>N’a pas travaillé</th></tr></thead><tbody>${day.agents.map(a=>`<tr><td>${esc(a.name)}</td><td>${esc(a.agent)}</td><td>${a.worked?'Oui':'Non'}</td><td>${a.pause?'Oui':'Non'}</td><td>${a.not_worked?'Oui':'Non'}</td></tr>`).join('')}</tbody></table></div></details>`).join('');
        target.innerHTML=`<section class="card panel"><div class="panel-head"><div><h2>Détail périmètre · ${String(btn.dataset.hour).padStart(2,'0')}:00</h2><p>Preuve positive de travail et pause distincte par jour.</p></div><button type="button" class="button ghost small" id="distribution-detail-close">Fermer</button></div>${rows||'<p class="empty">Aucun détail calculable.</p>'}</section>`;
        const close=document.getElementById('distribution-detail-close');if(close)close.onclick=()=>{target.innerHTML='';};
      }catch(e){target.innerHTML=flash(e.message,'error');}
    });
  }catch(e){if(active()){app.innerHTML=flash(e.message,'error')+'<button id="distribution-retry" class="button">Réinitialiser les filtres</button>';document.getElementById('distribution-retry').onclick=()=>{Object.assign(s,distributionDefaults());qualityDistributionsView();};}}
}
