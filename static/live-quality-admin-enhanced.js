// Signalisation Qualité Live - Interface SIMPLE et FONCTIONNELLE
// Créer: Niveaux de signalisation + Règles simples avec conditions

let liveQualityAdminState = {
  config: null
};

function liveQualityAdminView() {
  activate('live-quality-admin');
  setHead('Signalisation Qualité Live', 'Configuration des niveaux et règles de signalisation');

  app.innerHTML = '<div class="loading">Chargement…</div>';

  api('/api/live/quality/config').then(config => {
    liveQualityAdminState.config = config;
    renderAdmin(config);
  }).catch(err => {
    app.innerHTML = `<div class="flash error">${esc(err.message)}</div>`;
  });
}

function renderAdmin(config) {
  const canWrite = canWriteInterface('live_quality_admin');
  const levels = config.levels || [];
  const rules = config.rules || [];
  const metrics = config.metrics || [];
  const operators = config.operators || [];

  // Présets de métriques
  const commonMetrics = [
    { key: 'avg_post_call_duration', label: 'Post-appel (durée moyenne)', unit: 's' },
    { key: 'pct_waiting_duration', label: '% attente / appel', unit: '%' },
    { key: 'context_inactive', label: 'Contexte inactive', unit: 'nombre' },
    { key: 'agents_available', label: 'Agents disponibles', unit: 'nombre' },
    { key: 'agents_connected', label: 'Agents connectés', unit: 'nombre' }
  ];

  const getMetricLabel = (key) => {
    const m = metrics.find(x => x.key === key) || commonMetrics.find(x => x.key === key);
    return m ? m.label : key;
  };

  const getMetricUnit = (key) => {
    const m = metrics.find(x => x.key === key) || commonMetrics.find(x => x.key === key);
    return m ? (m.unit === 's' ? 'secondes' : m.unit === '%' ? '%' : 'nombre') : 'valeur';
  };

  app.innerHTML = `
    <style>
      .lq-page { display: flex; flex-direction: column; gap: 2rem; padding: 1rem; }
      .lq-card { background: white; border: 1px solid #e5e7eb; border-radius: 8px; padding: 1.5rem; }
      .lq-card h2 { margin: 0 0 1rem 0; font-size: 1.25rem; }
      .lq-card h3 { margin: 0 0 1rem 0; font-size: 1.125rem; }
      .lq-grid { display: grid; gap: 1rem; }
      .lq-grid-2 { grid-template-columns: 1fr 1fr; }
      .lq-grid-3 { grid-template-columns: 1fr 1fr 1fr; }
      label { display: flex; flex-direction: column; gap: 0.25rem; }
      label span { font-weight: 500; font-size: 0.875rem; }
      input, select { padding: 0.5rem; border: 1px solid #d1d5db; border-radius: 4px; font-size: 0.875rem; }
      input:focus, select:focus { outline: none; border-color: #3b82f6; box-shadow: 0 0 0 2px #dbeafe; }
      .button { padding: 0.5rem 1rem; background: #3b82f6; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 0.875rem; font-weight: 500; }
      .button:hover { background: #2563eb; }
      .button.ghost { background: transparent; color: #6b7280; border: 1px solid #d1d5db; }
      .button.ghost:hover { background: #f9fafb; }
      .button.small { padding: 0.25rem 0.5rem; font-size: 0.75rem; }
      .flash { padding: 1rem; border-radius: 4px; margin-bottom: 1rem; }
      .flash.error { background: #fee2e2; color: #991b1b; border: 1px solid #fca5a5; }
      .flash.warn { background: #fef3c7; color: #92400e; border: 1px solid #fcd34d; }
      .lq-level-item { display: flex; align-items: center; gap: 1rem; padding: 1rem; background: #f9fafb; border-radius: 4px; }
      .lq-level-swatch { width: 40px; height: 40px; border-radius: 4px; border: 2px solid #e5e7eb; flex-shrink: 0; }
      .lq-level-info { flex: 1; }
      .lq-level-info strong { display: block; }
      .lq-level-info small { color: #6b7280; }
      .lq-rule-item { display: grid; grid-template-columns: 1fr auto; gap: 1rem; padding: 1rem; background: #f9fafb; border-radius: 4px; align-items: center; }
      .lq-rule-info { display: grid; gap: 0.25rem; }
      .lq-rule-info strong { display: block; }
      .lq-rule-info small { color: #6b7280; }
      .lq-status { padding: 0.25rem 0.75rem; border-radius: 9999px; font-size: 0.75rem; font-weight: 600; }
      .lq-status.on { background: #dcfce7; color: #166534; }
      .lq-status.off { background: #fee2e2; color: #991b1b; }
      .lq-actions { display: flex; gap: 0.5rem; flex-wrap: wrap; }
      .lq-form-group { display: grid; gap: 1rem; }
      .form-row { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
      .form-row-3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 1rem; }
      .check-group { display: flex; align-items: center; gap: 0.5rem; }
      .check-group input { margin: 0; }
      .muted { color: #9ca3af; }
      details > summary { cursor: pointer; font-weight: 500; padding: 1rem; user-select: none; }
      details > summary:hover { background: #f9fafb; }
      details[open] > summary { background: #f3f4f6; }
    </style>

    <div class="lq-page">
      ${canWrite ? '' : '<div class="flash warn">Mode lecture seule</div>'}

      <!-- INTRO -->
      <div class="lq-card">
        <h2>Signalisation Qualité Live</h2>
        <p>Créez des niveaux de signalisation (couleurs) et des règles simples pour surveiller les métriques en temps réel.</p>
      </div>

      <!-- NIVEAUX -->
      <div class="lq-card">
        <h3>Niveaux de signalisation (${levels.length})</h3>
        ${levels.length ? `
          <div class="lq-grid">
            ${levels.map(level => {
              const cls = 'lq-color-' + (level.color || '#667085').replace('#', '').toLowerCase();
              return `
                <div class="lq-level-item">
                  <div class="lq-level-swatch ${cls}" style="--lq-color: ${level.color || '#667085'};"></div>
                  <div class="lq-level-info">
                    <strong>${esc(level.label || level.level_key)}</strong>
                    <small>Rang ${Number(level.rank || 0)}</small>
                  </div>
                  ${canWrite ? `
                    <button class="button ghost small lq-delete-level" data-key="${esc(level.level_key)}">Supprimer</button>
                  ` : ''}
                </div>
              `;
            }).join('')}
          </div>
        ` : '<p class="muted">Aucun niveau. Créez-en un.</p>'}

        ${canWrite ? `
          <details class="lq-card" style="margin-top: 1rem; padding: 1rem;">
            <summary>+ Ajouter un niveau</summary>
            <form class="lq-new-level" style="margin-top: 1rem;">
              <div class="lq-grid lq-grid-2">
                <label><span>Identifiant</span><input name="level_key" required maxlength="40" placeholder="ex: WARNING"></label>
                <label><span>Nom</span><input name="label" required maxlength="80" placeholder="ex: Attention"></label>
                <label><span>Rang</span><input name="rank" type="number" value="100"></label>
                <label><span>Couleur</span><input name="color" type="color" value="#fbbf24"></label>
              </div>
              <button type="submit" class="button" style="margin-top: 1rem;">Créer niveau</button>
              <span class="lq-result" style="margin-left: 1rem;"></span>
            </form>
          </details>
        ` : ''}
      </div>

      <!-- RÈGLES -->
      <div class="lq-card">
        <h3>Règles de signalisation (${rules.length})</h3>
        ${rules.length ? `
          <div class="lq-grid">
            ${rules.map(rule => {
              const metric = metrics.find(m => m.key === rule.conditions?.[0]?.metric) || commonMetrics.find(m => m.key === rule.conditions?.[0]?.metric);
              const cond = rule.conditions?.[0];
              return `
                <div class="lq-rule-item">
                  <div class="lq-rule-info">
                    <strong>${esc(rule.name)}</strong>
                    <small>${metric ? esc(metric.label) : 'Métrique'} ${cond ? esc(cond.operator) + ' ' + cond.value : ''}</small>
                    <small>${rule.scope_type}</small>
                  </div>
                  <div class="lq-actions">
                    <span class="lq-status ${rule.enabled !== 0 ? 'on' : 'off'}">${rule.enabled !== 0 ? '✓ Actif' : '✗ Inactif'}</span>
                    ${canWrite ? `
                      <button class="button ghost small lq-delete-rule" data-id="${rule.id}">Supprimer</button>
                    ` : ''}
                  </div>
                </div>
              `;
            }).join('')}
          </div>
        ` : '<p class="muted">Aucune règle. Créez-en une.</p>'}

        ${canWrite ? `
          <details class="lq-card" style="margin-top: 1rem; padding: 1rem;">
            <summary>+ Ajouter une règle</summary>
            <form class="lq-new-rule" style="margin-top: 1rem;">
              <div class="lq-form-group">
                <div class="form-row">
                  <label><span>Nom de la règle</span><input name="name" required maxlength="80" placeholder="ex: post-appel > 25s"></label>
                  <label><span>Métrique</span><select name="metric" required>
                    <option value="">-- Choisir --</option>
                    ${commonMetrics.map(m => `<option value="${esc(m.key)}">${esc(m.label)}</option>`).join('')}
                    ${metrics.filter(m => !commonMetrics.find(cm => cm.key === m.key)).map(m => `<option value="${esc(m.key)}">${esc(m.label)}</option>`).join('')}
                  </select></label>
                </div>

                <div class="form-row-3">
                  <label><span>Opérateur</span><select name="operator" required>
                    ${(operators || ['<', '<=', '>', '>=', '==', '!=']).map(op => `<option value="${esc(op)}">${esc(op)}</option>`).join('')}
                  </select></label>
                  <label><span>Valeur</span><input name="value" type="number" step="any" required placeholder="0"></label>
                  <label><span>Niveau</span><select name="level_key" required>
                    <option value="">-- Choisir --</option>
                    ${levels.map(l => `<option value="${esc(l.level_key)}">${esc(l.label)}</option>`).join('')}
                  </select></label>
                </div>

                <div class="form-row">
                  <label><span>Type de cible</span><select name="scope_type" required>
                    <option value="CAMPAIGN">Campagne</option>
                    <option value="GROUP">Groupe</option>
                    <option value="AGENT">Agent</option>
                    <option value="QUEUE">File</option>
                    <option value="SERVICE">Service</option>
                    <option value="GLOBAL">Global</option>
                  </select></label>
                  <div class="check-group"><input type="checkbox" name="enabled" checked><span>Actif</span></div>
                </div>
              </div>

              <button type="submit" class="button" style="margin-top: 1rem;">Créer règle</button>
              <span class="lq-result" style="margin-left: 1rem;"></span>
            </form>
          </details>
        ` : ''}
      </div>
    </div>
  `;

  // ÉVÉNEMENTS
  if (canWrite) {
    // Créer niveau
    app.querySelector('.lq-new-level')?.addEventListener('submit', async (e) => {
      e.preventDefault();
      const form = e.target;
      const out = form.querySelector('.lq-result');
      try {
        await api('/api/live/quality/level', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            level_key: form.elements.level_key.value.trim(),
            label: form.elements.label.value.trim(),
            rank: Number(form.elements.rank.value || 100),
            color: form.elements.color.value,
            enabled: 1
          })
        });
        out.textContent = '✓ Créé';
        setTimeout(liveQualityAdminView, 500);
      } catch (err) {
        out.textContent = '✗ ' + err.message;
      }
    });

    // Supprimer niveau
    app.querySelectorAll('.lq-delete-level').forEach(btn => {
      btn.addEventListener('click', async () => {
        const key = btn.dataset.key;
        if (!confirm(`Supprimer « ${key} » ?`)) return;
        try {
          await api('/api/live/quality/level-delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ level_key: key })
          });
          liveQualityAdminView();
        } catch (err) {
          alert(err.message);
        }
      });
    });

    // Créer règle
    app.querySelector('.lq-new-rule')?.addEventListener('submit', async (e) => {
      e.preventDefault();
      const form = e.target;
      const out = form.querySelector('.lq-result');
      try {
        await api('/api/live/quality/rule', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            name: form.elements.name.value.trim(),
            enabled: form.elements.enabled.checked ? 1 : 0,
            scope_type: form.elements.scope_type.value,
            target_keys: [],
            level_key: form.elements.level_key.value,
            match_mode: 'ALL',
            conditions: [{
              metric: form.elements.metric.value,
              operator: form.elements.operator.value,
              value: Number(form.elements.value.value)
            }],
            min_duration_seconds: 0,
            recovery_seconds: 30,
            cooldown_seconds: 300,
            min_sample_size: 0,
            allow_partial: 0
          })
        });
        out.textContent = '✓ Créée';
        setTimeout(liveQualityAdminView, 500);
      } catch (err) {
        out.textContent = '✗ ' + err.message;
      }
    });

    // Supprimer règle
    app.querySelectorAll('.lq-delete-rule').forEach(btn => {
      btn.addEventListener('click', async () => {
        const id = btn.dataset.id;
        if (!confirm('Supprimer cette règle ?')) return;
        try {
          await api('/api/live/quality/rule-delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id: Number(id) })
          });
          liveQualityAdminView();
        } catch (err) {
          alert(err.message);
        }
      });
    });
  } else {
    app.querySelectorAll('input,select,button').forEach(el => el.disabled = true);
  }
}
