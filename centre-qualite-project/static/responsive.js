/* Nelyio v12 Responsive. Presentation-only enhancement, no network requests.
   All original IDs, forms, permissions, row handlers and API routes are retained. */
(() => {
  'use strict';
  const body = document.body, app = document.getElementById('app');
  if (!app) return;
  const one = (s, root = document) => root.querySelector(s);
  const all = (s, root = document) => Array.from(root.querySelectorAll(s));
  const storage = {
    get(key, fallback = null) { try { return localStorage.getItem(key) ?? fallback; } catch { return fallback; } },
    set(key, value) { try { localStorage.setItem(key, value); } catch { /* Private browsing: keep current UI. */ } },
    remove(key) { try { localStorage.removeItem(key); } catch { /* Optional preference. */ } }
  };
  const text = (el, value) => { if (el && el.textContent !== value) el.textContent = value; };
  const create = (tag, cls, content) => {
    const el = document.createElement(tag); if (cls) el.className = cls;
    if (content !== undefined) el.textContent = content;
    return el;
  };
  const button = (label, cls = 'button ghost') => {
    const el = create('button', cls, label); el.type = 'button'; return el;
  };
  const view = () => (location.hash || '#dashboard').slice(1).split(/[/?]/)[0];
  const mobile = matchMedia('(max-width: 1023px)');
  const tableStates = new Map();
  const overflowStates = new Map();
  let serial = 0, scheduled = false, lastView = view();
  body.dataset.uiView = lastView;
  body.classList.add('ui-responsive');
  body.classList.toggle('ui-density-compact', storage.get('nelyio-density') === 'compact');
  body.classList.toggle('ui-help-open', storage.get('nelyio-help') === '1');
  body.classList.toggle('ui-sidebar-collapsed', storage.get('nelyio-ui-sidebar') === '1');

  // A drawer on narrow screens; a collapsible rail on desktop.
  const sidebar = one('.sidebar'), main = one('.main'), top = one('.topbar');
  sidebar.id = 'ui-navigation';
  sidebar.setAttribute('aria-label', 'Navigation principale');
  const toggle = one('#ui-sidebar-toggle') || button('\u2630', 'button ghost ui-sidebar-toggle');
  toggle.id = 'ui-sidebar-toggle'; toggle.setAttribute('aria-controls', sidebar.id);
  top.prepend(toggle);
  const closeNav = button('\u00d7', 'ui-nav-close');
  closeNav.setAttribute('aria-label', 'Fermer le menu'); sidebar.prepend(closeNav);
  const navScroll = create('div', 'ui-nav-scroll');
  const footer = one('.sidebar-bottom', sidebar);
  Array.from(sidebar.children).filter(el => el !== closeNav && el !== footer && !el.classList.contains('brand')).forEach(el => navScroll.append(el));
  sidebar.insertBefore(navScroll, footer);
  const backdrop = create('div', 'ui-mobile-backdrop');
  backdrop.setAttribute('aria-hidden', 'true'); body.append(backdrop);
  const skip = create('a', 'ui-skip-link', 'Aller au contenu');
  skip.href = '#app'; body.prepend(skip); app.tabIndex = -1;
  skip.onclick = e => { e.preventDefault(); app.focus(); app.scrollIntoView({block: 'start'}); };

  function updateNavigation() {
    const open = mobile.matches && body.classList.contains('ui-nav-open');
    sidebar.inert = mobile.matches && !open;
    main.inert = open; skip.inert = open;
    if (open) { sidebar.setAttribute('role', 'dialog'); sidebar.setAttribute('aria-modal', 'true'); }
    else { sidebar.removeAttribute('role'); sidebar.removeAttribute('aria-modal'); }
    toggle.setAttribute('aria-expanded', String(mobile.matches ? open : !body.classList.contains('ui-sidebar-collapsed')));
    const label = mobile.matches ? 'Ouvrir le menu' : body.classList.contains('ui-sidebar-collapsed') ? 'Agrandir le menu' : 'R\u00e9duire le menu';
    toggle.setAttribute('aria-label', label); toggle.title = label;
  }
  function setMenu(open, restoreFocus = true) {
    body.classList.toggle('ui-nav-open', Boolean(open && mobile.matches));
    updateNavigation();
    if (open && mobile.matches) closeNav.focus();
    else if (restoreFocus && mobile.matches) toggle.focus();
  }
  toggle.onclick = () => {
    if (mobile.matches) setMenu(!body.classList.contains('ui-nav-open'));
    else {
      body.classList.toggle('ui-sidebar-collapsed');
      storage.set('nelyio-ui-sidebar', body.classList.contains('ui-sidebar-collapsed') ? '1' : '0');
      updateNavigation(); schedule();
    }
  };
  closeNav.onclick = () => setMenu(false);
  backdrop.onclick = () => setMenu(false);
  sidebar.addEventListener('click', e => { if (e.target.closest('a[data-view],#logout')) setMenu(false, false); });
  mobile.addEventListener('change', () => { setMenu(false, false); schedule(); });
  document.addEventListener('keydown', e => {
    if (!body.classList.contains('ui-nav-open')) return;
    if (e.key === 'Escape') { e.preventDefault(); setMenu(false); }
    if (e.key === 'Tab') {
      const items = all('a[href],button:not([disabled])', sidebar).filter(el => el.getClientRects().length);
      const first = items[0], last = items[items.length - 1];
      if (!sidebar.contains(document.activeElement)) { e.preventDefault(); (e.shiftKey ? last : first)?.focus(); }
      else if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last?.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first?.focus(); }
    }
  });
  updateNavigation();

  // RC2: native disclosures, one open family by default; search never changes rights.
  const navSections = all('.nav-section', sidebar);
  const navSearchBox = one('.nav-search', sidebar), navSearch = one('#nav-search-input', sidebar);
  const navEmpty = one('#nav-search-empty', sidebar);
  let navAccount = null;
  const searchKey = value => String(value||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
  function activeSection() {
    const current=view()==='pc'?'inventory':view();
    return one(`a[data-view="${CSS.escape(current)}"]`,sidebar)?.closest('.nav-section');
  }
  function syncSections(activateCurrent=true) {
    const account=typeof currentUser!=='undefined'?currentUser?.username:null;
    if(account!==navAccount){navAccount=account;if(navSearch)navSearch.value='';}
    const query=searchKey(navSearch?.value.trim());
    let matches=0;
    const active=activeSection();
    for(const section of navSections){
      const links=all('a[data-view]',section);
      let count=0;
      links.forEach(a=>{
        const allowed=!a.classList.contains('hidden');
        const match=allowed&&(!query||searchKey(a.textContent).includes(query));
        a.toggleAttribute('data-nav-filtered',!match);if(match)count++;
        const selected=a.dataset.view===(view()==='pc'?'inventory':view());
        if(selected)a.setAttribute('aria-current','page');else a.removeAttribute('aria-current');
      });
      section.hidden=count===0;matches+=count;
      if(query)section.open=count>0;
      else if(activateCurrent)section.open=section===active&&!section.hidden;
      one('summary',section)?.setAttribute('aria-expanded',String(section.open));
    }
    if(navEmpty)navEmpty.hidden=!query||matches>0;
    // A permissions-only account has no empty navigation families.
    if(navSearchBox)navSearchBox.hidden=!navSections.some(s=>all('a[data-view]',s).some(a=>!a.classList.contains('hidden')));
  }
  navSections.forEach(section=>{
    const summary=one('summary',section);
    summary.addEventListener('click',e=>{
      if(!mobile.matches&&body.classList.contains('ui-sidebar-collapsed')){
        e.preventDefault();body.classList.remove('ui-sidebar-collapsed');storage.set('nelyio-ui-sidebar','0');section.open=true;updateNavigation();schedule();
      }
    });
    section.addEventListener('toggle',()=>{
      summary.setAttribute('aria-expanded',String(section.open));
      if(section.open&&!navSearch?.value.trim())navSections.forEach(other=>{if(other!==section)other.open=false;});
    });
  });
  navSearch?.addEventListener('input',()=>syncSections(true));
  navSearch?.addEventListener('keydown',e=>{if(e.key==='Escape'&&navSearch.value){e.preventDefault();e.stopPropagation();navSearch.value='';syncSections(true);}});
  document.addEventListener('nelyio:navigation',()=>syncSections(true));
  window.addEventListener('hashchange',()=>syncSections(true));
  syncSections(true);

  // Small user preferences, local to this browser and not stored in a database.
  const appearance = create('details', 'ui-appearance');
  const appearanceSummary = create('summary', 'button ghost', 'Affichage');
  appearanceSummary.setAttribute('aria-label', 'Options d\u2019affichage');
  const appearancePanel = create('div', 'ui-appearance-panel');
  appearancePanel.append(create('strong', '', 'Densit\u00e9 des tableaux'));
  [['comfortable', 'Confort'], ['compact', 'Compact']].forEach(([value, label]) => {
    const line = create('label'), input = create('input');
    input.type = 'radio'; input.name = 'ui-density'; input.value = value;
    input.checked = (storage.get('nelyio-density', 'comfortable') === value);
    input.onchange = () => {
      body.classList.toggle('ui-density-compact', value === 'compact');
      storage.set('nelyio-density', value); schedule();
    };
    line.append(input, document.createTextNode(label)); appearancePanel.append(line);
  });
  appearancePanel.append(create('hr'));
  const helpLine = create('label'), helpInput = create('input'); helpInput.type = 'checkbox';
  helpInput.checked = body.classList.contains('ui-help-open');
  helpInput.onchange = () => { body.classList.toggle('ui-help-open', helpInput.checked); storage.set('nelyio-help', helpInput.checked ? '1' : '0'); };
  helpLine.append(helpInput, document.createTextNode('Afficher les explications'));
  appearancePanel.append(helpLine); appearance.append(appearanceSummary, appearancePanel);
  one('.top-actions').append(appearance);
  document.addEventListener('click', e => {
    if (!appearance.contains(e.target)) appearance.open = false;
    const agents = one('#details-agent-dropdown');
    if (agents && !agents.contains(e.target)) agents.open = false;
  });
  document.addEventListener('keydown', e => {
    if (e.key !== 'Escape') return;
    if (appearance.open) { appearance.open = false; appearanceSummary.focus(); }
    const agents = one('#details-agent-dropdown');
    if (agents?.open) { agents.open = false; one('summary', agents)?.focus(); }
  });

  function ensureDetailsFilters() {
    const form = one('#details-filters');
    if (!form || form.dataset.responsiveReady) return;
    form.dataset.responsiveReady = '1';
    const head = create('div', 'ui-filter-header');
    const desc = create('div'); desc.append(create('strong', '', 'Filtres'));
    const actions = create('div', 'ui-filter-actions');
    const advanced = button('Plus de filtres', 'ui-filter-action');
    const collapse = button('R\u00e9duire', 'ui-filter-action');
    advanced.setAttribute('aria-expanded', 'false'); collapse.setAttribute('aria-expanded', 'true');
    actions.append(advanced, collapse); head.append(desc, actions); form.prepend(head);
    ['client', 'q'].forEach(name => form.elements[name]?.closest('label')?.classList.add('ui-filter-advanced-field'));
    const agentField = one('.details-agent-filter', form);
    agentField?.prepend(create('span', 'details-agent-label', 'Agents'));
    const submitRow = create('div', 'ui-filter-submit-row');
    const apply = one('.details-apply', form), reset = one('#details-reset', form);
    submitRow.append(apply, reset); form.append(submitRow);
    advanced.onclick = () => {
      form.classList.toggle('ui-filter-show-advanced');
      advanced.setAttribute('aria-expanded', String(form.classList.contains('ui-filter-show-advanced')));
      text(advanced, form.classList.contains('ui-filter-show-advanced') ? 'Moins de filtres' : 'Plus de filtres');
    };
    collapse.onclick = () => {
      form.classList.toggle('ui-filter-collapsed');
      text(collapse, form.classList.contains('ui-filter-collapsed') ? 'Modifier les filtres' : 'R\u00e9duire');
      collapse.setAttribute('aria-expanded', String(!form.classList.contains('ui-filter-collapsed')));
    };
    form.addEventListener('submit', () => {
      form.classList.add('ui-filter-collapsed');
      text(collapse, 'Modifier les filtres'); collapse.setAttribute('aria-expanded', 'false');
      const agents = one('#details-agent-dropdown'); if (agents) agents.open = false;
      schedule();
    });
  }
  function filterSummary(form) {
    const pieces = [], selectedAgents = all('input[name=agent]:checked', form);
    for (const el of Array.from(form.elements)) {
      if (!el.name || ['button','submit','reset','checkbox','radio'].includes(el.type) || el.closest('.details-agent-popover')) continue;
      if (!el.value || el.tagName === 'BUTTON') continue;
      let label = el.labels?.[0]?.childNodes[0]?.textContent?.trim() || '';
      let value = el.tagName === 'SELECT' ? el.selectedOptions[0]?.textContent : el.value;
      if (el.tagName === 'SELECT' && el.value === el.options[0]?.value && !(form.id==='details-filters' && el.name==='source')) continue;
      if (el.type === 'date') value = el.value.split('-').reverse().join('/');
      if (el.type === 'password') continue;
      pieces.push(label ? `${label} : ${value}` : value);
    }
    const checked = all('input[type=checkbox]:checked', form).filter(el => el.name !== 'agent');
    checked.forEach(el => pieces.push(el.closest('label')?.textContent.trim() || el.name));
    if (selectedAgents.length) pieces.push(`${selectedAgents.length} agent(s)`);
    return pieces.join(' \u00b7 ') || 'Tous les r\u00e9sultats';
  }
  function updateFilters() {
    all('.ui-filter-header', app).forEach(head => {
      const box = head.parentElement;
      const form = box.tagName === 'FORM' ? box : one('form', box);
      if (!form) return;
      let summary = one('.ui-filter-summary', head);
      if (!summary) { summary = create('span', 'ui-filter-summary'); head.firstElementChild.append(summary); }
      const value = filterSummary(form); text(summary, value); summary.title = value;
      const buttons = all('.ui-filter-action', head);
      if (buttons[0]) {
        const expanded = box.classList.contains('ui-filter-show-advanced');
        const count = all('.ui-filter-advanced-field input,.ui-filter-advanced-field select,input.ui-filter-advanced-field,select.ui-filter-advanced-field', form).filter(el => {
          if (el.type === 'checkbox' || el.type === 'radio') return el.checked;
          if (el.tagName === 'SELECT') return !!el.value && el.value !== el.options[0]?.value;
          return !!el.value && el.value !== el.defaultValue;
        }).length;
        buttons[0].setAttribute('aria-expanded', String(expanded));
        text(buttons[0], (expanded ? 'Moins de filtres' : 'Plus de filtres') + (count ? ` (${count})` : ''));
      }
      if (buttons[1]) buttons[1].setAttribute('aria-expanded', String(!box.classList.contains('ui-filter-collapsed')));
      if (!form.dataset.responsiveSummary) {
        form.dataset.responsiveSummary = '1';
        form.addEventListener('change', schedule); form.addEventListener('input', schedule);
        form.addEventListener('reset', () => setTimeout(schedule, 0));
        form.addEventListener('submit', () => setTimeout(schedule, 65));
      }
    });
  }

  // Column controls work on visible HTML only, without dropping fields from API data.
  function automaticColumns(state) {
    const n = state.headers.length;
    if (state.table.classList.contains('details-table')) {
      if (innerWidth < 760) return [0,1,5,6];
      if (innerWidth < 1280) return [0,1,3,5,6];
    }
    return Array.from({length: n}, (_, i) => i);
  }
  function selectedColumns(state) {
    const required = state.headers.flatMap((header, i) => header.hasAttribute('data-required-column') ? [i] : []);
    return Array.from(new Set([...(state.selection || automaticColumns(state)), ...required])).sort((a, b) => a - b);
  }
  function applyColumns(state) {
    const selected = selectedColumns(state), selectedSet = new Set(selected);
    state.headers.forEach((h, i) => h.classList.toggle('ui-column-hidden', !selectedSet.has(i)));
    for (const row of Array.from(state.table.tBodies).flatMap(tb => Array.from(tb.rows))) {
      const cells = Array.from(row.cells);
      if (cells.length === state.headers.length && cells.every(c => c.colSpan === 1)) {
        cells.forEach((cell, i) => cell.classList.toggle('ui-column-hidden', !selectedSet.has(i)));
      } else if (cells.length === 1 && cells[0].colSpan > 1) cells[0].colSpan = selected.length;
    }
    text(state.btn, selected.length === state.headers.length ? 'Colonnes' : `Colonnes ${selected.length}/${state.headers.length}`);
    state.btn.setAttribute('aria-label', `Choisir les colonnes : ${selected.length} sur ${state.headers.length} affich\u00e9es`);
    requestAnimationFrame(() => updateTableHint(state));
  }
  // Meme guidage pour les colonnes et les onglets : visible seulement en debordement.
  // Le defilement reste natif (tactile, molette, clavier) ; aucune donnee n'est retiree.
  function scrollControls(region, host, hint, kind) {
    let state = overflowStates.get(region);
    if (state) return state;
    if (!region.id) region.id = 'ui-scroll-region-' + (++serial);
    const controls = create('span', 'ui-scroll-buttons');
    const prev = button('\u2190', 'ui-scroll-button');
    const next = button('\u2192', 'ui-scroll-button');
    const noun = kind === 'tabs' ? 'onglets' : 'colonnes';
    prev.setAttribute('aria-label', 'Afficher les ' + noun + (kind === 'tabs' ? ' pr\u00e9c\u00e9dents' : ' pr\u00e9c\u00e9dentes'));
    next.setAttribute('aria-label', 'Afficher les ' + noun + (kind === 'tabs' ? ' suivants' : ' suivantes'));
    for (const b of [prev, next]) b.setAttribute('aria-controls', region.id);
    controls.append(prev, next); host.append(controls);
    state = {region, host, hint, controls, prev, next, kind};
    overflowStates.set(region, state);
    const move = direction => region.scrollBy({left: direction * Math.max(120, region.clientWidth * .8),
      behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth'});
    prev.onclick = () => move(-1); next.onclick = () => move(1);
    region.addEventListener('scroll', () => updateScrollControls(state), {passive: true});
    region.addEventListener('focusin', e => {
      if (e.target !== region) e.target.scrollIntoView({block: 'nearest', inline: 'nearest'});
    });
    return state;
  }
  function updateScrollControls(state) {
    const {region, host, hint, controls, prev, next, kind} = state;
    if (!region.isConnected || !region.getClientRects().length) return;
    const overflow = region.scrollWidth > region.clientWidth + 2;
    controls.hidden = !overflow;
    prev.disabled = !overflow || region.scrollLeft <= 2;
    next.disabled = !overflow || region.scrollLeft + region.clientWidth >= region.scrollWidth - 2;
    if (kind === 'tabs') {
      host.hidden = !overflow;
      text(hint, overflow ? 'Autres onglets \u2192' : '');
      region.setAttribute('aria-describedby', hint.id);
    } else {
      region.tabIndex = overflow ? 0 : -1;
      const base = region.querySelector('.details-table') ? 'Une ligne = tous les d\u00e9tails' : '';
      text(hint, [base, overflow ? 'D\u00e9filer horizontalement \u2192' : ''].filter(Boolean).join(' \u00b7 '));
    }
  }
  function updateTableHint(state) {
    if (!state.table.isConnected) return;
    updateScrollControls(scrollControls(state.wrap, state.toolbar, state.hint, 'table'));
  }
  function enhanceOverflowTabs() {
    for (const [region, state] of overflowStates) {
      if (!region.isConnected) { state.host.remove(); overflowStates.delete(region); }
    }
    all('.ui-workspace-tabs,.classification-tabs', app).forEach(region => {
      let state = overflowStates.get(region);
      if (!state) {
        const host = create('div', 'ui-overflow-controls');
        const hint = create('span', 'ui-table-hint'); hint.id = 'ui-scroll-hint-' + (++serial);
        host.append(hint); region.before(host);
        state = scrollControls(region, host, hint, 'tabs');
        if (region.matches('.classification-tabs')) {
          region.addEventListener('keydown', e => {
            if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(e.key)) return;
            const buttons = all('button[data-class-tab]', region), i = buttons.indexOf(e.target);
            if (i < 0) return;
            const j = e.key === 'Home' ? 0 : e.key === 'End' ? buttons.length - 1 :
              (i + (e.key === 'ArrowRight' ? 1 : -1) + buttons.length) % buttons.length;
            e.preventDefault(); buttons[j].focus(); buttons[j].click();
          });
        }
      }
      updateScrollControls(state);
    });
  }
  function pinRowActions(table) {
    // Deux tables d'investigation : conserver le vrai bouton et son gestionnaire.
    if (!table.querySelector('[data-call-details],.diag-row-open[data-diag-agent],.cons-edit,.cons-toggle')) return;
    const count = table.tHead?.rows[0]?.cells.length;
    if (!count) return;
    for (const row of table.rows) {
      if (row.cells.length === count && row.cells[count - 1].colSpan === 1) {
        row.cells[count - 1].classList.add('ui-action-cell');
      }
    }
  }
  function openColumns(state) {
    one('#ui-columns-dialog')?.remove();
    const dialog = create('dialog', 'ui-columns-dialog'); dialog.id = 'ui-columns-dialog';
    dialog.setAttribute('aria-labelledby', 'ui-columns-title');
    const header = create('div', 'details-dialog-head'), title = create('h3', '', 'Colonnes du tableau');
    title.id = 'ui-columns-title'; const close = button('\u00d7', 'details-dialog-close'); close.setAttribute('aria-label', 'Fermer');
    header.append(title, close); dialog.append(header);
    const options = create('div', 'ui-column-options');
    const status = create('p', 'muted'); status.setAttribute('role', 'status');
    const selected = () => selectedColumns(state);
    state.headers.forEach((h, index) => {
      const label = create('label'), input = create('input'); input.type = 'checkbox'; input.value = String(index);
      input.checked = selected().includes(index);
      input.disabled = h.hasAttribute('data-required-column');
      if (input.disabled) input.title = 'Information essentielle de la recherche d’appels';
      input.onchange = () => {
        const columns = all('input:checked', options).map(el => Number(el.value));
        if (!columns.length) { input.checked = true; text(status, 'Conservez au moins une colonne.'); return; }
        state.selection = columns; storage.set(state.key, JSON.stringify(columns)); applyColumns(state); text(status, '');
      };
      label.append(input, document.createTextNode(h.textContent.trim() || 'Actions')); options.append(label);
    });
    dialog.append(options, status);
    const actions = create('div', 'ui-dialog-actions'), auto = button('Automatique'), full = button('Tout afficher'), done = button('Fermer', 'button');
    const refresh = () => all('input', options).forEach(el => { el.checked = selected().includes(Number(el.value)); });
    auto.onclick = () => { state.selection = null; storage.remove(state.key); applyColumns(state); refresh(); text(status, 'Colonnes adapt\u00e9es \u00e0 la largeur de l\u2019\u00e9cran.'); };
    full.onclick = () => { state.selection = state.headers.map((_, i) => i); storage.set(state.key, JSON.stringify(state.selection)); applyColumns(state); refresh(); text(status, 'Toutes les colonnes sont visibles.'); };
    close.onclick = done.onclick = () => dialog.close();
    actions.append(auto, full, done); dialog.append(actions); body.append(dialog);
    dialog.addEventListener('close', () => { state.btn.focus(); dialog.remove(); }, {once: true});
    dialog.showModal();
  }
  function enhanceTables() {
    for (const [table] of tableStates) if (!table.isConnected) tableStates.delete(table);
    all('table', app).forEach((table, index) => {
      const headers = all('thead > tr:first-child > th', table);
      if (!headers.length) return;
      let wrap = table.parentElement;
      if (!wrap.matches('.table-wrap,.details-table-wrap,.analytics-table-scroll,.ui-data-scroll,.diag-table-wrap')) {
        wrap = create('div', 'ui-data-scroll'); table.before(wrap); wrap.append(table);
      }
      wrap.setAttribute('role', 'region'); wrap.setAttribute('aria-label', 'Tableau - ' + (one('#page-title')?.textContent || 'Donn\u00e9es'));
      headers.forEach(h => h.setAttribute('scope', 'col'));
      pinRowActions(table);
      if (headers.length < 4 || headers.some(h => h.colSpan !== 1) || all('thead > tr', table).length !== 1) return;
      let state = tableStates.get(table);
      if (!state || state.headers[0] !== headers[0]) {
        if (state) state.toolbar.remove();
        const key = `nelyio-columns-v1:${view()}:${index}:${headers.map(h => h.textContent.trim()).join('|')}`;
        let selection = null;
        try {
          const saved = JSON.parse(storage.get(key, 'null'));
          if (Array.isArray(saved) && saved.length && saved.every(i => Number.isInteger(i) && i >= 0 && i < headers.length)) selection = saved;
        } catch { /* Ignore invalid local preference. */ }
        const tools = create('div', 'ui-table-tools'), hint = create('span', 'ui-table-hint'), btn = button('Colonnes', 'ui-filter-action');
        tools.append(hint, btn);
        const toolbar = create('div', 'ui-table-toolbar'); toolbar.append(tools); wrap.before(toolbar);
        const scrollState = overflowStates.get(wrap);
        if (scrollState) { scrollState.host = toolbar; scrollState.hint = hint; toolbar.append(scrollState.controls); }
        state = {table, headers, wrap, tools, toolbar, hint, btn, key, selection};
        btn.onclick = () => openColumns(state); tableStates.set(table, state);
      }
      applyColumns(state);
    });
  }
  function enhanceSections() {
    all('.ui-workspace-tabs', app).forEach(nav => {
      nav.setAttribute('role', 'tablist');
      all('button[data-ui-workspace]', nav).forEach(b => {
        b.setAttribute('role', 'tab'); b.setAttribute('aria-selected', String(b.classList.contains('active')));
      });
      if (!nav.dataset.responsiveReady) {
        nav.dataset.responsiveReady = '1';
        nav.addEventListener('click', e => {
          const b = e.target.closest('button[data-ui-workspace]');
          if (!b) return;
          storage.set('nelyio-section:' + view(), b.dataset.uiWorkspace);
          b.scrollIntoView({block: 'nearest', inline: 'nearest'}); schedule();
        });
        nav.addEventListener('keydown', e => {
          if (!['ArrowRight','ArrowLeft','Home','End'].includes(e.key)) return;
          const buttons = all('button', nav).filter(b => !b.hidden), i = buttons.indexOf(document.activeElement);
          if (i < 0) return;
          const next = e.key === 'Home' ? 0 : e.key === 'End' ? buttons.length - 1 : (i + (e.key === 'ArrowRight' ? 1 : -1) + buttons.length) % buttons.length;
          e.preventDefault(); buttons[next].focus(); buttons[next].click();
        });
        // A search page always opens its results, even with an old Summary preference.
        const saved = view() === 'calls' ? 'results' : storage.get('nelyio-section:' + view());
        const target = all('button[data-ui-workspace]', nav).find(b => !b.hidden && b.dataset.uiWorkspace === saved);
        if (target && !target.classList.contains('active')) target.click();
      }
    });
    all('.ui-collapse-button', app).forEach(b => b.setAttribute('aria-expanded', String(!b.closest('section')?.classList.contains('ui-panel-collapsed'))));
    all('dialog', app).forEach(d => {
      if (d.hasAttribute('aria-labelledby')) return;
      const title = one('h2,h3', d); if (!title) return;
      if (!title.id) title.id = 'ui-dialog-heading-' + (++serial);
      d.setAttribute('aria-labelledby', title.id);
    });
    // Support's import shortcut must select its workspace before opening it.
    const importButton = one('#support-import-open');
    if (importButton && !importButton.dataset.responsiveReady) {
      importButton.dataset.responsiveReady = '1';
      importButton.addEventListener('click', () => {
        one('[data-ui-workspace="signals"]', app)?.click();
        const panel = one('#support-import-panel'); if (panel) { panel.open = true; panel.scrollIntoView({block: 'nearest'}); }
      }, true);
    }
  }
  function enhance() {
    scheduled = false;
    if (lastView !== view()) { lastView = view(); body.dataset.uiView = lastView; setMenu(false, false); }
    all('.sidebar a[data-view]').forEach(a => {
      if (a.classList.contains('active')) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current');
    });
    const user = one('#user-pill'); if (user) user.title = user.textContent;
    ensureDetailsFilters(); updateFilters(); enhanceSections(); enhanceTables(); enhanceOverflowTabs();
  }
  function schedule() { if (!scheduled) { scheduled = true; requestAnimationFrame(enhance); } }
  new MutationObserver(schedule).observe(app, {childList: true, subtree: true});
  app.addEventListener('click', schedule);
  window.addEventListener('resize', schedule);
  window.addEventListener('hashchange', () => { setMenu(false, false); schedule(); });
  if ('ResizeObserver' in window) new ResizeObserver(schedule).observe(main);
  schedule();
})();
