/**
 * LIVE VIEWS - UI/UX IMPROVEMENTS
 * Nelyio RC29.4+ - Centre Qualité Live
 *
 * Améliore :
 * - Agents: Groupage par groupe + filtres + états colorés
 * - Campagnes: Grille compacte + KPI flottant
 * - Responsive: Zéro scroll horizontal sur 1366px
 * - Performance: Cache filtre/tri + animations fluides
 */

// ===== CONFIGURATION =====

const LIVE_IMPROVEMENTS_CONFIG = {
  // Agents
  agents: {
    itemsPerPage: 50,
    refreshMs: 5000,
    groupBy: 'group', // 'group' | 'none'
    defaultSort: 'status-desc,agent-asc',
  },

  // Campagnes
  campaigns: {
    itemsPerPage: 12,
    refreshMs: 10000,
    gridMinWidth: 240,
    kpiSticky: true,
  },

  // UX
  states: {
    'in_call': { label: 'EN APPEL', class: 'in-call', icon: '🔴' },
    'available': { label: 'DISPONIBLE', class: 'available', icon: '🟢' },
    'pause': { label: 'PAUSE', class: 'pause', icon: '🟡' },
    'offline': { label: 'DÉCONNECTÉ', class: 'offline', icon: '⚪' },
    'unobserved': { label: 'NON OBSERVÉ', class: 'unobserved', icon: '⚫' },
  },

  // Statuts campagnes
  campStatus: {
    'alert': { icon: '🔴', label: 'ALERTE', priority: 3 },
    'warning': { icon: '🟡', label: 'SURVEILLANCE', priority: 2 },
    'ok': { icon: '🟢', label: 'OK', priority: 1 },
  }
};

// ===== FILTRES & PERSISTENCE =====

class LiveViewFilters {
  constructor(viewType) {
    this.viewType = viewType; // 'agents' | 'campaigns'
    this.storageKey = `nelyio.live.${viewType}.filters`;
    this.load();
  }

  load() {
    try {
      const stored = sessionStorage.getItem(this.storageKey);
      this.state = stored ? JSON.parse(stored) : this.defaults();
    } catch (_) {
      this.state = this.defaults();
    }
  }

  defaults() {
    return this.viewType === 'agents' ? {
      state: 'all',
      group: 'all',
      campaign: 'all',
      search: '',
      sort: 'status-desc,agent-asc'
    } : {
      status: 'all',
      service: 'all',
      alertsOnly: false,
      sort: 'status-desc'
    };
  }

  save() {
    try {
      sessionStorage.setItem(this.storageKey, JSON.stringify(this.state));
    } catch (_) {}
  }

  // Exporter en URL pour partage
  toUrl() {
    const params = new URLSearchParams();
    Object.entries(this.state).forEach(([k, v]) => {
      if (v && v !== 'all' && v !== false) {
        params.set(k, v);
      }
    });
    return params.toString();
  }

  // Importer d'URL
  fromUrl(queryString) {
    const params = new URLSearchParams(queryString);
    params.forEach((v, k) => {
      if (k in this.state) {
        if (typeof this.state[k] === 'boolean') {
          this.state[k] = v === 'true';
        } else {
          this.state[k] = v;
        }
      }
    });
    this.save();
  }
}

// ===== RENDU AGENTS AMÉLIORÉ =====

function renderAgentsImproved(data, filters) {
  if (!data || !data.agents) return '<div class="empty">Aucun agent disponible</div>';

  let agents = [...data.agents];

  // Appliquer filtres
  if (filters.state !== 'all') {
    agents = agents.filter(a => normalizeState(a.state, a.kind) === filters.state);
  }

  if (filters.group !== 'all') {
    agents = agents.filter(a => String(a.group_id || a.group) === filters.group);
  }

  if (filters.campaign !== 'all') {
    agents = agents.filter(a => String(a.campaign) === filters.campaign);
  }

  if (filters.search) {
    const q = filters.search.toLowerCase();
    agents = agents.filter(a =>
      String(a.agent || '').toLowerCase().includes(q) ||
      String(a.name || '').toLowerCase().includes(q)
    );
  }

  // Trier
  sortAgents(agents, filters.sort);

  // Grouper
  const grouped = groupBy(agents, 'group_id', 'group');

  let html = `<div class="live-agents-container">`;

  // Filtres (sticky)
  html += renderAgentFilters(filters, data);

  // Groupes
  Object.entries(grouped).forEach(([groupId, groupAgents]) => {
    const groupLabel = groupAgents[0]?.group_name || groupId || 'Non assigné';
    const qualityAvg = Math.round(
      groupAgents.reduce((sum, a) => sum + (Number(a.quality_score) || 0), 0) /
      groupAgents.length
    );

    html += `
      <div class="live-agent-group">
        <div class="live-agent-group-header">
          <strong>${escapeHtml(groupLabel)}</strong>
          <small>${groupAgents.length} agent(s) · Qualité ${qualityAvg}%</small>
        </div>
        <table class="live-agents-table">
          <thead>
            <tr>
              <th>Agent</th>
              <th>État</th>
              <th>Appel actuel</th>
              <th>Pauses</th>
            </tr>
          </thead>
          <tbody>
            ${groupAgents.map(a => renderAgentRow(a)).join('')}
          </tbody>
        </table>
      </div>
    `;
  });

  html += `</div>`;
  return html;
}

function renderAgentFilters(filters, data) {
  const states = ['all', 'in_call', 'available', 'pause', 'offline'];
  const groups = [...new Set(data.agents.map(a => a.group_id || a.group))].filter(Boolean);
  const campaigns = [...new Set(data.agents.map(a => a.campaign))].filter(Boolean);

  return `
    <div class="live-agents-filters">
      <div class="live-filter-group">
        <label>État</label>
        <select id="live-agent-state-filter" onchange="handleAgentFilterChange('state', this.value)">
          <option value="all" ${filters.state === 'all' ? 'selected' : ''}>Tous</option>
          ${states.filter(s => s !== 'all').map(s =>
            `<option value="${s}" ${filters.state === s ? 'selected' : ''}>
              ${LIVE_IMPROVEMENTS_CONFIG.states[s]?.label || s}
            </option>`
          ).join('')}
        </select>
      </div>

      <div class="live-filter-group">
        <label>Groupe</label>
        <select id="live-agent-group-filter" onchange="handleAgentFilterChange('group', this.value)">
          <option value="all" ${filters.group === 'all' ? 'selected' : ''}>Tous les groupes</option>
          ${groups.map(g =>
            `<option value="${g}" ${filters.group === g ? 'selected' : ''}>
              ${escapeHtml(g)}
            </option>`
          ).join('')}
        </select>
      </div>

      <div class="live-filter-group">
        <label>Campagne</label>
        <select id="live-agent-campaign-filter" onchange="handleAgentFilterChange('campaign', this.value)">
          <option value="all" ${filters.campaign === 'all' ? 'selected' : ''}>Toutes</option>
          ${campaigns.map(c =>
            `<option value="${c}" ${filters.campaign === c ? 'selected' : ''}>
              ${escapeHtml(c)}
            </option>`
          ).join('')}
        </select>
      </div>

      <div class="live-filter-group">
        <input type="search" id="live-agent-search" placeholder="Chercher agent…"
               value="${filters.search || ''}"
               onchange="handleAgentFilterChange('search', this.value)">
      </div>

      <div class="live-filter-group">
        <label>Tri</label>
        <select onchange="handleAgentFilterChange('sort', this.value)">
          <option value="status-desc,agent-asc" ${filters.sort === 'status-desc,agent-asc' ? 'selected' : ''}>
            Alerte d'abord
          </option>
          <option value="agent-asc">Nom agent</option>
          <option value="state-asc">État</option>
        </select>
      </div>
    </div>
  `;
}

function renderAgentRow(agent) {
  const stateInfo = normalizeState(agent.state, agent.kind);
  const stateConfig = LIVE_IMPROVEMENTS_CONFIG.states[stateInfo] || {};

  const callDuration = agent.call_duration_seconds
    ? formatDuration(agent.call_duration_seconds)
    : '—';

  const pauseDuration = agent.pause_duration_seconds
    ? formatDuration(agent.pause_duration_seconds)
    : '0m';

  return `
    <tr>
      <td>
        <span class="live-agent-name">${escapeHtml(agent.name || agent.agent)}</span>
        <span class="live-agent-context">${escapeHtml(agent.current_queue || '')}</span>
      </td>
      <td>
        <span class="live-agent-state ${stateConfig.class || ''}">
          ${stateConfig.icon || '⚫'} ${stateConfig.label || stateInfo}
        </span>
      </td>
      <td>
        <span class="live-call-duration">${callDuration}</span>
        ${agent.current_call_reference ?
          `<span class="live-call-ref">Ref: ${escapeHtml(agent.current_call_reference)}</span>`
          : ''}
      </td>
      <td>
        <strong>${pauseDuration}</strong>
        <small style="display:block;color:var(--muted,#718096);font-size:12px;margin-top:2px">
          ${formatPauseType(agent.pause_type)}
        </small>
      </td>
    </tr>
  `;
}

// ===== RENDU CAMPAGNES AMÉLIORÉ =====

function renderCampaignsImproved(data, filters) {
  if (!data || !data.campaigns) return '<div class="empty">Aucune campagne</div>';

  let campaigns = [...data.campaigns];

  // Filtres
  if (filters.status !== 'all') {
    campaigns = campaigns.filter(c => getCampStatus(c) === filters.status);
  }

  if (filters.service !== 'all') {
    campaigns = campaigns.filter(c => c.services?.includes(filters.service));
  }

  if (filters.alertsOnly) {
    campaigns = campaigns.filter(c => getCampStatus(c) === 'alert');
  }

  // Tri
  campaigns.sort((a, b) => {
    const sa = getCampStatus(a);
    const sb = getCampStatus(b);
    const pa = LIVE_IMPROVEMENTS_CONFIG.campStatus[sa]?.priority || 0;
    const pb = LIVE_IMPROVEMENTS_CONFIG.campStatus[sb]?.priority || 0;
    return pb - pa; // Alertes d'abord
  });

  const totalIncidents = campaigns.reduce((n, c) => n + (c.incident_count || 0), 0);
  const totalAgents = campaigns.reduce((n, c) => n + (c.agent_count || 0), 0);
  const avgQuality = Math.round(
    campaigns.reduce((sum, c) => sum + (c.quality_score || 0), 0) / campaigns.length
  );

  let html = `
    <div class="live-campaigns-wrapper">
      <div>
        <div class="live-agents-filters">
          <div class="live-filter-group">
            <label>Statut</label>
            <select onchange="handleCampFilterChange('status', this.value)">
              <option value="all">Tous</option>
              <option value="alert">Alerte</option>
              <option value="warning">Surveillance</option>
              <option value="ok">OK</option>
            </select>
          </div>

          <div class="live-filter-group">
            <input type="checkbox" id="alerts-only" onchange="handleCampFilterChange('alertsOnly', this.checked)">
            <label for="alerts-only" style="margin:0">Alertes seulement</label>
          </div>
        </div>

        <div class="live-campaigns-grid">
          ${campaigns.map(c => renderCampaignCard(c)).join('')}
        </div>
      </div>

      <div class="live-kpi-panel">
        <div class="live-kpi-title">📊 Tableau de bord</div>
        <div class="live-kpi-row">
          <span class="live-kpi-label">Campagnes</span>
          <span class="live-kpi-value">${campaigns.length}</span>
        </div>
        <div class="live-kpi-row">
          <span class="live-kpi-label">Incidents</span>
          <span class="live-kpi-value">${totalIncidents}${totalIncidents > 0 ? ' ⚠️' : ''}</span>
        </div>
        <div class="live-kpi-row">
          <span class="live-kpi-label">Agents</span>
          <span class="live-kpi-value">${totalAgents}</span>
        </div>
        <div class="live-kpi-row">
          <span class="live-kpi-label">Qualité moy</span>
          <span class="live-kpi-value">${avgQuality}%${avgQuality < 85 ? ' ⚠️' : ''}</span>
        </div>
      </div>
    </div>
  `;

  return html;
}

function renderCampaignCard(campaign) {
  const status = getCampStatus(campaign);
  const statusConfig = LIVE_IMPROVEMENTS_CONFIG.campStatus[status] || {};

  return `
    <div class="live-campaign-card ${status}" data-campaign-id="${campaign.id}">
      <div class="live-campaign-status">
        <span class="live-campaign-status-icon">${statusConfig.icon}</span>
        <span>${statusConfig.label}</span>
      </div>
      <div class="live-campaign-name">${escapeHtml(campaign.name)}</div>
      <div class="live-campaign-meta">
        ${campaign.services?.join(' · ') || ''} · ${campaign.agent_count || 0} agents
      </div>
      <div class="live-campaign-metrics">
        <div class="live-metric-item">
          <div class="live-metric-label">Agents</div>
          <div class="live-metric-value">${campaign.available_agents}/${campaign.agent_count}</div>
        </div>
        <div class="live-metric-item">
          <div class="live-metric-label">Qualité</div>
          <div class="live-metric-value">${campaign.quality_score}%</div>
        </div>
        <div class="live-metric-item">
          <div class="live-metric-label">Attente</div>
          <div class="live-metric-value">${formatDuration(campaign.asa_seconds || 0)}</div>
        </div>
        <div class="live-metric-item">
          <div class="live-metric-label">Ref</div>
          <div class="live-metric-value">${campaign.reference_percent || 0}%</div>
        </div>
      </div>
    </div>
  `;
}

// ===== UTILITAIRES =====

function groupBy(items, ...keys) {
  return items.reduce((acc, item) => {
    const key = keys.map(k => item[k]).filter(Boolean).join('_') || 'other';
    if (!acc[key]) acc[key] = [];
    acc[key].push(item);
    return acc;
  }, {});
}

function normalizeState(state, kind) {
  if (!state) return kind || 'unobserved';
  const s = String(state).toLowerCase();
  if (s.includes('appel') || s.includes('call')) return 'in_call';
  if (s.includes('pause') || s.includes('break')) return 'pause';
  if (s.includes('offline') || s.includes('déconnecté')) return 'offline';
  if (s.includes('disponible') || s.includes('available') || s.includes('ready')) return 'available';
  return kind || s;
}

function getCampStatus(campaign) {
  const quality = campaign.quality_score || 100;
  const incidents = campaign.incident_count || 0;
  const available = campaign.available_agents || 0;
  const total = campaign.agent_count || 1;

  if (incidents > 0 || quality < 70 || available < Math.ceil(total * 0.8)) return 'alert';
  if (quality < 85) return 'warning';
  return 'ok';
}

function sortAgents(agents, sortSpec) {
  const specs = (sortSpec || '').split(',').map(s => s.trim()).filter(Boolean);
  agents.sort((a, b) => {
    for (const spec of specs) {
      const [key, dir] = spec.split('-');
      const aVal = a[key] || '';
      const bVal = b[key] || '';

      const cmp = String(aVal).localeCompare(String(bVal), 'fr', {numeric: true});
      if (cmp !== 0) return dir === 'desc' ? -cmp : cmp;
    }
    return 0;
  });
}

function formatDuration(seconds) {
  const n = Math.max(0, Math.floor(Number(seconds) || 0));
  const h = Math.floor(n / 3600);
  const m = Math.floor((n % 3600) / 60);
  const s = n % 60;

  if (h) return `${h}h ${String(m).padStart(2, '0')}m`;
  return `${m}m ${String(s).padStart(2, '0')}s`;
}

function formatPauseType(pauseType) {
  const types = {
    'postwork': 'Post-appel',
    'coaching': 'Coaching',
    'lunch': 'Déjeuner',
    'normal': 'Pause'
  };
  return types[pauseType] || '';
}

function escapeHtml(text) {
  const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' };
  return String(text || '').replace(/[&<>"']/g, m => map[m]);
}

// ===== GESTIONNAIRES D'ÉVÉNEMENTS =====

let agentFilters = new LiveViewFilters('agents');
let campaignFilters = new LiveViewFilters('campaigns');

function handleAgentFilterChange(key, value) {
  agentFilters.state[key] = value;
  agentFilters.save();
  // Déclencher re-rendu
  if (window.renderAgentsImproved) {
    window.liveRefreshAgents?.();
  }
}

function handleCampFilterChange(key, value) {
  campaignFilters.state[key] = value;
  campaignFilters.save();
  if (window.renderCampaignsImproved) {
    window.liveRefreshCampaigns?.();
  }
}

// Export
window.LiveImprovements = {
  renderAgentsImproved,
  renderCampaignsImproved,
  config: LIVE_IMPROVEMENTS_CONFIG,
  filters: { agentFilters, campaignFilters }
};
