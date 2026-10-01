// Centre Qualité Live - Améliorations RC29.4 FIX1
// Système de filtres persistants, groupement par unité, et rendu optimisé

const LIVE_IMPROVEMENTS_CONFIG = {
  states: {
    in_call: { label: 'EN APPEL', emoji: '🔴', icon: 'call' },
    available: { label: 'DISPONIBLE', emoji: '🟢', icon: 'ready' },
    pause: { label: 'PAUSE', emoji: '🟡', icon: 'pause' },
    offline: { label: 'DÉCONNECTÉ', emoji: '⚪', icon: 'offline' },
    unobserved: { label: 'NON OBSERVÉ', emoji: '⚫', icon: 'unobserved' }
  },
  campaignStatuses: {
    active: { label: 'ACTIF', class: 'active' },
    pause: { label: 'EN PAUSE', class: 'pause' },
    critical: { label: 'CRITIQUE', class: 'critical' }
  },
  postworkSeverity: {
    normal: { threshold: 0, label: '' },
    warning: { threshold: 10, label: '⚠️ Surveillance' },
    alert: { threshold: 15, label: '⚠️ Alerte' },
    critical: { threshold: 25, label: '🚨 Critique' }
  },
  refreshInterval: 2000
};

class LiveViewFilters {
  constructor(viewType = 'agents') {
    this.viewType = viewType;
    this.state = this.load();
  }

  load() {
    try {
      const stored = sessionStorage.getItem(`nelyio.live.filters.${this.viewType}`);
      return stored ? JSON.parse(stored) : this.defaults();
    } catch (e) {
      return this.defaults();
    }
  }

  defaults() {
    return {
      state: '',
      group: '',
      campaign: '',
      search: '',
      sort: { key: '', direction: 'asc' }
    };
  }

  save() {
    try {
      sessionStorage.setItem(
        `nelyio.live.filters.${this.viewType}`,
        JSON.stringify(this.state)
      );
    } catch (e) {
      console.warn('Could not save filters to sessionStorage', e);
    }
    return this.state;
  }

  toUrl() {
    const params = new URLSearchParams();
    if (this.state.state) params.set('state', this.state.state);
    if (this.state.group) params.set('group', this.state.group);
    if (this.state.campaign) params.set('campaign', this.state.campaign);
    if (this.state.search) params.set('search', this.state.search);
    return params.toString();
  }

  static fromUrl(queryString, viewType = 'agents') {
    const filters = new LiveViewFilters(viewType);
    const params = new URLSearchParams(queryString);
    if (params.has('state')) filters.state.state = params.get('state');
    if (params.has('group')) filters.state.group = params.get('group');
    if (params.has('campaign')) filters.state.campaign = params.get('campaign');
    if (params.has('search')) filters.state.search = params.get('search');
    return filters;
  }
}

function normalizeState(state, kind) {
  const raw = String(state || '').toLowerCase().trim();
  const k = String(kind || '').toLowerCase().trim();

  if (k === 'call' || raw.includes('call') || raw.includes('appel')) return 'in_call';
  if (k === 'ready' || raw.includes('ready') || raw.includes('disponible')) return 'available';
  if (k === 'pause' || raw.includes('pause')) return 'pause';
  if (k === 'offline' || raw.includes('offline') || raw.includes('déco')) return 'offline';
  return 'unobserved';
}

function formatDuration(seconds) {
  const n = Math.max(0, Math.floor(Number(seconds) || 0));
  if (n === 0) return '—';
  const h = Math.floor(n / 3600);
  const m = Math.floor(n / 60) % 60;
  const s = n % 60;
  if (h > 0) return `${h}h ${String(m).padStart(2, '0')}m`;
  return `${m}m ${String(s).padStart(2, '0')}s`;
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

function groupBy(items, ...keys) {
  const result = {};
  items.forEach(item => {
    const keyPath = keys.map(k => item[k]).join('|');
    if (!result[keyPath]) result[keyPath] = [];
    result[keyPath].push(item);
  });
  return result;
}

function sortAgents(agents, sortSpec) {
  if (!sortSpec.key || sortSpec.direction === 'default') return agents;

  const compare = (a, b) => {
    let aVal = a[sortSpec.key];
    let bVal = b[sortSpec.key];

    if (typeof aVal === 'number' && typeof bVal === 'number') {
      return sortSpec.direction === 'asc' ? aVal - bVal : bVal - aVal;
    }

    const aStr = String(aVal || '').toLowerCase();
    const bStr = String(bVal || '').toLowerCase();
    const cmp = aStr.localeCompare(bStr, 'fr', { numeric: true });
    return sortSpec.direction === 'asc' ? cmp : -cmp;
  };

  return [...agents].sort(compare);
}

function renderAgentRow(agent) {
  const state = normalizeState(agent.state, agent.kind);
  const stateConfig = LIVE_IMPROVEMENTS_CONFIG.states[state] || LIVE_IMPROVEMENTS_CONFIG.states.unobserved;

  const callDuration = formatDuration(
    agent.activity?.state_seconds?.call ||
    agent.call_duration_seconds || 0
  );

  const pauseDuration = formatDuration(
    Math.max(
      agent.activity?.state_seconds?.pause || 0,
      agent.pause_duration_seconds || 0,
      agent.activity?.state_seconds?.wrap || 0
    )
  );

  const postworkSeconds = Number(agent.activity?.state_seconds?.wrap || 0);
  let postworkClass = '';
  if (postworkSeconds >= 25) postworkClass = 'live-postwork-critical';
  else if (postworkSeconds >= 15) postworkClass = 'live-postwork-alert';
  else if (postworkSeconds >= 10) postworkClass = 'live-postwork-warning';

  return `
    <tr data-live-agent-id="${escapeHtml(agent.agent || agent.id || '')}">
      <td><strong>${escapeHtml(agent.name || agent.agent || '')}</strong></td>
      <td>
        <span class="live-agent-state ${state}">
          ${stateConfig.emoji} ${stateConfig.label}
        </span>
      </td>
      <td class="live-agent-duration">${callDuration}</td>
      <td class="live-agent-duration">${pauseDuration}</td>
    </tr>
  `;
}

function renderAgentsImproved(data, filters = {}) {
  if (!data || !data.agents) return '<div class="live-empty-state"><strong>Aucune donnée disponible</strong></div>';

  let agents = data.agents || [];

  // Appliquer les filtres
  if (filters.state) {
    agents = agents.filter(a => {
      const state = normalizeState(a.state, a.kind);
      return state === filters.state;
    });
  }

  if (filters.group) {
    agents = agents.filter(a => {
      return String(a.group_id || a.group || '').toLowerCase() === String(filters.group).toLowerCase();
    });
  }

  if (filters.campaign) {
    agents = agents.filter(a => {
      return String(a.campaign || '').toLowerCase().includes(String(filters.campaign).toLowerCase());
    });
  }

  if (filters.search) {
    const searchLower = String(filters.search).toLowerCase();
    agents = agents.filter(a => {
      const name = String(a.name || a.agent || '').toLowerCase();
      const id = String(a.agent || a.id || '').toLowerCase();
      const campaign = String(a.campaign || '').toLowerCase();
      return name.includes(searchLower) || id.includes(searchLower) || campaign.includes(searchLower);
    });
  }

  // Grouper par unité organisationnelle
  const grouped = groupBy(agents, 'group_id', 'group_name');

  let html = '<div class="live-agents-container">';

  // Ajouter les filtres
  html += renderAgentFilters(filters, data);

  // Groupes
  for (const groupKey in grouped) {
    const groupAgents = grouped[groupKey];
    if (groupAgents.length === 0) continue;

    const firstAgent = groupAgents[0];
    const groupId = firstAgent.group_id || firstAgent.group || 'AUTRE';
    const groupName = firstAgent.group_name || firstAgent.group || 'Groupe sans nom';

    // Calcul qualité du groupe
    const qualities = groupAgents
      .map(a => Number(a.quality_score || 0))
      .filter(q => q > 0);
    const avgQuality = qualities.length > 0
      ? Math.round(qualities.reduce((a, b) => a + b) / qualities.length)
      : '—';

    html += `
      <div class="live-agent-group">
        <div class="live-agent-group-header">
          <div class="live-agent-group-name">
            <strong>${escapeHtml(groupName)}</strong>
            <small>${escapeHtml(groupId)}</small>
          </div>
          <div class="live-agent-group-stats">
            <span><strong>${groupAgents.length}</strong> agent(s)</span>
            <span>Qualité: <strong>${avgQuality}%</strong></span>
          </div>
        </div>
        <div class="table-wrap">
          <table class="live-agents-table">
            <thead>
              <tr>
                <th>Agent</th>
                <th>État</th>
                <th>Appel</th>
                <th>Pauses</th>
              </tr>
            </thead>
            <tbody>
              ${groupAgents.map(renderAgentRow).join('')}
            </tbody>
          </table>
        </div>
      </div>
    `;
  }

  if (Object.keys(grouped).length === 0) {
    html += '<div class="live-empty-state"><strong>Aucun agent ne correspond aux filtres</strong></div>';
  }

  html += '</div>';
  return html;
}

function renderAgentFilters(filters = {}, data = {}) {
  const states = Object.entries(LIVE_IMPROVEMENTS_CONFIG.states).map(([key, config]) => ({
    value: key,
    label: config.label
  }));

  const groups = [];
  const groupsSet = new Set();
  (data.agents || []).forEach(a => {
    const gId = a.group_id || a.group;
    if (gId && !groupsSet.has(gId)) {
      groupsSet.add(gId);
      groups.push({ value: gId, label: a.group_name || gId });
    }
  });

  const campaigns = [];
  const campaignsSet = new Set();
  (data.agents || []).forEach(a => {
    const camp = a.campaign;
    if (camp && !campaignsSet.has(camp)) {
      campaignsSet.add(camp);
      campaigns.push({ value: camp, label: a.campaign_name || camp });
    }
  });

  return `
    <div class="live-agents-filters">
      <div>
        <label for="filter-state" class="sr-only">Filtrer par État</label>
        <select id="filter-state" data-filter="state" onchange="handleAgentFilterChange('state', this.value)">
          <option value="">État (Tous)</option>
          ${states.map(s => `<option value="${s.value}" ${filters.state === s.value ? 'selected' : ''}>${s.label}</option>`).join('')}
        </select>
      </div>
      <div>
        <label for="filter-group" class="sr-only">Filtrer par Groupe</label>
        <select id="filter-group" data-filter="group" onchange="handleAgentFilterChange('group', this.value)">
          <option value="">Groupe (Tous)</option>
          ${groups.map(g => `<option value="${g.value}" ${filters.group === g.value ? 'selected' : ''}>${g.label}</option>`).join('')}
        </select>
      </div>
      <div>
        <label for="filter-campaign" class="sr-only">Filtrer par Campagne</label>
        <select id="filter-campaign" data-filter="campaign" onchange="handleAgentFilterChange('campaign', this.value)">
          <option value="">Campagne (Tous)</option>
          ${campaigns.map(c => `<option value="${c.value}" ${filters.campaign === c.value ? 'selected' : ''}>${c.label}</option>`).join('')}
        </select>
      </div>
      <div>
        <label for="filter-search" class="sr-only">Rechercher</label>
        <input
          type="search"
          id="filter-search"
          placeholder="Rechercher…"
          value="${escapeHtml(filters.search || '')}"
          oninput="handleAgentFilterChange('search', this.value)"
        >
      </div>
    </div>
  `;
}

function renderCampaignsImproved(data, filters = {}) {
  if (!data || !data.campaigns) return '<div class="live-empty-state"><strong>Aucune campagne disponible</strong></div>';

  let campaigns = data.campaigns || [];

  // Appliquer filtres si nécessaire
  if (filters.search) {
    campaigns = campaigns.filter(c => {
      const name = String(c.name || '').toLowerCase();
      const id = String(c.id || '').toLowerCase();
      return name.includes(filters.search.toLowerCase()) || id.includes(filters.search.toLowerCase());
    });
  }

  let html = '<div class="live-campaigns-grid">';

  campaigns.forEach(campaign => {
    const statusKey = campaign.status || 'active';
    const statusConfig = LIVE_IMPROVEMENTS_CONFIG.campaignStatuses[statusKey] || LIVE_IMPROVEMENTS_CONFIG.campaignStatuses.active;

    html += `
      <div class="live-campaign-card">
        <div class="live-campaign-card-header">${escapeHtml(campaign.id || 'N/A')}</div>
        <div class="live-campaign-card-name">${escapeHtml(campaign.name || campaign.id || '')}</div>
        <div class="live-campaign-card-status live-campaign-status-${statusConfig.class}">
          ${statusConfig.label}
        </div>
        <div class="live-campaign-card-metrics">
          <div class="live-campaign-card-metric">
            <span class="live-campaign-card-metric-label">Agents</span>
            <span class="live-campaign-card-metric-value">${Number(campaign.agent_count || 0)}</span>
          </div>
          <div class="live-campaign-card-metric">
            <span class="live-campaign-card-metric-label">Qualité</span>
            <span class="live-campaign-card-metric-value">${Number(campaign.quality_score || 0)}%</span>
          </div>
          ${campaign.received_today ? `
            <div class="live-campaign-card-metric">
              <span class="live-campaign-card-metric-label">Reçus</span>
              <span class="live-campaign-card-metric-value">${Number(campaign.received_today)}</span>
            </div>
          ` : ''}
          ${campaign.handled_today ? `
            <div class="live-campaign-card-metric">
              <span class="live-campaign-card-metric-label">Traités</span>
              <span class="live-campaign-card-metric-value">${Number(campaign.handled_today)}</span>
            </div>
          ` : ''}
        </div>
      </div>
    `;
  });

  if (campaigns.length === 0) {
    html += '<div class="live-empty-state"><strong>Aucune campagne ne correspond aux filtres</strong></div>';
  }

  html += '</div>';
  return html;
}

// Exporter l'interface globale
window.LiveImprovements = {
  renderAgentsImproved,
  renderCampaignsImproved,
  renderAgentFilters,
  LiveViewFilters,
  config: LIVE_IMPROVEMENTS_CONFIG,
  filters: {
    agentFilters: new LiveViewFilters('agents').state,
    campaignFilters: new LiveViewFilters('campaigns').state
  }
};

// Handler pour changement de filtre (à implémenter dans le contexte de l'application)
if (typeof window.handleAgentFilterChange === 'undefined') {
  window.handleAgentFilterChange = function(filterKey, value) {
    console.log(`Filter change: ${filterKey} = ${value}`);
    // À implémenter selon le contexte de l'application
  };
}
