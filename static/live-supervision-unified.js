// Supervision Qualité Live - Vue unifiée simple et minimaliste
// Montre: Configuration + État LIVE + Incidents + Stats en un seul écran

let liveSupervisionState = {
  config: null,
  incidents: [],
  stats: null,
  lastRefresh: 0,
  autoRefreshInterval: null
};

function renderSupervisionLive() {
  activate('live-supervision-unified');
  setHead('Supervision Qualité Live', 'Configuration des règles + État en temps réel + Incidents + Statistiques');

  app.innerHTML = `
    <div class="lsu-container">
      <div class="lsu-loading">Chargement...</div>
    </div>
  `;

  Promise.all([
    api('/api/live/quality/config').catch(() => ({})),
    api('/api/live/incidents?limit=500').catch(() => ({ incidents: [] })),
    api('/api/live/incident-stats').catch(() => ({}))
  ]).then(([config, incidentData, stats]) => {
    liveSupervisionState.config = config;
    liveSupervisionState.incidents = incidentData.incidents || [];
    liveSupervisionState.stats = stats;
    renderDashboard();
  }).catch(err => {
    app.innerHTML = `<div class="flash error">${esc(err.message)}</div>`;
  });
}

function getColorClass(levelKey) {
  const config = liveSupervisionState.config || {};
  const level = (config.levels || []).find(l => l.level_key === levelKey);
  if (!level) return 'lsu-status-normal';
  const color = level.color || '#22c55e';
  const rank = Number(level.rank || 0);
  if (rank <= 0) return 'lsu-status-normal';
  if (rank <= 10) return 'lsu-status-warning';
  return 'lsu-status-critical';
}

function getStatusEmoji(levelKey) {
  const config = liveSupervisionState.config || {};
  const level = (config.levels || []).find(l => l.level_key === levelKey);
  if (!level) return '🟢';
  const rank = Number(level.rank || 0);
  if (rank <= 0) return '🟢';
  if (rank <= 10) return '🟡';
  return '🔴';
}

function renderDashboard() {
  const config = liveSupervisionState.config || {};
  const rules = config.rules || [];
  const levels = config.levels || [];
  const incidents = liveSupervisionState.incidents || [];
  const stats = liveSupervisionState.stats || {};

  // Grouper incidents actifs par règle
  const activeIncidents = incidents.filter(i => !['RETABLI', 'CLOTURE'].includes(i.status));
  const incidentsByRule = {};
  activeIncidents.forEach(inc => {
    const key = inc.rule_name || 'Manuel';
    if (!incidentsByRule[key]) incidentsByRule[key] = [];
    incidentsByRule[key].push(inc);
  });

  const rulesStats = (stats.rows || []).slice(0, 20) || [];

  app.innerHTML = `
    <div class="lsu-page">

      <!-- HEADER -->
      <section class="lsu-header">
        <div>
          <h1>Supervision Qualité Live</h1>
          <p>Configuration + État en temps réel + Incidents + Statistiques</p>
        </div>
        <div class="lsu-header-actions">
          <a href="#live-quality-admin" class="button">⚙️ Configurer</a>
          <button class="button ghost" onclick="location.reload()">🔄 Actualiser</button>
        </div>
      </section>

      <!-- TABLEAU RÈGLES & ÉTAT LIVE -->
      <section class="lsu-rules-live">
        <div class="lsu-section-head">
          <h2>Règles & État LIVE</h2>
          <span class="lsu-badge">${rules.length} règle(s)</span>
        </div>

        ${rules.length ? `
          <table class="lsu-table">
            <thead>
              <tr>
                <th style="width: 5%;">État</th>
                <th style="width: 30%;">Règle</th>
                <th style="width: 20%;">Niveau</th>
                <th style="width: 20%;">Cibles</th>
                <th style="width: 15%;">Incidents actifs</th>
                <th style="width: 10%;">Aujourd'hui</th>
              </tr>
            </thead>
            <tbody>
              ${rules.map(rule => {
                const levelLabel = levels.find(l => l.level_key === rule.level_key)?.label || rule.level_key;
                const ruleIncidents = incidentsByRule[rule.name] || [];
                const ruleStats = rulesStats.find(s => s.rule_name === rule.name) || {};
                const targetCount = (rule.target_keys || []).length;
                const todayCount = ruleStats.count || 0;

                return `
                  <tr class="lsu-rule-row">
                    <td class="lsu-status-col">
                      <span class="lsu-emoji">${getStatusEmoji(rule.level_key)}</span>
                    </td>
                    <td><strong>${esc(rule.name)}</strong></td>
                    <td><span class="lsu-level-badge">${esc(levelLabel)}</span></td>
                    <td>
                      ${targetCount ? `${targetCount} cible(s)` : '<em>Toutes</em>'}
                    </td>
                    <td>
                      ${ruleIncidents.length ? `<strong>${ruleIncidents.length}</strong> incident(s)` : '—'}
                    </td>
                    <td>${todayCount ? `+${todayCount}` : '—'}</td>
                  </tr>
                `;
              }).join('')}
            </tbody>
          </table>
        ` : `
          <div class="lsu-empty">Aucune règle configurée. <a href="#live-quality-admin">Créer une règle</a></div>
        `}
      </section>

      <!-- INCIDENTS ACTUELLEMENT ACTIFS -->
      <section class="lsu-incidents-active">
        <div class="lsu-section-head">
          <h2>Incidents Actuellement Actifs</h2>
          <span class="lsu-badge">${activeIncidents.length} incident(s)</span>
        </div>

        ${activeIncidents.length ? `
          <div class="lsu-incidents-grid">
            ${activeIncidents.slice(0, 10).map(inc => {
              const statusColor = {
                'NOUVEAU': '#3b82f6',
                'VU': '#8b5cf6',
                'EN_INVESTIGATION': '#f97316',
                'ACTION_EN_COURS': '#ef4444',
                'RETABLI': '#22c55e'
              }[inc.status] || '#9ca3af';

              const durationSecs = inc.duration_seconds || 0;
              const durationText = durationSecs < 60 ? `${Math.round(durationSecs)}s` :
                                   durationSecs < 3600 ? `${Math.round(durationSecs/60)}m` :
                                   `${Math.round(durationSecs/3600)}h`;

              return `
                <div class="lsu-incident-card">
                  <div class="lsu-incident-header">
                    <strong>${esc(inc.scope_label || inc.agent || 'N/A')}</strong>
                    <span class="lsu-incident-status" style="color: ${statusColor};">●</span>
                  </div>
                  <div class="lsu-incident-detail">
                    <small>${esc(inc.rule_name || 'Incident')}</small>
                  </div>
                  <div class="lsu-incident-duration">
                    <span>${durationText}</span>
                  </div>
                </div>
              `;
            }).join('')}
            ${activeIncidents.length > 10 ? `
              <div class="lsu-incident-card lsu-more">
                <strong>+${activeIncidents.length - 10}</strong> incident(s)
              </div>
            ` : ''}
          </div>
        ` : `
          <div class="lsu-empty">✓ Aucun incident actif — Tout va bien!</div>
        `}
      </section>

      <!-- STATISTIQUES -->
      <section class="lsu-stats">
        <div class="lsu-section-head">
          <h2>Statistiques Aujourd'hui</h2>
          <span class="lsu-badge">${incidents.length} incident(s) total</span>
        </div>

        ${rulesStats.length ? `
          <div class="lsu-stats-grid">
            ${rulesStats.map(stat => `
              <div class="lsu-stat-card">
                <strong>${esc(stat.rule_name || 'N/A')}</strong>
                <div class="lsu-stat-number">${stat.count || 0}</div>
                <small>incident(s)</small>
              </div>
            `).join('')}
          </div>
        ` : `
          <div class="lsu-empty">Pas de statistiques disponibles</div>
        `}
      </section>

      <!-- ACTIONS RAPIDES -->
      <section class="lsu-actions">
        <a href="#live-quality-admin" class="button">⚙️ Configurer les règles</a>
        <a href="#live-incidents" class="button">📊 Voir l'historique</a>
      </section>

    </div>

    <style>
      .lsu-page {
        display: flex;
        flex-direction: column;
        gap: 2rem;
        padding: 1rem;
      }

      .lsu-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 1.5rem;
        background: #f9fafb;
        border-radius: 8px;
        border: 1px solid #e5e7eb;
      }

      .lsu-header h1 {
        margin: 0;
        font-size: 1.5rem;
      }

      .lsu-header p {
        margin: 0.25rem 0 0 0;
        color: #6b7280;
        font-size: 0.875rem;
      }

      .lsu-header-actions {
        display: flex;
        gap: 0.5rem;
      }

      .lsu-section-head {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 1rem;
      }

      .lsu-section-head h2 {
        margin: 0;
        font-size: 1.125rem;
      }

      .lsu-badge {
        background: #dbeafe;
        color: #1e40af;
        padding: 0.25rem 0.75rem;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 500;
      }

      .lsu-table {
        width: 100%;
        border-collapse: collapse;
        background: white;
        border: 1px solid #e5e7eb;
        border-radius: 6px;
        overflow: hidden;
      }

      .lsu-table th {
        background: #f3f4f6;
        padding: 0.75rem;
        text-align: left;
        font-weight: 600;
        font-size: 0.875rem;
        border-bottom: 1px solid #d1d5db;
      }

      .lsu-table td {
        padding: 1rem 0.75rem;
        border-bottom: 1px solid #f3f4f6;
        font-size: 0.875rem;
      }

      .lsu-table tbody tr:hover {
        background: #fafafa;
      }

      .lsu-status-col {
        text-align: center;
      }

      .lsu-emoji {
        font-size: 1.25rem;
      }

      .lsu-level-badge {
        background: #f0fdf4;
        color: #166534;
        padding: 0.25rem 0.5rem;
        border-radius: 4px;
        font-size: 0.8rem;
        font-weight: 500;
      }

      .lsu-incidents-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
        gap: 1rem;
      }

      .lsu-incident-card {
        padding: 1rem;
        background: white;
        border: 1px solid #e5e7eb;
        border-radius: 6px;
        display: flex;
        flex-direction: column;
        gap: 0.5rem;
      }

      .lsu-incident-card.lsu-more {
        justify-content: center;
        align-items: center;
        text-align: center;
        background: #f9fafb;
        color: #9ca3af;
      }

      .lsu-incident-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        font-weight: 500;
      }

      .lsu-incident-detail {
        color: #6b7280;
      }

      .lsu-incident-duration {
        color: #9ca3af;
        font-size: 0.8rem;
      }

      .lsu-stats-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
        gap: 1rem;
      }

      .lsu-stat-card {
        padding: 1rem;
        background: white;
        border: 1px solid #e5e7eb;
        border-radius: 6px;
        text-align: center;
      }

      .lsu-stat-number {
        font-size: 2rem;
        font-weight: bold;
        color: #1f2937;
        margin: 0.5rem 0;
      }

      .lsu-empty {
        padding: 2rem;
        text-align: center;
        color: #9ca3af;
        background: #f9fafb;
        border-radius: 6px;
      }

      .lsu-actions {
        display: flex;
        gap: 1rem;
        padding-top: 1rem;
        border-top: 1px solid #e5e7eb;
      }

      @media (max-width: 900px) {
        .lsu-table {
          font-size: 0.75rem;
        }

        .lsu-table th, .lsu-table td {
          padding: 0.5rem 0.25rem;
        }

        .lsu-incidents-grid {
          grid-template-columns: 1fr;
        }
      }
    </style>
  `;

  // Auto-refresh toutes les 5 secondes
  if (liveSupervisionState.autoRefreshInterval) {
    clearInterval(liveSupervisionState.autoRefreshInterval);
  }
  liveSupervisionState.autoRefreshInterval = setInterval(() => {
    renderSupervisionLive();
  }, 5000);
}
