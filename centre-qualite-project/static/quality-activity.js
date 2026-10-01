let qualityActivityGeneration=0;
const qualityActivityDefaults=()=>({date_from:'',date_to:'',time_from:'',time_to:'',service:'',group:'',search:'',selectedAgent:''});
const qualityActivityState=qualityActivityDefaults();

async function qualityActivityView(){
 const s=qualityActivityState,generation=++qualityActivityGeneration,user=currentUser;
 activate('quality-activity');setHead('Qualité agents','Activité, appels et distribution par files');app.innerHTML='<div class="loading">Chargement…</div>';
 const active=()=>generation===qualityActivityGeneration&&location.hash==='#quality-activity'&&user===currentUser&&canRead('quality');
 try{
  const query=new URLSearchParams();for(const k of ['date_from','date_to','time_from','time_to','service','group','search'])if(s[k])query.set(k,s[k]);
  const d=await api('/api/quality/agent-activity?'+query);if(!active())return;
  for(const k of ['date_from','date_to','time_from','time_to'])s[k]=d[k];
  const duration=v=>{if(v===null||v===undefined)return '—';const n=Math.max(0,Math.round(Number(v)));return Math.floor(n/3600)+'h '+String(Math.floor(n%3600/60)).padStart(2,'0')+'m '+String(n%60).padStart(2,'0')+'s';};
  const compactDuration=v=>{if(v===null||v===undefined)return '—';const n=Math.max(0,Math.round(Number(v)));if(n<60)return n+' s';if(n<3600)return Math.floor(n/60)+'m '+String(n%60).padStart(2,'0')+'s';return Math.floor(n/3600)+'h '+String(Math.floor(n%3600/60)).padStart(2,'0')+'m';};
  const number=v=>v===null||v===undefined?'—':Number(v).toLocaleString('fr-FR');
  const decimal=v=>v===null||v===undefined?'—':Number(v).toLocaleString('fr-FR',{minimumFractionDigits:1,maximumFractionDigits:2});
  const option=(value,label,selected)=>`<option value="${esc(value)}" ${value===selected?'selected':''}>${esc(label)}</option>`;
  const q=d.summary||{};
  const groups=d.groups||[];
  const visibleGroups=groups.filter(x=>!s.service||String(x.service_name||'').toLowerCase()===s.service.toLowerCase());
  const selectedGroup=groups.find(g=>g.id===s.group);
  const rows=d.rows||[];

  app.innerHTML=`<section class="q-page qa-page"><form id="qa-filters" class="q-toolbar"><div class="q-main-filters">
   <label>Du<input name="date_from" type="date" required value="${esc(s.date_from)}"></label><label>Au<input name="date_to" type="date" required value="${esc(s.date_to)}"></label>
   <label>Début<input name="time_from" type="time" required value="${esc(s.time_from)}"></label><label>Fin<input name="time_to" type="time" required value="${esc(s.time_to)}"></label>
   <label>Service<select name="service">${option('','Tous les services',s.service)}${(d.services||[]).map(x=>option(x,x,s.service)).join('')}</select></label>
   <label>Sous-groupe (files)<select name="group">${option('','Tous les sous-groupes',s.group)}${visibleGroups.map(g=>option(g.id,g.name+' · '+number(g.file_count)+' file(s)',s.group)).join('')}</select></label>
   <label>Agent<input type="search" name="search" placeholder="Nom ou identifiant" value="${esc(s.search)}"></label></div>
   <div class="q-actions"><button class="button">Appliquer</button><button class="button ghost" id="qa-reset" type="button">Réinitialiser</button></div></form>
   <div class="q-info"><span><b>${d.available_days} / ${d.total_days}</b> jours d’activité disponibles · Europe/Paris</span><span>Mode calcul : requêtes groupées</span></div>
   ${selectedGroup&&selectedGroup.file_count===0?'<p class="notice">Ce groupe ne possède aucune file configurée. Il ne peut donc pas définir un périmètre Qualité agents fiable.</p>':''}
   ${d.available_days<d.total_days?'<p class="notice">Activités incomplètes sur la période. Les valeurs ne sont calculées que sur les jours disponibles.</p>':''}
   ${!d.calls_compatible?'<p class="notice">Les KPI appels ne couvrent pas tous les jours sélectionnés. Les métriques d’activité restent affichées, mais les KPI appels incomplets sont masqués.</p>':''}
   ${d.integrity?.ok===false?'<p class="notice danger"><strong>Contrôle de cohérence Qualité agents en échec.</strong> Une valeur ou une distribution nécessite une vérification.</p>':''}
   <div class="qo-cards qa-summary">${[
      ['Agents',number(q.agent_count)],
      ['Traités',d.calls_compatible?number(q.handled):'—'],
      ['Jours actifs',number(q.worked_agent_days)],
      ['Moy. appel entrant',compactDuration(q.call_average)],
      ['Travail cumulé',duration(q.work_seconds)],
      ['Durée déconnectée',duration(q.disconnected_seconds)]
    ].map(([label,v])=>`<div class="card"><small>${esc(label)}</small><strong>${v}</strong></div>`).join('')}</div>
   <details class="qo-definitions"><summary>Définitions et précision des données</summary>
     <p><strong>Jours actifs</strong> : +1 dès qu’un agent possède au moins une donnée d’activité de durée positive ou au moins un appel traité ce jour-là. Ce compteur représente uniquement les jours observés avec données, pas le planning contractuel.</p>
     <p><strong>Travail</strong> : présence observée moins les intervalles de pause et coaching. Un libellé Hermes non reconnu ne peut donc plus faire tomber un agent actif à 0 s de travail.</p>
     <p><strong>Moy. appel entrant</strong> : moyenne de <code>CallDuration</code> dans Stats.INBOUND pour les appels attribués à l’agent. Stats.AGENT sert uniquement de repli si cette durée n’est pas disponible.</p>
     <p><strong>Traités / Répondus / ASA</strong> : calculés depuis Stats.INBOUND. Les groupes sont déterminés par les <strong>files configurées</strong> et les affectations agents ACTIVE ; les campagnes ne sont plus l’ancre du groupe.</p>
     <p><strong>Distribution par files</strong> : Stats.INBOUND contient la campagne mais pas toujours l’identifiant de file. Nelyio attribue une file uniquement lorsque le lien campagne → file est univoque. Les cas ambigus sont signalés et ne sont jamais répartis artificiellement.</p>
   </details>
   <div class="table-wrap"><table class="qa-table"><thead><tr><th>Agent</th><th>Traités</th><th>Jours actifs</th><th>Moy. appel entrant</th><th>ASA</th><th>Travail</th><th>Déconnecté</th><th>Pauses</th><th>Détail</th></tr></thead><tbody>${rows.map(r=>`<tr data-agent="${esc(r.agent)}"><td><strong>${esc(r.name)}</strong><small>${esc(r.agent)}</small>${r.invalid_durations?'<small class="qa-warn">Durée source invalide détectée</small>':''}</td><td>${number(r.handled)}</td><td>${number(r.worked_days)}</td><td>${compactDuration(r.call_average)}${r.call_average_count?'<small>'+number(r.call_average_count)+' activité(s)</small>':''}</td><td>${compactDuration(r.asa_seconds)}</td><td>${duration(r.work_seconds)}</td><td>${duration(r.disconnected_seconds)}${r.disconnected_incomplete?'<small title="Déconnexion finale sans retour observé">incomplet</small>':''}</td><td>${number(r.pause_count)}<small>${duration(r.pause_seconds)}</small></td><td><button type="button" class="button ghost small qa-detail-btn" data-agent="${esc(r.agent)}">Voir</button></td></tr>`).join('')||'<tr><td colspan="9">Aucune activité pour cette sélection.</td></tr>'}</tbody></table></div>
   <section id="qa-detail-panel" class="qa-detail-panel" ${s.selectedAgent?'':'hidden'}></section>
  </section>`;

  qualityMakeSortable(app.querySelector('.qa-table'),'quality-agents');

  const renderDetailContent=r=>{
    const panel=document.getElementById('qa-detail-panel');
    s.selectedAgent=r.agent;
    const dist=r.distribution||[];
    const mappingLabel=m=>m==='exact'?'File identifiée':m==='ambiguous'?'Ambiguë':'Non rattachée';
    const mappingNote=item=>{
      if(item.mapping==='exact')return 'Lien campagne → file unique';
      if(item.mapping==='ambiguous')return 'Candidates : '+(item.candidate_files||[]).map(x=>(x.line_name||('File '+x.line_id))+' ['+x.line_id+']').join(', ');
      return 'Aucune file du catalogue ne correspond à cette campagne';
    };
    panel.hidden=false;
    panel.innerHTML=`<div class="qa-detail-head"><div><small>Détail agent</small><h3>${esc(r.name)} <span>· ${esc(r.agent)}</span></h3></div><button type="button" class="button ghost small" id="qa-detail-close">Fermer</button></div>
      <div class="qa-detail-metrics">${[
        ['Traités',number(r.handled)],['Répondus SIMPLIFY2',number(r.answered)],['ASA',compactDuration(r.asa_seconds)],['Jours actifs',number(r.worked_days)],
        ['Présence observée',duration(r.presence_seconds)],['Travail',duration(r.work_seconds)],['Déconnecté',duration(r.disconnected_seconds)],
        ['Pauses',number(r.pause_count)+' · '+duration(r.pause_seconds)],['Coaching',number(r.coaching_count)+' · '+duration(r.coaching_seconds)],
        ['Moy. appel entrant',compactDuration(r.call_average)],['Occurrences appel entrant',number(r.call_average_count)],['Moy. mise en attente',compactDuration(r.hold_average)]
      ].map(([k,v])=>`<div><small>${esc(k)}</small><strong>${v}</strong></div>`).join('')}</div>
      <div class="qa-distribution-head"><div><h4>Distribution des appels traités par files</h4><p>${number(r.distribution_exact)} exacts · ${number(r.distribution_ambiguous)} ambigus · ${number(r.distribution_unmapped)} non rattachés</p></div></div>
      <div class="table-wrap"><table class="qa-distribution-table"><thead><tr><th>File</th><th>Campagne(s)</th><th>Traités</th><th>Précision</th></tr></thead><tbody>${dist.map(item=>{
        const camps=item.campaigns?.length?item.campaigns.map(c=>`${esc(c.campaign_name||c.campaign)} <small>· ${esc(c.campaign)}</small>`).join('<br>'):`${esc(item.campaign_name||item.campaign||'—')}<small>${item.campaign?' · '+esc(item.campaign):''}</small>`;
        return `<tr><td>${esc(item.file_name||'—')}${item.file_id?'<small>· '+esc(item.file_id)+'</small>':''}</td><td>${camps}</td><td>${number(item.handled)}</td><td><span class="qa-map ${esc(item.mapping)}">${esc(mappingLabel(item.mapping))}</span><small>${esc(mappingNote(item))}</small></td></tr>`;
      }).join('')||'<tr><td colspan="4">Aucun appel traité à distribuer sur cette sélection.</td></tr>'}</tbody></table></div>
      ${r.unresolved_subactions?'<p class="q-note">Certaines sous-actions Stats.AGENT ne sont pas identifiables avec certitude ; elles ne sont pas intégrées à la moyenne de mise en attente.</p>':''}`;
    document.getElementById('qa-detail-close').onclick=()=>{s.selectedAgent='';panel.hidden=true;panel.innerHTML='';};
    panel.scrollIntoView({behavior:'smooth',block:'nearest'});
  };
  const renderDetail=async agentId=>{
    const panel=document.getElementById('qa-detail-panel');
    const r=rows.find(x=>String(x.agent)===String(agentId));
    if(!r){panel.hidden=true;panel.innerHTML='';s.selectedAgent='';return;}
    s.selectedAgent=r.agent;
    if(!r.distribution_loaded){
      panel.hidden=false;panel.innerHTML='<div class="loading">Chargement du détail agent…</div>';
      try{
        const query=new URLSearchParams();for(const k of ['date_from','date_to','time_from','time_to','service','group'])if(s[k])query.set(k,s[k]);
        query.set('agent',r.agent);query.set('include_distribution','1');
        const detail=await api('/api/quality/agent-activity?'+query);if(!active())return;
        const full=(detail.rows||[])[0];if(!full)throw new Error('Détail agent indisponible pour cette période.');
        Object.assign(r,full);
      }catch(e){panel.innerHTML=flash(e.message,'error');return;}
    }
    renderDetailContent(r);
  };
  document.querySelectorAll('.qa-detail-btn').forEach(b=>b.onclick=()=>renderDetail(b.dataset.agent));
  if(s.selectedAgent)renderDetail(s.selectedAgent);
  document.getElementById('qa-filters').onsubmit=e=>{e.preventDefault();for(const [k,v] of new FormData(e.currentTarget))s[k]=v;s.selectedAgent='';qualityActivityView();};
  document.getElementById('qa-filters').elements.service.onchange=e=>{s.service=String(e.target.value||'');s.group='';s.selectedAgent='';qualityActivityView();};
  document.getElementById('qa-reset').onclick=()=>{Object.assign(s,qualityActivityDefaults());qualityActivityView();};
 }catch(e){if(active()){app.innerHTML=flash(e.message,'error')+'<button class="button" id="qa-retry">Réinitialiser</button>';document.getElementById('qa-retry').onclick=()=>{Object.assign(s,qualityActivityDefaults());qualityActivityView();};}}
}
