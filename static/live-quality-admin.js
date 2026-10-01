// Signalisation Qualité Live - Configuration Interface
// With correct metrics from system documentation

let liveQualityAdminState = {
  config: null,
  selectedPreset: null
};

// Actual metrics from live_quality.py
const AVAILABLE_METRICS = {
  "agents_connected": { label: "Agents connectés", unit: "", type: "count" },
  "agents_available": { label: "Agents disponibles", unit: "", type: "count" },
  "agents_in_call": { label: "Agents en appel (mise en attente incluse)", unit: "", type: "count" },
  "agents_on_hold": { label: "Agents en mise en attente explicite", unit: "", type: "count" },
  "agents_wrap": { label: "Agents en post-appel", unit: "", type: "count" },
  "agents_pause": { label: "Agents en pause", unit: "", type: "count" },
  "agents_pause_normal": { label: "Agents en pause normale", unit: "", type: "count" },
  "agents_pause_lunch": { label: "Agents en pause déjeuner", unit: "", type: "count" },
  "agents_pause_coaching": { label: "Agents en coaching", unit: "", type: "count" },
  "agents_pause_general": { label: "Agents en General Break", unit: "", type: "count" },
  "agents_inactive_context": { label: "Agents en contexte inactif", unit: "", type: "count" },
  "agents_offline": { label: "Agents déconnectés", unit: "", type: "count" },
  "available_percent": { label: "% agents disponibles", unit: "%", type: "percentage" },
  "wrap_percent": { label: "% agents en post-appel", unit: "%", type: "percentage" },
  "pause_percent": { label: "% agents en pause", unit: "%", type: "percentage" },
  "hold_percent": { label: "% agents en mise en attente", unit: "%", type: "percentage" },
  "inactive_context_percent": { label: "% agents en contexte inactif", unit: "%", type: "percentage" },
  "max_wrap_seconds": { label: "Post-appel le plus long", unit: "s", type: "duration" },
  "max_pause_seconds": { label: "Pause la plus longue", unit: "s", type: "duration" },
  "max_pause_normal_seconds": { label: "Pause normale la plus longue", unit: "s", type: "duration" },
  "max_pause_lunch_seconds": { label: "Pause déjeuner la plus longue", unit: "s", type: "duration" },
  "max_pause_coaching_seconds": { label: "Coaching le plus long", unit: "s", type: "duration" },
  "max_pause_general_seconds": { label: "General Break le plus long", unit: "s", type: "duration" },
  "max_hold_seconds": { label: "Mise en attente la plus longue", unit: "s", type: "duration" },
  "max_inactive_context_seconds": { label: "Contexte inactif le plus long", unit: "s", type: "duration" },
  "max_offline_seconds": { label: "Déconnexion la plus longue", unit: "s", type: "duration" },
  "earliest_hold_start_seconds": { label: "Mise en attente précoce (< 10s)", unit: "s", type: "duration" },
};

// Pre-built rule presets - examples users can customize
const RULE_PRESETS = [
  { key: "post_appel_surveillance_10s", name: "Post-appel · surveillance 10 s", metric: "max_wrap_seconds", operator: ">=", value: 10, level_key: "SURVEILLANCE", min_duration: 0, cooldown: 30 },
  { key: "post_appel_alerte_15s", name: "Post-appel · alerte 15 s", metric: "max_wrap_seconds", operator: ">=", value: 15, level_key: "DEGRADE", min_duration: 0, cooldown: 30 },
  { key: "post_appel_critique_25s", name: "Post-appel · critique > 25 s", metric: "max_wrap_seconds", operator: ">", value: 25, level_key: "CRITIQUE", min_duration: 0, cooldown: 30 },
  { key: "pause_longue", name: "Pause longue", metric: "max_pause_seconds", operator: ">=", value: 600, level_key: "SURVEILLANCE", min_duration: 60, cooldown: 300 },
  { key: "pause_dejeuner_1h", name: "Pause déjeuner > 1 h", metric: "max_pause_lunch_seconds", operator: ">", value: 3600, level_key: "DEGRADE", min_duration: 0, cooldown: 300 },
  { key: "hold_long", name: "Mise en attente longue", metric: "max_hold_seconds", operator: ">=", value: 30, level_key: "DEGRADE", min_duration: 0, cooldown: 120 },
  { key: "deconnexion_prolongee", name: "Déconnexion > 10 min", metric: "max_offline_seconds", operator: ">", value: 600, level_key: "DEGRADE", min_duration: 120, cooldown: 300 },
  { key: "contexte_inactif_long", name: "Contexte inactif long", metric: "max_inactive_context_seconds", operator: ">=", value: 300, level_key: "SURVEILLANCE", min_duration: 0, cooldown: 180 },
];

const DEFAULT_LEVELS = [
  { level_key: "CRITIQUE", label: "CRITIQUE", rank: 400, color: "#B42318", enabled: 1 },
  { level_key: "DEGRADE", label: "DÉGRADÉ", rank: 300, color: "#B54708", enabled: 1 },
  { level_key: "SURVEILLANCE", label: "À SURVEILLER", rank: 200, color: "#A56A00", enabled: 1 },
  { level_key: "NORMAL", label: "NORMAL", rank: 100, color: "#24634A", enabled: 1 },
];

function liveQualityAdminView() {
  activate('live-quality-admin');
  setHead('Signalisation Qualité Live', 'Configurez les niveaux de signalisation et les règles');

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
  const levels = config.levels || DEFAULT_LEVELS;
  const rules = config.rules || [];

  app.innerHTML = `
    <style>
      .lq-admin { display: flex; flex-direction: column; gap: 2rem; padding: 1.5rem; }
      .lq-section { background: white; border: 1px solid #e5e7eb; border-radius: 8px; padding: 1.5rem; }
      .lq-section h2 { margin: 0 0 1rem 0; font-size: 1.25rem; font-weight: 600; }
      .lq-section h3 { margin: 1.5rem 0 1rem 0; font-size: 1.1rem; font-weight: 600; color: #374151; }
      .lq-intro { background: #f0f9ff; border-left: 4px solid #3b82f6; padding: 1rem; border-radius: 4px; }
      .lq-intro p { margin: 0.5rem 0; font-size: 0.95rem; color: #1e40af; }

      .lq-levels-grid { display: grid; gap: 1rem; }
      .lq-level-card { display: flex; align-items: center; gap: 1rem; padding: 1rem; background: #f9fafb; border-radius: 6px; border: 1px solid #e5e7eb; }
      .lq-level-swatch { width: 50px; height: 50px; border-radius: 6px; flex-shrink: 0; border: 2px solid #e5e7eb; }
      .lq-level-info { flex: 1; }
      .lq-level-info strong { display: block; font-size: 1rem; }
      .lq-level-info small { display: block; color: #6b7280; font-size: 0.875rem; }
      .lq-level-info code { background: #f3f4f6; padding: 0.125rem 0.5rem; border-radius: 2px; font-size: 0.8rem; }

      .lq-rules-list { display: grid; gap: 1rem; }
      .lq-rule-card { display: grid; grid-template-columns: 1fr auto; gap: 1rem; padding: 1.25rem; background: #f9fafb; border-radius: 6px; border: 1px solid #e5e7eb; align-items: start; }
      .lq-rule-info strong { display: block; font-size: 1rem; margin-bottom: 0.5rem; }
      .lq-rule-info small { display: block; color: #6b7280; font-size: 0.875rem; line-height: 1.4; }
      .lq-rule-conditions { font-family: monospace; font-size: 0.8rem; background: white; padding: 0.75rem; border-radius: 4px; margin-top: 0.5rem; color: #374151; border: 1px solid #e5e7eb; }
      .lq-rule-actions { display: flex; gap: 0.5rem; flex-direction: column; }

      .lq-preset-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 1rem; margin-top: 1rem; }
      .lq-preset-card { padding: 1rem; background: #f0f9ff; border: 1px solid #bfdbfe; border-radius: 6px; cursor: pointer; transition: all 0.2s; }
      .lq-preset-card:hover { background: #e0f2fe; border-color: #7dd3fc; }
      .lq-preset-card strong { display: block; margin-bottom: 0.5rem; color: #0369a1; }
      .lq-preset-card small { display: block; color: #0c4a6e; font-size: 0.8rem; line-height: 1.3; }

      .lq-form-group { display: grid; gap: 1rem; }
      label { display: flex; flex-direction: column; gap: 0.5rem; }
      label span { font-weight: 500; font-size: 0.95rem; color: #1f2937; }
      input, select { padding: 0.75rem; border: 1px solid #d1d5db; border-radius: 4px; font-size: 0.95rem; font-family: inherit; }
      input:focus, select:focus { outline: none; border-color: #3b82f6; box-shadow: 0 0 0 3px #eff6ff; }
      input[type="color"] { height: 44px; cursor: pointer; }

      .button { padding: 0.75rem 1.25rem; background: #3b82f6; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 0.95rem; font-weight: 500; transition: background 0.2s; }
      .button:hover { background: #2563eb; }
      .button.ghost { background: transparent; color: #6b7280; border: 1px solid #d1d5db; }
      .button.ghost:hover { background: #f9fafb; }
      .button.small { padding: 0.5rem 0.75rem; font-size: 0.85rem; }
      .button.danger { background: #ef4444; }
      .button.danger:hover { background: #dc2626; }

      .flash { padding: 1rem; border-radius: 4px; margin-bottom: 1rem; }
      .flash.error { background: #fee2e2; color: #991b1b; border: 1px solid #fca5a5; }
      .flash.success { background: #dcfce7; color: #166534; border: 1px solid #86efac; }

      .lq-status { display: inline-flex; align-items: center; gap: 0.5rem; padding: 0.25rem 0.75rem; border-radius: 9999px; font-size: 0.8rem; font-weight: 600; }
      .lq-status.on { background: #dcfce7; color: #166534; }
      .lq-status.off { background: #fee2e2; color: #991b1b; }

      .form-row { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
      .form-row-3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 1rem; }
      .form-row-full { grid-column: 1 / -1; }

      details > summary { cursor: pointer; font-weight: 600; padding: 1rem; user-select: none; display: flex; align-items: center; gap: 0.5rem; }
      details > summary:hover { background: #f9fafb; }
      details[open] > summary { background: #f3f4f6; border-bottom: 1px solid #e5e7eb; }
      details > summary::before { content: "▶"; display: inline-block; width: 1rem; text-align: center; }
      details[open] > summary::before { content: "▼"; }
      details > * + * { padding-top: 1rem; }

      .lq-divider { height: 1px; background: #e5e7eb; margin: 1.5rem 0; }
    </style>

    <div class="lq-admin">
      ${canWrite ? '' : '<div class="flash error">Mode lecture seule - vous ne pouvez pas modifier</div>'}

      <div class="lq-intro">
        <p><strong>Comment ça marche :</strong> Configurez les niveaux de couleur, puis créez des règles qui surveillent les métriques en temps réel. Les règles signalent automatiquement les anomalies avec la couleur appropriée.</p>
      </div>

      <!-- NIVEAUX -->
      <div class="lq-section">
        <h2>1. Niveaux de signalisation (${levels.length})</h2>
        <p style="color: #6b7280; margin-bottom: 1rem;">Définissez les étapes de dégradation avec des couleurs.</p>

        <div class="lq-levels-grid">
          ${levels.map(level => `
            <div class="lq-level-card">
              <div class="lq-level-swatch" style="background-color: ${level.color || '#667085'};"></div>
              <div class="lq-level-info">
                <strong>${esc(level.label)}</strong>
                <small><code>${esc(level.level_key)}</code> · Rang ${level.rank}</small>
              </div>
              ${canWrite ? `<button class="button ghost small lq-delete-level" data-key="${esc(level.level_key)}">Supprimer</button>` : ''}
            </div>
          `).join('')}
        </div>

        ${canWrite ? `
          <div class="lq-divider"></div>
          <details class="lq-form-section">
            <summary>+ Ajouter un niveau personnalisé</summary>
            <form class="lq-new-level lq-form-group">
              <div class="form-row">
                <label><span>Identifiant (ex: CRITIQUE)</span><input name="level_key" required maxlength="40" placeholder="CRITIQUE"></label>
                <label><span>Nom affichage</span><input name="label" required maxlength="80" placeholder="CRITIQUE"></label>
              </div>
              <div class="form-row">
                <label><span>Rang (100-400)</span><input name="rank" type="number" value="200" min="0" max="10000"></label>
                <label><span>Couleur</span><input name="color" type="color" value="#A56A00"></label>
              </div>
              <button type="submit" class="button">Créer niveau</button>
              <span class="lq-result" style="margin-left: 1rem;"></span>
            </form>
          </details>
        ` : ''}
      </div>

      <!-- RÈGLES -->
      <div class="lq-section">
        <h2>2. Règles de signalisation (${rules.length})</h2>
        <p style="color: #6b7280; margin-bottom: 1rem;">Créez des règles qui surveillent les métriques. Chaque condition déclenche un incident et colore l'agent/campagne.</p>

        ${rules.length ? `
          <div class="lq-rules-list">
            ${rules.map(rule => {
              const conditions = rule.conditions || [];
              const level = levels.find(l => l.level_key === rule.level_key);
              return `
                <div class="lq-rule-card">
                  <div class="lq-rule-info">
                    <strong>${esc(rule.name)}</strong>
                    <small>📌 ${rule.scope_type} · ${conditions.length} condition(s)</small>
                    <div class="lq-rule-conditions">
                      ${conditions.map(c => {
                        const metric = AVAILABLE_METRICS[c.metric];
                        return metric ? \`\${esc(metric.label)} \${esc(c.operator)} \${c.value}\${metric.unit ? ' ' + metric.unit : ''}\` : \`Unknown metric: \${c.metric}\`;
                      }).join(' <strong>ET</strong> ')}
                    </div>
                    <small style="margin-top: 0.5rem;">
                      Niveau: <strong style="color: ${level?.color || '#999'}">${esc(level?.label || 'Inconnu')}</strong>
                    </small>
                  </div>
                  <div class="lq-rule-actions">
                    <span class="lq-status ${rule.enabled ? 'on' : 'off'}">
                      ${rule.enabled ? '✓ Actif' : '✗ Inactif'}
                    </span>
                    ${canWrite ? `<button class="button ghost small lq-delete-rule" data-id="${rule.id}">Supprimer</button>` : ''}
                  </div>
                </div>
              `;
            }).join('')}
          </div>
        ` : '<p style="color: #9ca3af; padding: 1rem; background: #f9fafb; border-radius: 4px;">Aucune règle. Commencez par un modèle.</p>'}

        ${canWrite ? `
          <div class="lq-divider"></div>

          <h3>Créer une règle à partir d'un modèle</h3>
          <p style="color: #6b7280; font-size: 0.95rem; margin-bottom: 1rem;">Cliquez sur un modèle pour commencer, puis ajustez les paramètres.</p>

          <div class="lq-preset-grid">
            ${RULE_PRESETS.map(preset => `
              <div class="lq-preset-card" onclick="selectPreset('${preset.key}')">
                <strong>${esc(preset.name)}</strong>
                <small>
                  Métrique: ${AVAILABLE_METRICS[preset.metric]?.label || preset.metric}<br>
                  Seuil: ${preset.value}${AVAILABLE_METRICS[preset.metric]?.unit || ''}<br>
                  Niveau: ${preset.level_key}
                </small>
              </div>
            `).join('')}
          </div>

          <div class="lq-divider"></div>
          <details class="lq-form-section">
            <summary>+ Créer une règle personnalisée</summary>
            <form class="lq-new-rule lq-form-group">
              <label><span>Nom de la règle</span><input name="name" required maxlength="80" placeholder="ex: Post-appel > 25s"></label>

              <div class="form-row">
                <label><span>Type de cible</span><select name="scope_type" required>
                  <option value="AGENT">Agent</option>
                  <option value="GROUP">Groupe</option>
                  <option value="CAMPAIGN">Campagne</option>
                  <option value="QUEUE">File</option>
                  <option value="SERVICE">Service</option>
                  <option value="GLOBAL">Global</option>
                </select></label>
                <label><span>Niveau signalisation</span><select name="level_key" required>
                  ${levels.map(l => `<option value="${esc(l.level_key)}">${esc(l.label)}</option>`).join('')}
                </select></label>
              </div>

              <h3 style="margin: 1rem 0 0.5rem 0; font-size: 1rem;">Conditions (ET logique)</h3>
              <div class="lq-conditions-list"></div>
              <button type="button" class="button ghost lq-add-condition">+ Ajouter une condition</button>

              <div class="form-row" style="margin-top: 1rem;">
                <label><span>Durée minimale (s)</span><input name="min_duration" type="number" value="0" min="0"></label>
                <label><span>Cooldown (s)</span><input name="cooldown" type="number" value="300" min="0"></label>
              </div>

              <label style="margin-top: 1rem;">
                <div style="display: flex; align-items: center; gap: 0.5rem;">
                  <input type="checkbox" name="enabled" checked>
                  <span>Règle active</span>
                </div>
              </label>

              <button type="submit" class="button" style="margin-top: 1rem;">Créer règle</button>
              <span class="lq-result" style="margin-left: 1rem;"></span>
            </form>
          </details>
        ` : ''}
      </div>
    </div>
  `;

  setupEventListeners(canWrite, levels);
}

function setupEventListeners(canWrite, levels) {
  if (!canWrite) {
    app.querySelectorAll('input,select,button').forEach(el => el.disabled = true);
    return;
  }

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
          level_key: form.elements.level_key.value.trim().toUpperCase(),
          label: form.elements.label.value.trim(),
          rank: Number(form.elements.rank.value || 100),
          color: form.elements.color.value,
          enabled: 1
        })
      });
      out.textContent = '✓ Créé';
      out.style.color = '#16a34a';
      setTimeout(liveQualityAdminView, 500);
    } catch (err) {
      out.textContent = '✗ ' + err.message;
      out.style.color = '#dc2626';
    }
  });

  // Supprimer niveau
  app.querySelectorAll('.lq-delete-level').forEach(btn => {
    btn.addEventListener('click', async () => {
      if (!confirm('Supprimer ce niveau ?')) return;
      try {
        await api('/api/live/quality/level-delete', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ level_key: btn.dataset.key })
        });
        liveQualityAdminView();
      } catch (err) {
        alert('Erreur: ' + err.message);
      }
    });
  });

  // Supprimer règle
  app.querySelectorAll('.lq-delete-rule').forEach(btn => {
    btn.addEventListener('click', async () => {
      if (!confirm('Supprimer cette règle ?')) return;
      try {
        await api('/api/live/quality/rule-delete', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ id: Number(btn.dataset.id) })
        });
        liveQualityAdminView();
      } catch (err) {
        alert('Erreur: ' + err.message);
      }
    });
  });

  // Ajouter condition
  app.querySelector('.lq-add-condition')?.addEventListener('click', () => {
    const container = app.querySelector('.lq-conditions-list');
    const idx = container.children.length;
    const div = document.createElement('div');
    div.style.cssText = 'display: grid; grid-template-columns: 1fr auto 1fr auto; gap: 0.5rem; margin-bottom: 0.5rem; align-items: center;';
    div.innerHTML = `
      <select class="metric-${idx}" style="padding: 0.5rem; border: 1px solid #d1d5db; border-radius: 4px;">
        <option value="">-- Métrique --</option>
        ${Object.entries(AVAILABLE_METRICS).map(([k, v]) => `<option value="${k}">${esc(v.label)}</option>`).join('')}
      </select>
      <select class="operator-${idx}" style="padding: 0.5rem; border: 1px solid #d1d5db; border-radius: 4px; width: 80px;">
        <option value=">">&gt;</option>
        <option value=">=">&gt;=</option>
        <option value="<">&lt;</option>
        <option value="<=">&lt;=</option>
        <option value="==">=</option>
        <option value="!=">≠</option>
      </select>
      <input type="number" class="value-${idx}" placeholder="Valeur" step="any" style="padding: 0.5rem; border: 1px solid #d1d5db; border-radius: 4px;">
      <button type="button" class="button ghost small" onclick="this.parentElement.remove()">✕</button>
    `;
    container.appendChild(div);
  });

  // Créer règle
  app.querySelector('.lq-new-rule')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const form = e.target;
    const out = form.querySelector('.lq-result');

    try {
      const conditions = [];
      form.querySelector('.lq-conditions-list').querySelectorAll('select, input[type="number"]').forEach((el, idx) => {
        if (el.classList.contains('metric-' + Math.floor(idx / 3))) {
          // Process every 3rd element (metric, operator, value group)
        }
      });

      // Parse conditions from form
      const condList = form.querySelector('.lq-conditions-list');
      for (let i = 0; i < condList.children.length; i++) {
        const row = condList.children[i];
        const metric = row.querySelector('select:nth-child(1)')?.value;
        const operator = row.querySelector('select:nth-child(2)')?.value;
        const value = row.querySelector('input')?.value;
        if (metric && operator && value) {
          conditions.push({
            metric: metric,
            operator: operator,
            value: Number(value)
          });
        }
      }

      if (!conditions.length) {
        throw new Error('Ajoutez au moins une condition');
      }

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
          conditions: conditions,
          min_duration_seconds: Number(form.elements.min_duration.value || 0),
          recovery_seconds: 30,
          cooldown_seconds: Number(form.elements.cooldown.value || 300),
          min_sample_size: 0,
          allow_partial: 0
        })
      });
      out.textContent = '✓ Créée';
      out.style.color = '#16a34a';
      setTimeout(liveQualityAdminView, 500);
    } catch (err) {
      out.textContent = '✗ ' + err.message;
      out.style.color = '#dc2626';
    }
  });
}

function selectPreset(presetKey) {
  const preset = RULE_PRESETS.find(p => p.key === presetKey);
  if (!preset) return;

  const form = app.querySelector('.lq-new-rule');
  form.elements.name.value = preset.name;
  form.elements.level_key.value = preset.level_key;
  form.elements.min_duration.value = preset.min_duration || 0;
  form.elements.cooldown.value = preset.cooldown || 300;

  // Clear existing conditions
  const condList = form.querySelector('.lq-conditions-list');
  condList.innerHTML = '';

  // Add preset condition
  const div = document.createElement('div');
  div.style.cssText = 'display: grid; grid-template-columns: 1fr auto 1fr auto; gap: 0.5rem; margin-bottom: 0.5rem; align-items: center;';
  div.innerHTML = `
    <select class="metric-0" style="padding: 0.5rem; border: 1px solid #d1d5db; border-radius: 4px;">
      <option value="${preset.metric}">${AVAILABLE_METRICS[preset.metric]?.label || preset.metric}</option>
    </select>
    <select class="operator-0" style="padding: 0.5rem; border: 1px solid #d1d5db; border-radius: 4px; width: 80px;">
      <option value="${preset.operator}">${preset.operator}</option>
    </select>
    <input type="number" class="value-0" value="${preset.value}" step="any" style="padding: 0.5rem; border: 1px solid #d1d5db; border-radius: 4px;">
    <button type="button" class="button ghost small" onclick="this.parentElement.remove()">✕</button>
  `;
  condList.appendChild(div);

  form.scrollIntoView({ behavior: 'smooth' });
}
