/* RC21 - Observabilite production durcie, lecture seule. */
(()=>{
  let refreshTimer=0, loading=false;
  const E=window.esc||((v)=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])));
  const fmtMs=v=>v==null?'—':`${Number(v).toLocaleString('fr-FR',{maximumFractionDigits:1})} ms`;
  const fmtS=v=>v==null?'—':`${Number(v).toLocaleString('fr-FR',{maximumFractionDigits:3})} s`;
  const yesNo=(v,yes='Oui',no='Non')=>v?yes:no;
  const statusClass=s=>({OK:'good',A_SURVEILLER:'warn',DEGRADE:'bad',GO:'good',INCOMPLET:'warn',BLOQUE:'bad',NON_EXECUTEE:'neutral',A_INVESTIGUER:'warn',AUCUN_HOTSPOT_JOURNALISE:'good',AUCUN_SIGNAL_CIBLE:'good',DONNEES_INSUFFISANTES:'neutral'}[String(s||'').toUpperCase()]||'neutral');
  const serviceLabel=s=>({web:'Web',live:'Live',analytics:'Analytics',import:'Import'}[s]||s||'—');
  const slowTable=(title,data,label,threshold)=>{
    const rows=(data?.top_24h||[]);
    return `<section class="card panel ph-panel"><div class="panel-head"><div><h2>${E(title)}</h2><p>Journal technique agrégé à partir de ${fmtS(threshold)}, sans query string ni donnée patient.</p></div><span class="ph-count">${Number(data?.last_hour||0)} / 1 h</span></div>
      <div class="ph-slow-summary"><span>24 h <b>${Number(data?.last_24h||0)}</b></span><span>Maximum <b>${fmtS(data?.max_24h_seconds||0)}</b></span></div>
      ${rows.length?`<div class="table-wrap"><table class="ph-table"><thead><tr><th>${E(label)}</th><th>Occurrences 24 h</th><th>Moyenne</th><th>P95</th><th>Max</th></tr></thead><tbody>${rows.map(r=>`<tr><td><code>${E(r.key)}</code></td><td>${Number(r.count||0)}</td><td>${fmtS(r.avg_seconds)}</td><td>${fmtS(r.p95_seconds)}</td><td>${fmtS(r.max_seconds)}</td></tr>`).join('')}</tbody></table></div>`:'<p class="q-note">Aucune entrée lente dans la fenêtre disponible.</p>'}</section>`;
  };
  const performanceAnalysis=(analysis)=>{
    const findings=analysis?.findings||[], evidence=analysis?.evidence||{};
    const label={A_INVESTIGUER:'À investiguer',AUCUN_HOTSPOT_JOURNALISE:'Aucun hotspot journalisé',AUCUN_SIGNAL_CIBLE:'Aucun signal ciblé',DONNEES_INSUFFISANTES:'Données insuffisantes'}[analysis?.status]||analysis?.status||'Inconnu';
    return `<section class="card panel ph-panel ph-analysis"><div class="panel-head"><div><h2>Analyse ciblée des performances</h2><p>Corrélation explicable des journaux Web, Analytics et du test de charge. Aucune optimisation n’est appliquée automatiquement.</p></div><span class="ph-state ${statusClass(analysis?.status)}">${E(label)}</span></div>
      <div class="ph-analysis-coverage"><span>Web 24 h <b>${Number(evidence.http_slow_24h||0)}</b></span><span>Analytics 24 h <b>${Number(evidence.analytics_slow_24h||0)}</b></span><span>Charge prolongée <b>${evidence.soak_available?'disponible':'absente'}</b></span></div>
      ${findings.length?`<div class="ph-findings">${findings.map((f,i)=>`<article class="ph-finding ${String(f.attention||'').toLowerCase()}"><div class="ph-finding-head"><span>${i+1}</span><div><strong>${E(f.title||f.code||'Constat')}</strong><code>${E(f.scope||'—')}</code></div><em>${E(f.attention==='ELEVEE'?'Attention élevée':'À vérifier')}</em></div><p>${E(f.interpretation||'')}</p>${(f.evidence||[]).length?`<ul>${f.evidence.map(x=>`<li>${E(x)}</li>`).join('')}</ul>`:''}<div class="ph-next"><b>Prochaine vérification</b><span>${E(f.next_step||'—')}</span></div></article>`).join('')}</div>`:'<p class="q-note">Aucun constat ciblé avec les preuves actuellement disponibles. L’absence d’entrée lente ne prouve pas une latence nulle.</p>'}
      <p class="q-note">Rapport rejouable : <code>ANALYSER_PERFORMANCE_PRODUCTION.bat</code> → <code>logs\performance_analysis.md</code>.</p>
    </section>`;
  };
  function render(d){
    const overall=d.overall||{}, services=d.services||{}, pg=d.postgresql||{}, live=d.live||{}, sessions=d.sessions||{}, acc=d.acceptance||{}, soak=d.soak_test||{}, imports=d.imports||{}, thresholds=d.performance_thresholds||{}, analysis=d.performance_analysis||{};
    const rows=(services.services||[]);
    const reasons=(overall.reasons||[]).map(x=>({services:'Services requis non sains',postgresql:'PostgreSQL indisponible',live_stale:'Hermes Live actif mais périmé',http_slow:'Requêtes Web lentes répétées',analytics_slow:'Calculs Analytics lents répétés'}[x]||x));
    app.innerHTML=`
      <section class="ph-hero card panel ${statusClass(overall.status)}">
        <div><span class="ph-kicker">État technique actuel</span><h2>${E(String(overall.status||'INCONNU').replace('_',' '))}</h2><p>${reasons.length?E(reasons.join(' · ')):'Aucun signal technique agrégé détecté par ce tableau.'}</p></div>
        <div class="ph-actions"><button type="button" class="button ghost" id="ph-refresh">Actualiser</button><span>RC ${E(d.version||'—')}</span></div>
      </section>
      <section class="ph-cards">
        <article class="card ph-card ${services.all_healthy?'good':'bad'}"><span>Services</span><strong>${services.all_healthy?'Sains':'À vérifier'}</strong><small>Web · Live · Analytics</small></article>
        <article class="card ph-card ${pg.ok?'good':'bad'}"><span>PostgreSQL</span><strong>${pg.ok?'Disponible':'Indisponible'}</strong><small>${E(pg.engine||'—')} · ${fmtMs(pg.latency_ms)}</small></article>
        <article class="card ph-card ${live.active?(live.fresh?'good':'warn'):'neutral'}"><span>Hermes Live</span><strong>${live.active?(live.fresh?'Frais':'Périmé'):'Inactif'}</strong><small>${E(live.last_response_text||'Aucune réponse récente')}</small></article>
        <article class="card ph-card neutral"><span>Sessions Nelyio</span><strong>${sessions.valid_sessions==null?'—':Number(sessions.valid_sessions)}</strong><small>${sessions.seen_last_10m==null?'indisponible':Number(sessions.seen_last_10m)+' vue(s) dans les 10 min'}</small></article>
        <article class="card ph-card ${acc.status==='GO'?'good':acc.available?'warn':'neutral'}"><span>Dernière recette</span><strong>${E(acc.status||'NON EXECUTÉE')}</strong><small>${acc.generated_at?E(acc.generated_at):'RECETTE_PRODUCTION.bat non détectée'}</small></article>
        <article class="card ph-card ${soak.status==='PASS'?'good':soak.status==='WARN'?'warn':soak.status==='FAIL'?'bad':'neutral'}"><span>Charge prolongée</span><strong>${E(soak.status||'NON EXÉCUTÉ')}</strong><small>${soak.available?`${Number(soak.virtual_users||0)} utilisateurs · P95 ${fmtS(soak.p95_s)}`:'TEST_CHARGE_PROLONGEE.bat non détecté'}</small></article>
        <article class="card ph-card neutral"><span>Import</span><strong>${E(imports.manual_importer?'Séparé du Web':imports.mode||'—')}</strong><small>${imports.available?`${imports.active_count==null?'activité non mesurée':Number(imports.active_count)+' actif'} · ${Number(imports.pending_count||0)} en attente`:'indisponible'}</small></article>
      </section>
      <section class="grid2 ph-grid">
        <section class="card panel ph-panel"><div class="panel-head"><div><h2>Services locaux</h2><p>Heartbeats isolés dans Nelyio_Services.db.</p></div></div>
          <div class="ph-service-list">${rows.length?rows.map(r=>`<div class="ph-service-row"><span class="status-dot ${r.healthy?'on':'off'}"></span><div><strong>${E(serviceLabel(r.service))}</strong><small>PID ${Number(r.pid||0)} · build ${E(r.build||'—')} · âge ${Number(r.age_seconds||0).toLocaleString('fr-FR')} s</small></div><span class="ph-state ${r.healthy?'good':'bad'}">${r.healthy?'SAIN':E(r.state||'INCONNU')}</span></div>`).join(''):'<p class="q-note">Aucun heartbeat disponible.</p>'}</div>
        </section>
        <section class="card panel ph-panel"><div class="panel-head"><div><h2>Collecte Live</h2><p>État du spool central, sans inventer de navigateur connecté.</p></div></div>
          <dl class="ph-kv"><div><dt>Session active</dt><dd>${yesNo(live.active)}</dd></div><div><dt>Donnée fraîche</dt><dd>${yesNo(live.fresh)}</dd></div><div><dt>Connexion source</dt><dd>${E(live.connection_state||'—')}</dd></div><div><dt>Événements en attente</dt><dd>${Number(live.pending||0)}</dd></div><div><dt>Publication retardée</dt><dd>${yesNo(live.publication_delayed)}</dd></div><div><dt>Journée</dt><dd>${E(live.day||'—')}</dd></div></dl>
        </section>
      </section>
      <section class="grid2 ph-grid">${slowTable('Requêtes Web lentes',d.performance?.http,'Endpoint',thresholds.http_log_seconds)}${slowTable('Calculs Analytics lents',d.performance?.analytics,'Type de calcul',thresholds.analytics_log_seconds)}</section>
      ${performanceAnalysis(analysis)}
      <section class="card panel ph-panel"><div class="panel-head"><div><h2>Seuils de surveillance</h2><p>Valeurs de diagnostic configurables par variables d’environnement ; elles ne modifient aucun KPI métier.</p></div></div>
        <dl class="ph-kv"><div><dt>Journal Web lent</dt><dd>${fmtS(thresholds.http_log_seconds)}</dd></div><div><dt>Journal Analytics lent</dt><dd>${fmtS(thresholds.analytics_log_seconds)}</dd></div><div><dt>Surveillance</dt><dd>${Number(thresholds.warn_events_per_hour||0)} événement(s) / heure</dd></div><div><dt>Critique</dt><dd>${Number(thresholds.critical_events_per_hour||0)} événement(s) / heure ou ${fmtS(thresholds.critical_seconds)}</dd></div></dl>
      </section>
      <section class="card panel ph-panel"><div class="panel-head"><div><h2>Recette et limites de mesure</h2><p>Le tableau complète la recette de production ; il ne remplace pas la preuve depuis un poste LAN.</p></div></div>
        <div class="ph-recipe"><div><span>Statut</span><strong class="ph-state ${statusClass(acc.status)}">${E(acc.status||'NON EXECUTÉE')}</strong></div><div><span>Échecs</span><strong>${Number(acc.failures||0)}</strong></div><div><span>Avertissements</span><strong>${Number(acc.warnings||0)}</strong></div><div><span>Ignorés</span><strong>${Number(acc.skipped||0)}</strong></div></div>
        <ul class="ph-limitations">${(d.limitations||[]).map(x=>`<li>${E(x)}</li>`).join('')}</ul>
        <p class="q-note">Confidentialité : lecture seule, aucun identifiant métier, aucune query string, aucun secret.</p>
      </section>`;
    document.getElementById('ph-refresh')?.addEventListener('click',()=>load(true));
  }
  async function load(manual=false){
    const hostHash='#production-health';
    if(location.hash!==hostHash)return;
    if(loading)return;
    loading=true;
    if(refreshTimer){clearTimeout(refreshTimer);refreshTimer=0;}
    if(manual){const btn=document.getElementById('ph-refresh');if(btn){btn.disabled=true;btn.textContent='Actualisation…';}}
    try{render(await api('/api/production/observability'));}
    catch(err){if(location.hash===hostHash)app.innerHTML=`<div class="flash error">${E(err.message)}</div><button class="button" id="ph-retry">Réessayer</button>`;document.getElementById('ph-retry')?.addEventListener('click',()=>load(true));return;}
    finally{loading=false;}
    if(location.hash===hostHash)refreshTimer=setTimeout(()=>load(false),10000);
  }
  window.productionHealthView=async function(){
    if(!canRead('config')){redirectAllowed();return;}
    activate('production-health');setHead('Santé de production','Web, Live, Analytics, PostgreSQL et performances agrégées, en lecture seule.');
    app.innerHTML='<div class="loading">Lecture de la santé de production…</div>';
    await load(false);
  };
})();
