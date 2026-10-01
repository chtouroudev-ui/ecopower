// Centre Qualité Live - Gestion Améliorée des Incidents RC29.4
// Améliore l'interface Incidents / Alertes avec filtres persistants, sauvegarde manuelle et gestion de statut

let liveIncidentsImprovedState = {
  mode: sessionStorage.getItem('nelyio_incidents_mode') || 'history',
  from: '',
  to: '',
  page: 0,
  pageSize: 15,
  filter: {
    agent: sessionStorage.getItem('nelyio_incidents_filter_agent') || '',
    category: sessionStorage.getItem('nelyio_incidents_filter_category') || '',
    status: sessionStorage.getItem('nelyio_incidents_filter_status') || '',
    search: ''
  },
  selected: [],
  showNewIncidentForm: false
};

function saveIncidentFilters() {
  try {
    sessionStorage.setItem('nelyio_incidents_filter_agent', liveIncidentsImprovedState.filter.agent);
    sessionStorage.setItem('nelyio_incidents_filter_category', liveIncidentsImprovedState.filter.category);
    sessionStorage.setItem('nelyio_incidents_filter_status', liveIncidentsImprovedState.filter.status);
    sessionStorage.setItem('nelyio_incidents_mode', liveIncidentsImprovedState.mode);
  } catch(e) {}
}

function incidentStatusBadge(status) {
  const colors = {
    'NOUVEAU': '#3b82f6',
    'VU': '#8b5cf6',
    'EN_INVESTIGATION': '#f97316',
    'ACTION_EN_COURS': '#ef4444',
    'RETABLI': '#22c55e',
    'CLOTURE': '#6b7280'
  };
  const labels = {
    'NOUVEAU': '🆕 Nouveau',
    'VU': '👁️ Vu',
    'EN_INVESTIGATION': '🔍 Investigation',
    'ACTION_EN_COURS': '⚙️ Action',
    'RETABLI': '✓ Rétabli',
    'CLOTURE': '✔️ Clôturé'
  };
  const color = colors[status] || '#9ca3af';
  const label = labels[status] || status;
  return `<span class="incident-status-badge" style="background:${color}14;color:${color};border:1px solid ${color};padding:0.25rem 0.5rem;border-radius:4px;font-weight:600;white-space:nowrap;font-size:0.85em">${esc(label)}</span>`;
}

function renderIncidentForm() {
  return `
    <details class="card panel" id="lq-new-incident-form">
      <summary><strong>+ Ajouter un incident manuellement</strong><small>pour le suivi manuel et les investigations</small></summary>
      <form class="lq-incident-form">
        <div class="lq-grid">
          <label>
            Agent / Périmètre
            <input name="scope_key" type="text" placeholder="ex. Agent 571 ou GROUP:MED" required>
            <small>Identifiant unique de la cible</small>
          </label>
          <label>
            Type de cible
            <select name="scope_type" required>
              <option value="">Sélectionner...</option>
              <option value="AGENT">Agent</option>
              <option value="GROUP">Groupe</option>
              <option value="CAMPAIGN">Campagne</option>
              <option value="SERVICE">Service</option>
            </select>
          </label>
        </div>
        <div class="lq-grid">
          <label>
            Règle / Catégorie
            <input name="rule_name" type="text" placeholder="ex. Post-appel trop long" required>
          </label>
          <label>
            Niveau
            <select name="level_key" required>
              <option value="">Sélectionner...</option>
              <option value="WARNING">⚠️ Attention</option>
              <option value="ALERT">🔔 Alerte</option>
              <option value="CRITICAL">🚨 Critique</option>
            </select>
          </label>
        </div>
        <label>
          Détail / Raison
          <textarea name="detail" placeholder="Raison du déclenchement de cet incident..." rows="2"></textarea>
        </label>
        <div class="lq-actions">
          <button type="submit" class="button">Créer l'incident</button>
          <span class="form-result" style="margin-left:1rem;"></span>
        </div>
      </form>
    </details>
  `;
}

function renderIncidentsHistoryWithFilters(data, filters) {
  const incidents = data.incidents || [];
  const categories = [...new Set(incidents.map(i => i.category_label))].filter(Boolean);
  const statuses = ['NOUVEAU', 'VU', 'EN_INVESTIGATION', 'ACTION_EN_COURS', 'RETABLI', 'CLOTURE'];

  let filtered = incidents;
  if (filters.agent) {
    filtered = filtered.filter(i => {
      const agent = String(i.agent || i.agent_name || '').toLowerCase();
      return agent.includes(filters.agent.toLowerCase());
    });
  }
  if (filters.category) {
    filtered = filtered.filter(i => i.category_label === filters.category);
  }
  if (filters.status) {
    filtered = filtered.filter(i => i.status === filters.status);
  }
  if (filters.search) {
    const q = filters.search.toLowerCase();
    filtered = filtered.filter(i => {
      return String(i.rule_name || '').toLowerCase().includes(q) ||
             String(i.agent_name || '').toLowerCase().includes(q);
    });
  }

  const pageSize = liveIncidentsImprovedState.pageSize;
  const pages = Math.max(1, Math.ceil(filtered.length / pageSize));
  const page = Math.min(liveIncidentsImprovedState.page, pages - 1);
  const visible = filtered.slice(page * pageSize, (page + 1) * pageSize);

  return `
    <div class="live-incidents-filters-bar">
      <input type="search" id="incident-search" placeholder="Rechercher par règle ou agent…" value="${esc(filters.search)}" style="flex:1;min-width:150px;">
      <select id="incident-filter-agent" style="min-width:120px;">
        <option value="">Agent (Tous)</option>
        ${[...new Set(incidents.map(i => i.agent).filter(Boolean))].sort().map(a => `<option value="${esc(a)}" ${filters.agent === a ? 'selected' : ''}>${esc(a)}</option>`).join('')}
      </select>
      <select id="incident-filter-category" style="min-width:140px;">
        <option value="">Catégorie (Toutes)</option>
        ${categories.sort().map(c => `<option value="${esc(c)}" ${filters.category === c ? 'selected' : ''}>${esc(c)}</option>`).join('')}
      </select>
      <select id="incident-filter-status" style="min-width:130px;">
        <option value="">Statut (Tous)</option>
        ${statuses.map(s => `<option value="${s}" ${filters.status === s ? 'selected' : ''}>${esc({
          'NOUVEAU': '🆕 Nouveau',
          'VU': '👁️ Vu',
          'EN_INVESTIGATION': '🔍 Investigation',
          'ACTION_EN_COURS': '⚙️ Action',
          'RETABLI': '✓ Rétabli',
          'CLOTURE': '✔️ Clôturé'
        }[s] || s)}</option>`).join('')}
      </select>
      <button class="button ghost" id="incident-filter-reset" title="Réinitialiser les filtres">Réinitialiser</button>
      <button class="button ghost" id="incident-export-csv" title="Exporter en CSV">📥 Export</button>
    </div>

    <div class="table-wrap">
      <table class="live-incident-history-table-improved">
        <thead>
          <tr>
            <th style="width:30px;text-align:center;">
              <input type="checkbox" id="incident-select-all" title="Sélectionner tous les incidents visibles" ${liveIncidentsImprovedState.selected.length === visible.length && visible.length > 0 ? 'checked' : ''}>
            </th>
            <th>Date / heure</th>
            <th>Agent</th>
            <th>Incident</th>
            <th>Statut</th>
            <th>Durée</th>
            <th style="width:100px;">Actions</th>
          </tr>
        </thead>
        <tbody>
          ${visible.map((i, idx) => `
            <tr data-incident-id="${esc(i.id || idx)}" style="background:${['NOUVEAU', 'EN_INVESTIGATION'].includes(i.status) ? '#fef3c7' : 'white'}">
              <td style="text-align:center;">
                <input type="checkbox" class="incident-checkbox" value="${esc(i.id || idx)}" ${liveIncidentsImprovedState.selected.includes(i.id || idx) ? 'checked' : ''}>
              </td>
              <td style="white-space:nowrap;font-size:0.875em;">${esc(liveIncidentTime(i.triggered_at || i.first_seen))}</td>
              <td><strong>${esc(i.agent_name || i.scope_label || '—')}</strong><small>${esc(i.agent || '')}</small></td>
              <td><strong>${esc(i.category_label || 'Incident')}</strong><small>${esc(i.rule_name || '')}</small></td>
              <td>${incidentStatusBadge(i.status)}</td>
              <td>${esc(liveDuration(i.duration_seconds || 0))}</td>
              <td style="white-space:nowrap;">
                <button class="button ghost small" data-incident-action="status" data-incident-id="${esc(i.id || idx)}" title="Changer le statut">⋯</button>
              </td>
            </tr>
          `).join('')}
        </tbody>
      </table>
      ${visible.length === 0 ? `<div class="empty" style="padding:2rem;text-align:center;color:#9ca3af;">Aucun incident ne correspond aux critères.</div>` : ''}
    </div>

    ${filtered.length > pageSize ? `
      <div class="sup-pager">
        <button class="button ghost" id="incident-prev" ${page <= 0 ? 'disabled' : ''}>Précédent</button>
        <span>Page ${page + 1} / ${pages}</span>
        <button class="button ghost" id="incident-next" ${page + 1 >= pages ? 'disabled' : ''}>Suivant</button>
      </div>
    ` : ''}
  `;
}

function exportIncidentsCSV(incidents) {
  if (!incidents.length) {
    alert('Aucun incident à exporter.');
    return;
  }
  const headers = ['Date', 'Agent', 'Catégorie', 'Règle', 'Statut', 'Durée'];
  const rows = incidents.map(i => [
    new Date(Number(i.triggered_at || 0) * 1000).toLocaleString('fr-FR'),
    i.agent_name || i.agent || '—',
    i.category_label || '—',
    i.rule_name || '—',
    i.status || '—',
    liveDuration(i.duration_seconds || 0)
  ]);

  const csv = [
    headers.join(';'),
    ...rows.map(r => r.map(cell => `"${String(cell).replace(/"/g, '""')}"`).join(';'))
  ].join('\n');

  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const link = document.createElement('a');
  link.setAttribute('href', URL.createObjectURL(blob));
  link.setAttribute('download', `incidents-${new Date().toISOString().split('T')[0]}.csv`);
  link.click();
}

async function updateIncidentStatus(incidentId, newStatus, comment) {
  try {
    await api('/api/live/incident/' + encodeURIComponent(incidentId) + '/status', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: newStatus, comment: comment || '' })
    });
    return true;
  } catch (err) {
    console.error('Erreur mise à jour statut:', err);
    return false;
  }
}

async function createIncidentManual(formData) {
  try {
    const response = await api('/api/live/incident', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(formData)
    });
    return response;
  } catch (err) {
    throw err;
  }
}

window.LiveIncidentsImproved = {
  renderIncidentForm,
  renderIncidentsHistoryWithFilters,
  exportIncidentsCSV,
  updateIncidentStatus,
  createIncidentManual,
  state: liveIncidentsImprovedState,
  saveFilters: saveIncidentFilters
};
