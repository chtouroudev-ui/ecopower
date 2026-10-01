const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];
const app = $('#app');
let currentUser = null;
let csrfToken = "";
// A slow response must not replace the screen selected in the meantime.
let routeRevision=0;
let routeAbortController=null;
function captureViewTicket(){return {revision:routeRevision,hash:location.hash,user:currentUser};}
function viewTicketIsCurrent(t){return t.revision===routeRevision&&t.hash===location.hash&&t.user===currentUser&&!!currentUser;}
let followupUiConfig={warning_days:7,late_days:20,labels:{EN_SERVICE:"À jour",PAS_A_JOUR:"Pas à jour",RETARD_7J:"Retard",CRITIQUE:"Critique",STOCK:"En stock",REPARATION:"Réparation",KO:"KO / perdu",REFORME:"Réformé"}};
function setFollowupConfig(c){if(c&&typeof c==='object')followupUiConfig={...followupUiConfig,...c,labels:{...followupUiConfig.labels,...(c.labels||{})}};}

const esc = s => String(s ?? '').replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
const show = (el, yes=true) => el && el.classList.toggle('hidden', !yes);
const fmt = s => s ? String(s).replace('T',' ') : '—';

function siteBadge(site){
  return `<span class="badge ${site==='SUR SITE'?'b-site':site==='TELETRAVAIL'?'b-remote':'b-unknown'}"><i></i>${esc(site || 'INCONNU')}</span>`;
}
function groupBadge(name){return name?`<span class="group-badge">${esc(name)}</span>`:'<span class="muted">Non classé</span>';}
function userDisplay(display, raw){
  const d=String(display||'').trim(), r=String(raw||'').trim();
  if(!d && !r) return '<span class="muted">—</span>';
  if(d && r && d!==r) return `<strong class="user-display-name">${esc(d)}</strong><small class="sub mono">${esc(r)}</small>`;
  return `<strong>${esc(d||r)}</strong>`;
}
function siteReason(r){return r?`<small class="site-reason">${esc(r)}</small>`:'';}
function freshnessMeta(status){
  const defaults={EN_SERVICE:'green',PAS_A_JOUR:'yellow',RETARD_7J:'orange',CRITIQUE:'red',STOCK:'blue',REPARATION:'orange',KO:'red',REFORME:'gray'};
  const color=followupUiConfig.colors?.[status]||defaults[status]||'gray';
  const safe=['green','yellow','orange','red','blue','purple','gray'].includes(color)?color:'gray';
  return [followupUiConfig.labels?.[status]||'Suivi inconnu','fresh-'+safe];
}
function ageText(days,status){
  if(days===null || days===undefined || days==='') return 'Jamais vu';
  const n=Number(days); if(!Number.isFinite(n)) return 'Jamais vu';
  if(n<=0) return "Vu aujourd'hui"; if(n===1) return 'Vu il y a 1 jour'; return `Vu il y a ${n} jours`;
}
function freshnessBadge(status,days){const [label,cls]=freshnessMeta(status); return `<span class="fresh-badge ${cls}">${esc(label)}</span><small class="fresh-age">${esc(ageText(days,status))}</small>`;}
function adminStatus(status){
  const labels={EN_SERVICE:'En service',STOCK:'En stock',REPARATION:'En réparation',REFORME:'Réformé',PERDU:'Perdu'};
  const cls={EN_SERVICE:'admin-service',STOCK:'admin-stock',REPARATION:'admin-repair',REFORME:'admin-retired',PERDU:'admin-lost'}[status]||'';
  return `<span class="admin-status ${cls}">${esc(labels[status]||status||'En service')}</span>`;
}
function manualFlag(r){return r.created_manually?'<span class="manual-badge">Ajout manuel</span>':r.has_manual_override?'<span class="manual-badge subtle">Surcharge manuelle</span>':'';}
function shortNote(v){v=String(v||'').trim(); return v ? esc(v.length>72?v.slice(0,72)+'…':v) : '<span class="muted">—</span>';}
const pageDisplayNames={"Declarations":"D\u00e9clarations","Policies Nelyio": "R\u00e8gles d\u2019analyse", "Priorit\u00e9s Support": "Niveaux d\u2019alerte", "R\u00e8gles de tri": "R\u00e8gles de classement", "D\u00e9tails": "Journal d\u00e9taill\u00e9", "D\u00e9tails Nelyio": "Journal d\u00e9taill\u00e9", "Diagnostic Nelyio": "Diagnostic technique", "Analyse & tendances": "Tendances techniques", "Parc informatique": "Ordinateurs", "Groupes": "Groupes et \u00e9quipes"};
function setHead(t,s){$('#page-title').textContent=pageDisplayNames[t]||t; $('#page-sub').textContent=s;}
function activate(v){$$('nav a[data-view]').forEach(a=>{a.classList.toggle('active',a.dataset.view===v);if(a.dataset.view===v)a.setAttribute('aria-current','page');else a.removeAttribute('aria-current');});document.dispatchEvent(new Event('nelyio:navigation'));}
function pcLink(n){return `<a class="link strong" href="#pc/${encodeURIComponent(n)}">${esc(n)}</a>`;}
function flash(text,type='ok'){return `<div class="flash ${type==='error'?'error':type==='warn'?'warn':''}">${esc(text)}</div>`;}

function accessLevel(module){
  if(!currentUser)return 0;
  if(currentUser.role==='admin')return 2;
  return Number((currentUser.permissions||{})[module]||0);
}
function canRead(module){return accessLevel(module)>=1;}
function canWrite(module){return accessLevel(module)>=2;}
const viewInterfaceMap={
  dashboard:'dashboard',inventory:'inventory',consumables:'consumables',add:'inventory_add',
  'live-supervision':'live_supervision','live-campaigns':'live_campaigns','live-incidents':'live_incidents','live-search':'live_search',
  support:'support','disconnect-details':'disconnect_details',calls:'calls',details:'details',analytics:'analytics',reports:'reports',declarations:'declarations',
  'analytics-home':'analytics_home','quality-pilotage':'quality_pilotage','quality-activity':'quality_activity','quality-overview':'quality_overview','quality-distributions':'quality_distributions','suspicious-calls':'suspicious_calls','classification-groups':'classification_groups','quality-agents':'quality_agents','quality-bases':'quality_bases',
  collection:'collection_admin','live-quality-admin':'live_quality_admin','production-health':'production_health',config:'config',classification:'classification','support-priority':'support_priority',policies:'policies',users:'users',security:'security'
};
function interfaceLevel(key){
  if(!currentUser)return 0;
  if(currentUser.role==='admin')return 2;
  return Number((currentUser.interface_permissions||{})[key]||0);
}
function canOpenInterface(key){return interfaceLevel(key)>=1;}
function canWriteInterface(key){return interfaceLevel(key)>=2;}
function interfaceForView(view){return viewInterfaceMap[String(view||'')]||'';}
function groupScopePolicy(){return currentUser?.group_scope||{mode:'SELECTED',allowed_group_ids:[],default_group_id:'',filter_locked:true,all_groups:false};}
function firstAllowedHash(){
  const order=['dashboard','inventory','consumables','add','live-supervision','live-campaigns','live-incidents','live-search','support','disconnect-details','calls','details','analytics','reports','declarations','analytics-home','quality-pilotage','quality-activity','quality-overview','quality-distributions','suspicious-calls','classification-groups','quality-agents','quality-bases','collection','live-quality-admin','production-health','config','classification','support-priority','policies','users','security'];
  for(const v of order){const key=interfaceForView(v);if(key&&canOpenInterface(key))return '#'+v;}
  return '#account';
}
function redirectAllowed(){const h=firstAllowedHash();if(location.hash!==h)location.hash=h;}
function accessLabel(level){return Number(level)>=2?'Modification':Number(level)>=1?'Lecture seule':'Aucun accès';}

async function api(url,opt={}){
  const method=String(opt.method||'GET').toUpperCase();
  const headers=new Headers(opt.headers||{});
  if(!['GET','HEAD','OPTIONS'].includes(method) && url!='/api/login' && csrfToken){headers.set('X-CSRF-Token',csrfToken);}
  const fetchOptions={...opt,headers,credentials:'same-origin'};
  if(method==='GET' && !fetchOptions.signal && routeAbortController) fetchOptions.signal=routeAbortController.signal;
  const r=await fetch(url,fetchOptions);
  let j={}; try{j=await r.json();}catch{throw new Error('Réponse serveur illisible. Vérifiez le backend et le proxy HTTPS.');}
  if(!j||typeof j!=='object')throw new Error('Réponse serveur invalide.');
  if(j.csrf_token) csrfToken=j.csrf_token;
  if(r.status===401 && url!='/api/login'){currentUser=null;csrfToken='';renderAuth();throw new Error('Session expirée ou inactive');}
  if(!r.ok) throw new Error(j.error||'Erreur');
  return j;
}

// Only uploads use this contract. No mutation is retried after a network error.
async function importInBackground(url,opt,selector){
  let result=await api(url,opt);
  const started=Date.now();
  while(['queued','running'].includes(result.status)){
    const host=document.querySelector(selector);
    const steps=Object.entries(result.steps||{}).filter(([,v])=>v.state==='ok').length;
    if(host)host.textContent=result.status==='queued'?'Fichier enregistré · en attente…':`Import en arrière-plan · ${steps} étape(s) terminée(s)… Vous pouvez continuer à naviguer.`;
    if(Date.now()-started>30*60*1000)throw new Error('Import toujours suivi côté serveur. Consultez l’état des imports pour le résultat.');
    await new Promise(resolve=>setTimeout(resolve,2000));
    try{result=await api('/api/supervision/auto-import?job_id='+encodeURIComponent(result.job_id));}
    catch(e){throw new Error(e.message+' · Le fichier est enregistré : consultez l’état des imports avant de réessayer.');}
  }
  if(result.status==='failed')throw new Error(result.error||'Import échoué ; source conservée, reprise disponible.');
  return result;
}

async function initAuth(){
  try{const d=await api('/api/me');currentUser=d.user;csrfToken=d.csrf_token||'';}catch{currentUser=null;csrfToken='';}
  renderAuth();
}
function renderAuth(){
  const authed=!!currentUser;
  show($('#shell'),authed); show($('#login-screen'),!authed);
  if(authed){
    const roleLabel=currentUser.role==='admin'?'Administrateur système':(currentUser.group_name||'Sans groupe');
    $('#user-pill').textContent=`${currentUser.username} · ${roleLabel}`;
    $$('nav a[data-view]').forEach(el=>{const key=interfaceForView(el.dataset.view);show(el,!key||canOpenInterface(key));});
    $$('[data-permission]:not(nav a)').forEach(el=>show(el,el.dataset.write==='1'?canWrite(el.dataset.permission):canRead(el.dataset.permission)));
    const sectionVisible=id=>[...document.querySelectorAll(`#${id} a[data-view]`)].some(a=>!a.classList.contains('hidden'));
    show($('#park-nav'),sectionVisible('park-nav'));show($('#park-nav-label'),sectionVisible('park-nav'));
    show($('#support-nav'),sectionVisible('support-nav'));show($('#support-nav-label'),sectionVisible('support-nav'));
    show($('#quality-nav'),sectionVisible('quality-nav'));show($('#quality-nav-label'),sectionVisible('quality-nav'));
    show($('#admin-nav'),sectionVisible('admin-nav'));show($('#admin-nav-label'),sectionVisible('admin-nav'));
    document.dispatchEvent(new Event('nelyio:navigation'));
    route();
  }
}

$('#login-form').addEventListener('submit',async e=>{
  e.preventDefault(); $('#login-error').textContent='';
  const body=Object.fromEntries(new FormData(e.target));
  try{const d=await api('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});currentUser=d.user;csrfToken=d.csrf_token||'';location.hash='#dashboard';renderAuth();}
  catch(err){$('#login-error').textContent=err.message;}
});
$('#logout').addEventListener('click',async()=>{try{await api('/api/logout',{method:'POST'});}catch{}currentUser=null;csrfToken='';renderAuth();});

// Frontend 1 B : une seule information sur l'accueil, sans nouvelle affectation.
// Le compteur scoped_agents inclut les liens configures/manuels du catalogue.
// unclassified_agent_count ne suffit pas : il ne compte que la regle automatique.
function dashboardGroupNotice(data){
  const total=data?.stats?.agents, linked=data?.group_summary?.scoped_agents;
  if(!Number.isInteger(total)||!Number.isInteger(linked)||total<0||linked<0||linked>total){
    throw new Error('Compteurs de groupes indisponibles');
  }
  const missing=total-linked;
  if(!total||missing/total<0.5)return null;
  const source=data.group_summary.source_day;
  return {total,missing,percent:Math.round(100*missing/total),
    sourceDay:typeof source==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(source)?source:''};
}
async function dashboardLoadGroupNotice(host){
  // Une lecture a chaque ouverture, aucun cache ni timer partage entre utilisateurs.
  if(!host)return;
  host.classList.add('hidden');host.replaceChildren();
  if(!canRead('quality'))return;
  const user=currentUser;
  const active=()=>host.isConnected&&currentUser===user&&canRead('quality')&&
    (!location.hash||location.hash==='#dashboard');
  try{
    const notice=dashboardGroupNotice(await api('/api/groups/status'));
    if(!active()||!notice)return;
    const link=canRead('classification')?'<a href="#classification-groups">Voir les groupes</a>':
      '<a href="#quality-agents">Voir les agents</a>';
    host.innerHTML=`<div class="flash warn"><strong>Groupes d'analyse \u00e0 compl\u00e9ter</strong><p>${notice.missing} sur ${notice.total} agents du catalogue sont sans lien de groupe d'analyse (${notice.percent}\u00a0%).${notice.sourceDay?' Source : '+esc(notice.sourceDay)+'.':''} Les analyses par groupe peuvent \u00eatre incompl\u00e8tes.</p>${link}</div>`;
    host.classList.remove('hidden');
  }catch(_){
    if(!active())return;
    host.textContent='V\u00e9rification des groupes indisponible. Rouvrez l\u2019accueil pour r\u00e9essayer.';
    host.classList.remove('hidden');
  }
}

async function dashboard(){
  const viewTicket=captureViewTicket();
  if(!canRead('dashboard')){redirectAllowed();return;}
  activate('dashboard'); setHead("Vue d'ensemble","État du parc calculé depuis la dernière remontée de chaque PC et enrichi par les informations de gestion.");
  const d=await api('/api/dashboard'); setFollowupConfig(d.followup_config);
  const importLine=d.last_import ? `${d.last_import.status==='OK'?'Dernier import réussi':'Dernier import en erreur'} · ${esc(d.last_import.finished_at||d.last_import.started_at)} · ${Number(d.last_import.imported_rows||0)} nouvelle(s) ligne(s)` : 'Aucun import enregistré';
  if(!viewTicketIsCurrent(viewTicket))return;
  app.innerHTML=`
    <section id="dashboard-group-notice" class="hidden" role="status" aria-live="polite"></section>
    <section class="overview-strip">
      <div><span>Parc total</span><strong>${d.total}</strong><small>${d.manual_only} PC manuel(s) jamais vu(s)</small></div>
      <div><span>Sur site</span><strong>${d.site}</strong><small>classification selon tes règles</small></div>
      <div><span>Télétravail</span><strong>${d.remote}</strong><small>classification selon tes règles</small></div>
      <div><span>Emplacement inconnu</span><strong>${d.unknown}</strong><small>règle ou défaut = inconnu</small></div>
    </section>
    ${InventoryFollowup.dashboard(followupUiConfig.policy||InventoryFollowup.defaults(),d.followup_counts||{})}
    <div class="dashboard-info-grid">
      <div class="card info-card"><div class="info-icon">↻</div><div><strong>Synchronisation diagnostic</strong><span>${importLine}</span></div>${canRead('config')?'<a href="#config">Configurer</a>':''}</div>
      <div class="card info-card"><div class="info-icon">△</div><div><strong>Écarts d'emplacement</strong><span>${d.ecarts} PC avec emplacement attendu différent de la classification actuelle</span></div><a href="#inventory">Ouvrir le parc</a></div>
    </div>
    <div class="rule-banner"><strong>Suivi du parc</strong><span>Calcul selon le dernier diagnostic et le statut administratif.</span>${canRead('classification')?'<a href="#classification?tab=followup">Configurer le suivi</a>':''}</div>
    <div class="grid2">
      <section class="card panel"><div class="panel-head"><div><h2>Derniers PC vus</h2><p>Dernière remontée automatique par machine.</p></div><a class="button ghost" href="#inventory">Voir le parc</a></div>
        <div class="table-wrap"><table><thead><tr><th>PC</th><th>Suivi</th><th>Emplacement</th><th>Groupe</th><th>Affectation</th><th>Dernière vue</th></tr></thead><tbody>
        ${d.recent.map(r=>`<tr><td>${pcLink(r.ordinateur)} ${manualFlag(r)}</td><td>${freshnessBadge(r.suivi_statut,r.jours_depuis_vue)}</td><td>${siteBadge(r.site_actuel)}</td><td>${groupBadge(r.groupe_utilisateur)}</td><td>${esc(r.affectation||'—')}</td><td>${esc(r.date_evenement||'Jamais')}</td></tr>`).join('')||'<tr><td colspan="6" class="empty">Aucun PC.</td></tr>'}</tbody></table></div>
      </section>
      <section class="card panel"><div class="panel-head"><div><h2>Mobilité détectée</h2><p>PC ayant été observés via DC1 et DC2.</p></div></div>
        <div class="timeline-list">${d.transitions.map(r=>`<a href="#pc/${encodeURIComponent(r.ordinateur)}"><div><strong>${esc(r.ordinateur)}</strong><small>${esc(r.sites)}</small></div><span>${esc(r.derniere_vue)}</span></a>`).join('')||'<p class="muted">Aucun changement détecté.</p>'}</div>
      </section>
    </div>`;
  dashboardLoadGroupNotice($('#dashboard-group-notice'));
}

async function inventory(initialQuery=""){
  const viewTicket=captureViewTicket();
  if(!canRead('inventory')){redirectAllowed();return;}
  activate('inventory'); setHead('Parc informatique','Rechercher et filtrer par IP, passerelle, emplacement, groupe et état administratif.');
  const initial=await api('/api/inventory?q='+encodeURIComponent(initialQuery)); setFollowupConfig(initial.followup_config);
  const groupOptions=initial.groups.map(g=>`<option value="${g.id}">${esc(g.name)}</option>`).join('');
  if(!viewTicketIsCurrent(viewTicket))return;
  app.innerHTML=`
    <section class="card filter-card">
      <form id="filters" class="filters filters-wide">
        <div class="search-wrap"><span>⌕</span><input name="q" value="${esc(initialQuery)}" placeholder="PC, utilisateur, nom, groupe, affectation, note…"></div>
        <input name="ip" class="net-filter" placeholder="IP, CIDR ou range…">
        <input name="gateway" class="net-filter" placeholder="Passerelle, CIDR ou range…">
        <select name="freshness"><option value="">Tous les suivis</option>${InventoryFollowup.filterOptions(followupUiConfig.policy||InventoryFollowup.defaults())}</select>
        <select name="site"><option value="">Tous les emplacements</option><option value="SUR SITE">Sur site</option><option value="TELETRAVAIL">Télétravail</option><option value="INCONNU">Inconnu</option></select>
        <select name="group"><option value="">Tous les groupes</option>${groupOptions}</select>
        <select name="status"><option value="">Tous les états admin.</option><option value="EN_SERVICE">En service</option><option value="STOCK">En stock</option><option value="REPARATION">Réparation</option><option value="REFORME">Réformé</option><option value="PERDU">Perdu</option></select>
        <button class="button">Filtrer</button><button type="button" id="reset" class="button ghost">Effacer</button>
      </form>
      <div class="network-help"><strong>Filtres réseau :</strong> IP exacte <code>192.168.100.25</code>, CIDR <code>192.168.100.0/24</code> ou intervalle <code>192.168.100.20-80</code>.</div>
    </section>
    <section class="card panel inventory-panel"><div class="panel-head"><div><h2 id="count">PC</h2><p>Une ligne représente l'état actuel consolidé du poste.</p></div><div class="actions">${canWrite('inventory')?'<a class="button" href="#add">+ Ajouter un PC</a>':''}<a class="button ghost" href="/api/export.csv">Exporter CSV</a></div></div>
      <div class="table-wrap"><table><thead><tr><th>PC</th><th>Suivi</th><th>Emplacement</th><th>Groupe</th><th>État administratif</th><th>Affectation</th><th>Note</th><th>Utilisateur / IP</th><th>Dernière vue</th></tr></thead><tbody id="inv-body"></tbody></table></div>
    </section>`;
  function renderRows(d){
    $('#count').textContent=d.count+' PC';
    $('#inv-body').innerHTML=d.rows.map(r=>`<tr class="${r.emplacement_ecart?'row-alert':''}">
      <td>${pcLink(r.ordinateur)}<div class="cell-flags">${r.asset_tag?`<small class="asset-tag">${esc(r.asset_tag)}</small>`:''}${manualFlag(r)}</div></td>
      <td>${freshnessBadge(r.suivi_statut,r.jours_depuis_vue)}</td>
      <td>${siteBadge(r.site_actuel)}${siteReason(r.site_reason)}${r.emplacement_ecart?'<small class="warning">Attendu différent</small>':''}</td>
      <td>${groupBadge(r.groupe_utilisateur)}</td>
      <td>${adminStatus(r.statut)}</td><td>${esc(r.affectation||'—')}</td><td class="note-cell">${shortNote(r.notes)}</td>
      <td>${userDisplay(r.utilisateur_affiche,r.utilisateur)}<small class="sub">${esc(r.adresse_ip||'IP inconnue')} · GW ${esc(r.passerelle||'—')}</small></td><td>${esc(r.date_evenement||'Jamais vu')}</td>
    </tr>`).join('')||'<tr><td colspan="9" class="empty">Aucun résultat.</td></tr>';
  }
  async function load(){const p=new URLSearchParams(new FormData($('#filters'))); const data=await api('/api/inventory?'+p);setFollowupConfig(data.followup_config);renderRows(data);}
  $('#filters').onsubmit=e=>{e.preventDefault();load();}; $('#reset').onclick=()=>{$('#filters').reset();load();}; renderRows(initial);
}

const adminOptions = value => [['EN_SERVICE','En service'],['STOCK','En stock'],['REPARATION','En réparation'],['REFORME','Réformé'],['PERDU','Perdu']].map(([v,l])=>`<option value="${v}" ${value===v?'selected':''}>${l}</option>`).join('');
const locOptions = value => `<option value="">Non défini</option><option value="SUR SITE" ${value==='SUR SITE'?'selected':''}>Sur site</option><option value="TELETRAVAIL" ${value==='TELETRAVAIL'?'selected':''}>Télétravail</option>`;

async function detail(name){
  const viewTicket=captureViewTicket();
  if(!canRead('inventory')){redirectAllowed();return;}
  activate(''); const d=await api('/api/pc?name='+encodeURIComponent(name)); const p=d.pc; setFollowupConfig(d.followup_config);
  setHead(p.ordinateur,'Fiche complète du poste, données automatiques, groupe utilisateur, gestion manuelle et historique.');
  if(!viewTicketIsCurrent(viewTicket))return;
  app.innerHTML=`
    <section class="card pc-hero">
      <div class="pc-title"><div class="pc-avatar">PC</div><div><div class="hero-badges">${freshnessBadge(p.suivi_statut,p.jours_depuis_vue)} ${siteBadge(p.site_actuel)} ${groupBadge(p.groupe_utilisateur)} ${manualFlag(p)}</div><h2>${esc(p.ordinateur)}</h2><p>${esc(p.fabricant||'Fabricant inconnu')} · ${esc(p.modele||'Modèle inconnu')}</p></div></div>
      <div class="pc-management-summary"><div><small>État administratif</small>${adminStatus(p.statut)}</div><div><small>Affectation</small><strong>${esc(p.affectation||'Non affecté')}</strong></div><div><small>Groupe</small><strong>${esc(p.groupe_utilisateur||'Non classé')}</strong></div><div><small>Asset tag</small><strong>${esc(p.asset_tag||'—')}</strong></div></div>
    </section>
    <div class="grid2">
      <section class="card panel"><div class="panel-head"><div><h2>État actuel</h2><p>Dernières données disponibles et résultat des règles de classification.</p></div></div>
        <dl class="specs">
          <dt>Utilisateur</dt><dd>${userDisplay(p.utilisateur_affiche,p.utilisateur)}</dd><dt>Groupe utilisateur</dt><dd>${groupBadge(p.groupe_utilisateur)}</dd><dt>Adresse IP</dt><dd>${esc(p.adresse_ip||'—')}</dd><dt>Passerelle</dt><dd>${esc(p.passerelle||'—')}</dd><dt>MAC</dt><dd>${esc(p.adresse_mac||'—')}</dd><dt>N° série PC</dt><dd>${esc(p.sn_pc||'—')}</dd><dt>Carte mère</dt><dd>${esc(p.sn_carte_mere||'—')}</dd><dt>Domaine</dt><dd>${esc(p.domaine||'—')}</dd><dt>Windows</dt><dd>${esc(p.version_windows||p.windows||'—')}</dd><dt>Collecteur</dt><dd>${esc(p.collecteur||'—')}</dd><dt>Emplacement calculé</dt><dd>${siteBadge(p.site_actuel)}${siteReason(p.site_reason)}</dd><dt>Dernière vue</dt><dd>${esc(p.date_evenement||'Jamais')}</dd><dt>Note</dt><dd class="note-value">${esc(p.notes||'—')}</dd>
        </dl>
      </section>
      <section class="card panel"><div class="panel-head"><div><h2>Gestion manuelle</h2><p>${canWrite('inventory')?"Les changements sont historisés avec l'utilisateur connecté.":"Consultation uniquement : votre groupe dispose du droit Lecture seule."}</p></div></div>
        ${canWrite('inventory')?`<form id="manage" class="manage-form">
          <label>Asset tag<input name="asset_tag" value="${esc(p.asset_tag)}"></label><label>État administratif<select name="statut">${adminOptions(p.statut)}</select></label>
          <label>Affectation<input name="affectation" value="${esc(p.affectation)}" placeholder="Agent / service"></label><label>Emplacement attendu<select name="emplacement_attendu">${locOptions(p.emplacement_attendu)}</select></label>
          <label class="full">Note<textarea name="notes" rows="4">${esc(p.notes)}</textarea></label>
          <div class="form-divider full"><strong>Surcharge technique manuelle</strong><span>La donnée automatique reste conservée dans l'historique. Le groupe est calculé depuis l'utilisateur selon la configuration des groupes.</span></div>
          <label>Utilisateur manuel<input name="manual_utilisateur" value="${esc(p.manual_utilisateur)}"></label><label>IP manuelle<input name="manual_ip" value="${esc(p.manual_ip)}"></label>
          <label>MAC manuelle<input name="manual_mac" value="${esc(p.manual_mac)}"></label><label>N° série PC<input name="manual_sn_pc" value="${esc(p.manual_sn_pc)}"></label>
          <label>N° série carte mère<input name="manual_sn_carte_mere" value="${esc(p.manual_sn_carte_mere)}"></label><label>Domaine<input name="manual_domaine" value="${esc(p.manual_domaine)}"></label>
          <label>Fabricant<input name="manual_fabricant" value="${esc(p.manual_fabricant)}"></label><label>Modèle<input name="manual_modele" value="${esc(p.manual_modele)}"></label>
          <label>Windows<input name="manual_windows" value="${esc(p.manual_windows)}"></label><label>Version Windows<input name="manual_version_windows" value="${esc(p.manual_version_windows)}"></label>
          <div class="full form-actions"><button class="button">Enregistrer</button><span id="saved" class="form-result"></span></div>
        </form>`:`<div class="readonly-box"><strong>Mode lecture seule</strong><span>Tu peux consulter toutes les données et l'historique mais pas modifier ce PC.</span></div>`}
      </section>
    </div>
    <section class="card panel"><div class="panel-head"><div><h2>Historique des changements manuels</h2><p>Traçabilité : utilisateur, date, champ, ancienne et nouvelle valeur.</p></div></div>
      <div class="table-wrap"><table><thead><tr><th>Date</th><th>Utilisateur</th><th>IP source</th><th>Action</th><th>Champ</th><th>Avant</th><th>Après</th></tr></thead><tbody>${d.audit.map(a=>`<tr><td>${esc(a.created_at)}</td><td><span class="user-tag">${esc(a.username)}</span></td><td><code>${esc(a.source_ip||'—')}</code></td><td>${esc(a.action)}</td><td>${esc(a.field_name||'—')}</td><td>${esc(a.old_value||'—')}</td><td>${esc(a.new_value||'—')}</td></tr>`).join('')||'<tr><td colspan="7" class="empty">Aucune modification manuelle enregistrée.</td></tr>'}</tbody></table></div>
    </section>
    <section class="card panel"><div class="panel-head"><div><h2>Historique automatique</h2><p>${d.history.length} diagnostic(s) importé(s) et reclassés selon les règles actuelles.</p></div></div>
      <div class="table-wrap"><table><thead><tr><th>Date</th><th>Emplacement</th><th>Règle</th><th>Collecteur</th><th>Utilisateur</th><th>Groupe</th><th>IP</th><th>Passerelle</th><th>Windows</th></tr></thead><tbody>${d.history.map(h=>`<tr><td>${esc(h.date_evenement)}</td><td>${siteBadge(h.site)}</td><td>${esc(h.site_reason||'—')}</td><td>${esc(h.collecteur||'—')}</td><td>${userDisplay(h.utilisateur_affiche,h.utilisateur)}</td><td>${groupBadge(h.groupe_utilisateur)}</td><td>${esc(h.adresse_ip||'—')}</td><td>${esc(h.passerelle||'—')}</td><td>${esc(h.version_windows||h.windows||'—')}</td></tr>`).join('')||'<tr><td colspan="9" class="empty">Jamais vu automatiquement.</td></tr>'}</tbody></table></div>
    </section>`;
  if($('#manage')) $('#manage').onsubmit=async e=>{e.preventDefault(); const body=Object.fromEntries(new FormData(e.target)); body.ordinateur=name; try{const r=await api('/api/manage',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}); $('#saved').textContent=`Enregistré par ${r.updated_by} · ${r.changes} changement(s)`; setTimeout(()=>detail(name),700);}catch(err){$('#saved').textContent=err.message;}};
}

function addPc(){
  if(!canWrite('inventory')){redirectAllowed();return;}
  activate('add'); setHead('Ajouter un PC','Créer un poste manuellement avant sa première remontée automatique.');
  app.innerHTML=`<section class="card panel form-page"><div class="form-intro"><div class="form-icon">＋</div><div><h2>Nouveau poste</h2><p>L'ajout sera signé par <strong>${esc(currentUser.username)}</strong>. Sans diagnostic automatique, le PC apparaîtra en rouge « Critique · Jamais vu ».</p></div></div>
    <form id="add-form" class="manage-form roomy">
      <label>Nom du PC *<input name="ordinateur" required placeholder="SIMPLIFY-150"></label><label>Asset tag<input name="asset_tag" placeholder="TECHIN-PC-150"></label>
      <label>État administratif<select name="statut">${adminOptions('EN_SERVICE')}</select></label><label>Affectation<input name="affectation" placeholder="Agent / service"></label>
      <label>Emplacement attendu<select name="emplacement_attendu">${locOptions('')}</select></label><label>IP manuelle<input name="manual_ip" placeholder="Information réseau"></label>
      <label>Utilisateur<input name="manual_utilisateur"></label><label>MAC<input name="manual_mac"></label><label>N° série PC<input name="manual_sn_pc"></label><label>N° série carte mère<input name="manual_sn_carte_mere"></label>
      <label>Fabricant<input name="manual_fabricant"></label><label>Modèle<input name="manual_modele"></label><label>Windows<input name="manual_windows"></label><label>Domaine<input name="manual_domaine"></label>
      <label class="full">Note<textarea name="notes" rows="5" placeholder="Provenance, état, réparation, observation…"></textarea></label>
      <div class="full form-actions"><button class="button">Ajouter au parc</button><span id="add-result" class="form-result"></span></div>
    </form></section>`;
  $('#add-form').onsubmit=async e=>{e.preventDefault(); const body=Object.fromEntries(new FormData(e.target)); try{const r=await api('/api/pc/add',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}); location.hash='#pc/'+encodeURIComponent(r.ordinateur);}catch(err){$('#add-result').textContent=err.message;}};
}

let usersUiState={tab:'accounts',selectedGroupId:null,selectedUserId:null,selectedUserIds:new Set(),query:'',status:'all',group:'all'};
async function users(){
  const viewTicket=captureViewTicket();
  if(!canOpenInterface('users')){redirectAllowed();return;}
  activate('users');setHead('Utilisateurs & accès','Comptes, groupes, profils et droits effectifs dans une administration simplifiée.');
  const d=await api('/api/users'),editable=canWriteInterface('users');
  if(!viewTicketIsCurrent(viewTicket))return;
  const groupOptions=(includeEmpty=true,selected='')=>`${includeEmpty?'<option value="">Aucun groupe</option>':''}${d.access_groups.map(g=>`<option value="${g.id}" ${String(selected)===String(g.id)?'selected':''}>${esc(g.name)}</option>`).join('')}`;
  const profileOptions=()=>`<option value="">Choisir un profil…</option>${(d.access_profiles||[]).map(p=>`<option value="${p.id}">${esc(p.name)}</option>`).join('')}`;
  const bySection={};(d.interfaces||[]).forEach(x=>(bySection[x.section]||(bySection[x.section]=[])).push(x));
  const businessName=id=>{const g=(d.business_groups||[]).find(x=>String(x.id)===String(id));return g?g.name:String(id||'—');};
  const profileScopeText=p=>{const x=p?.summary||{};if(x.scope_mode!=='SELECTED')return x.default_group_id?`Tous les groupes · défaut : ${businessName(x.default_group_id)}${x.filter_locked?' · verrouillé':''}`:'Tous les groupes';const names=(x.allowed_group_ids||[]).map(businessName);let text=names.length?names.join(', '):'Aucun groupe';if(x.default_group_id)text+=` · défaut : ${businessName(x.default_group_id)}`;if(x.filter_locked)text+=' · verrouillé';return text;};
  const userScopeText=u=>{const p=u.effective_group_scope||{};if(u.role==='admin'||p.all_groups)return 'Tous les groupes';const names=(p.allowed_group_ids||[]).map(businessName);let text=names.length?names.join(', '):'Aucun groupe';if(p.default_group_id)text+=` · défaut : ${businessName(p.default_group_id)}`;if(p.filter_locked)text+=' · verrouillé';return text;};
  const permissionSummary=perm=>{const vals=Object.values(perm||{});return {write:vals.filter(x=>Number(x)>=2).length,read:vals.filter(x=>Number(x)===1).length,none:vals.filter(x=>Number(x)===0).length};};
  const groupSummary=g=>{const s=permissionSummary(g.interface_permissions);const p=g.scope_policy||{};return {rights:`${s.write} modif. · ${s.read} lecture`,scope:p.scope_mode==='SELECTED'?`${(p.allowed_group_ids||[]).length} groupe(s) métier`:'Tous les groupes',locked:!!p.filter_locked};};
  const permissionSections=(perm,interactive=false)=>Object.entries(bySection).map(([section,items])=>{const active=items.filter(m=>Number((perm||{})[m.key]||0)>0).length;return `<details class="access-perm-section"><summary><span>${esc(section)}</span><small>${active}/${items.length} autorisée(s)</small></summary><div class="access-interface-list">${items.map(m=>{const level=Number((perm||{})[m.key]||0),writeOnly=!!m.write_only;return `<label class="access-interface-row"><span><strong>${esc(m.label)}</strong><small>${writeOnly?'Action de modification uniquement':m.write?'Lecture ou modification':'Lecture uniquement'}</small></span>${interactive?`<select class="interface-access-level" data-interface="${esc(m.key)}" ${editable?'':'disabled'}>${writeOnly?`<option value="0" ${level<2?'selected':''}>Interdit</option><option value="2" ${level>=2?'selected':''}>Autorisé</option>`:`<option value="0" ${level===0?'selected':''}>Aucun accès</option><option value="1" ${level===1?'selected':''}>Lecture seule</option>${m.write?`<option value="2" ${level===2?'selected':''}>Lecture + modification</option>`:''}`}</select>`:`<span class="access-level-chip level-${level}">${esc(accessLabel(level))}</span>`}</label>`;}).join('')}</div></details>`;}).join('');
  const scopeCard=g=>{const p=g.scope_policy||{},selected=new Set((p.allowed_group_ids||[]).map(String));return `<div class="access-scope-box compact"><div class="access-scope-head"><div><h4>Périmètre des groupes métier</h4><p>Groupes opérationnels visibles par les membres.</p></div><span class="scope-pill">${p.scope_mode==='SELECTED'?'Limité':'Tous les groupes'}</span></div><div class="access-scope-controls"><label>Portée<select class="scope-mode" ${editable?'':'disabled'}><option value="ALL" ${p.scope_mode!=='SELECTED'?'selected':''}>Tous les groupes métier</option><option value="SELECTED" ${p.scope_mode==='SELECTED'?'selected':''}>Seulement les groupes sélectionnés</option></select></label><label>Groupe par défaut<select class="scope-default" ${editable?'':'disabled'}><option value="">Aucun / Tous</option>${(d.business_groups||[]).map(bg=>`<option value="${bg.id}" ${String(p.default_group_id||'')===String(bg.id)?'selected':''}>${esc(bg.service_name?`${bg.service_name} · ${bg.name}`:bg.name)}</option>`).join('')}</select></label><label class="check-line"><input type="checkbox" class="scope-locked" ${p.filter_locked?'checked':''} ${editable?'':'disabled'}><span><strong>Verrouiller le filtre Groupe</strong><small>Force le groupe par défaut et empêche le changement.</small></span></label></div><details class="scope-groups-details"><summary>Groupes autorisés ${p.scope_mode==='SELECTED'?`(${selected.size})`:''}</summary><div class="scope-group-grid">${(d.business_groups||[]).map(bg=>`<label><input type="checkbox" class="scope-group" value="${bg.id}" ${selected.has(String(bg.id))?'checked':''} ${editable?'':'disabled'}><span>${esc(bg.name)}${bg.service_name?`<small>${esc(bg.service_name)}</small>`:''}</span></label>`).join('')||'<span class="muted">Aucun groupe métier configuré.</span>'}</div></details>${editable?`<div class="form-actions"><button class="button save-access-scope" data-id="${g.id}">Enregistrer le périmètre</button><span class="form-result" id="scope-result-${g.id}"></span></div>`:''}</div>`;};
  const activeUsers=d.rows.filter(u=>u.active).length;
  const accountRows=d.rows.map(u=>`<tr class="access-user-row" data-user-id="${u.id}" data-search="${esc(`${u.username} ${u.access_group_name||''}`.toLowerCase())}" data-status="${u.active?'active':'inactive'}" data-group="${u.access_group_id||''}"><td>${editable&&u.id!==currentUser.id?`<input type="checkbox" class="access-user-select" value="${u.id}" ${usersUiState.selectedUserIds.has(String(u.id))?'checked':''}>`:''}</td><td><strong>${esc(u.username)}</strong><small>${u.role==='admin'?'Administrateur système':'Compte standard'}</small></td><td>${u.role==='admin'?'<span class="muted">Accès total</span>':editable?`<select class="user-access-group compact" data-user-id="${u.id}"><option value="">Aucun groupe</option>${d.access_groups.map(g=>`<option value="${g.id}" ${Number(u.access_group_id)===Number(g.id)?'selected':''}>${esc(g.name)}</option>`).join('')}</select>`:esc(u.access_group_name||'Non affecté')}</td><td>${u.active?'<span class="fresh-badge fresh-green">Actif</span>':'<span class="fresh-badge fresh-red">Désactivé</span>'}</td><td><small>${esc(u.last_login_at||'Jamais')}</small></td><td class="access-row-actions"><button class="button ghost small inspect-user-rights" data-id="${u.id}">Voir droits</button>${editable&&u.id!==currentUser.id?`<button class="button ghost small toggle-user" data-id="${u.id}">${u.active?'Désactiver':'Réactiver'}</button>`:''}</td></tr>`).join('');
  const groupList=d.access_groups.map(g=>{const s=groupSummary(g);return `<button class="access-group-list-item ${String(usersUiState.selectedGroupId||'')===String(g.id)?'active':''}" data-id="${g.id}"><span><strong>${esc(g.name)}</strong><small>${Number(g.member_count||0)} utilisateur(s)</small></span><span><small>${esc(s.rights)}</small><small>${esc(s.scope)}${s.locked?' · verrouillé':''}</small></span></button>`;}).join('')||'<div class="empty">Aucun groupe d’accès.</div>';
  const profileCards=(d.access_profiles||[]).map(p=>`<article class="access-profile-card compact" data-profile-id="${p.id}"><div><span class="eyebrow">PROFIL</span><h3>${esc(p.name)}</h3><p>${esc(p.description||'Aucune description')}</p></div><div class="profile-summary"><span>${Number(p.summary?.write||0)} modif.</span><span>${Number(p.summary?.read||0)} lecture</span><span>${p.summary?.ani?'ANI autorisé':'ANI masqué'}</span></div><small>${esc(profileScopeText(p))}</small>${editable?`<details class="profile-actions-details"><summary>Actions</summary><div class="profile-refresh-row"><select class="profile-refresh-source">${groupOptions(false)}</select><button class="button ghost small refresh-access-profile" data-id="${p.id}">Actualiser</button></div><div class="access-profile-actions"><button class="button ghost small create-group-from-profile" data-id="${p.id}">Créer un groupe</button><button class="button ghost small duplicate-access-profile" data-id="${p.id}">Dupliquer le profil</button><button class="button ghost small danger delete-access-profile" data-id="${p.id}">Supprimer</button></div></details>`:''}</article>`).join('')||'<div class="empty">Aucun profil enregistré.</div>';
  app.innerHTML=`
    <div class="access-hero card compact"><div><span class="eyebrow">ADMINISTRATION · UTILISATEURS & ACCÈS</span><h2>Administration simplifiée</h2><p>Gérez les comptes, les groupes d’accès et les périmètres sans afficher toute la configuration en même temps.</p></div><div class="access-kpis"><span><b>${d.rows.length}</b> comptes</span><span><b>${activeUsers}</b> actifs</span><span><b>${d.access_groups.length}</b> groupes</span><span><b>${(d.access_profiles||[]).length}</b> profils</span></div></div>
    ${!editable?'<div class="flash warn">Votre compte peut consulter cette configuration mais ne peut pas la modifier.</div>':''}
    <nav class="access-tabs card" aria-label="Sections Utilisateurs et accès">
      <button class="access-tab" data-tab="accounts">Comptes <span>${d.rows.length}</span></button>
      <button class="access-tab" data-tab="groups">Groupes d’accès <span>${d.access_groups.length}</span></button>
      <button class="access-tab" data-tab="profiles">Profils <span>${(d.access_profiles||[]).length}</span></button>
      <button class="access-tab" data-tab="effective">Droits effectifs</button>
    </nav>
    <section class="access-tab-panel" data-panel="accounts">
      <div class="access-toolbar card"><div class="access-search"><input id="access-user-search" type="search" placeholder="Rechercher un utilisateur ou un groupe…" value="${esc(usersUiState.query)}"></div><select id="access-user-status"><option value="all">Tous les états</option><option value="active" ${usersUiState.status==='active'?'selected':''}>Actifs</option><option value="inactive" ${usersUiState.status==='inactive'?'selected':''}>Désactivés</option></select><select id="access-user-group"><option value="all">Tous les groupes d’accès</option><option value="" ${usersUiState.group===''?'selected':''}>Sans groupe</option>${d.access_groups.map(g=>`<option value="${g.id}" ${String(usersUiState.group)===String(g.id)?'selected':''}>${esc(g.name)}</option>`).join('')}</select>${editable?'<button class="button" id="open-user-create">Créer un compte</button>':''}</div>
      ${editable?`<details id="user-create-details" class="card access-create-box"><summary>Nouveau compte</summary><form id="user-form" class="manage-form"><label>Identifiant<input name="username" required></label><label>Type de compte<select name="role"><option value="viewer" selected>Compte standard</option>${currentUser.role==='admin'?'<option value="admin">Administrateur système</option>':''}</select></label><label>Groupe d'accès<select name="access_group_id">${groupOptions(true)}</select></label><label>Mot de passe temporaire<input type="password" name="password" required placeholder="12+ caractères : Aa1! minimum"></label><div class="full form-actions"><button class="button">Créer le compte</button><span id="user-result" class="form-result"></span></div></form></details>`:''}
      ${editable?`<div class="access-bulkbar card"><label><input type="checkbox" id="access-select-visible"> Sélectionner les comptes visibles</label><span id="access-selected-count">0 sélectionné(s)</span><select id="access-bulk-group"><option value="">Aucun groupe</option>${groupOptions(false)}</select><button class="button ghost" id="access-bulk-apply" disabled>Affecter au groupe</button></div>`:''}
      <section class="card panel access-users-panel"><div class="panel-head"><div><h2>Comptes</h2><p id="access-user-visible-count">${d.rows.length} compte(s) affiché(s)</p></div></div><div class="table-wrap"><table class="access-users-table"><thead><tr><th></th><th>Utilisateur</th><th>Groupe d’accès</th><th>État</th><th>Dernière connexion</th><th></th></tr></thead><tbody id="access-users-body">${accountRows}</tbody></table></div></section>
    </section>
    <section class="access-tab-panel" data-panel="groups">
      <div class="access-section-head"><div><h2>Groupes d’accès</h2><p>Choisissez un groupe à gauche. Un seul groupe est ouvert en édition à la fois.</p></div>${editable?'<button class="button" id="open-group-create">Créer un groupe</button>':''}</div>
      ${editable?`<details id="access-group-create-details" class="card access-create-box"><summary>Nouveau groupe d’accès</summary><form id="access-group-form" class="manage-form"><input type="hidden" name="id"><label>Nom du groupe<input name="name" required placeholder="Superviseurs MED1"></label><label class="full">Description<input name="description" placeholder="Accès Live + Analytiques limité au groupe MED1"></label><div class="full form-actions"><button class="button">Créer le groupe</button><button class="button ghost hidden" type="button" id="access-group-cancel">Annuler</button><span id="access-group-result" class="form-result"></span></div></form></details>`:''}
      <div class="access-groups-workspace"><aside class="card access-groups-list">${groupList}</aside><div id="access-group-editor" class="access-group-editor"></div></div>
    </section>
    <section class="access-tab-panel" data-panel="profiles">
      <div class="access-section-head"><div><h2>Profils d'accès réutilisables</h2><p>Des modèles réutilisables, sans utilisateurs attachés.</p></div>${editable?'<button class="button" id="open-profile-create">Créer un profil</button>':''}</div>
      ${editable?`<details id="access-profile-create-details" class="card access-create-box"><summary>Nouveau profil</summary><form id="access-profile-form" class="manage-form access-profile-form"><label>Nom du profil<input name="name" required placeholder="Superviseur MEDICAL"></label><label>Groupe d'accès source<select name="source_group_id" required>${groupOptions(false)}</select></label><label class="full">Description<input name="description" placeholder="Droits Live + Analytiques limités aux groupes MEDICAL"></label><div class="full form-actions"><button class="button">Créer le profil</button><span id="access-profile-result" class="form-result"></span></div></form></details>`:''}
      <div class="access-profile-grid clean">${profileCards}</div>
    </section>
    <section class="access-tab-panel" data-panel="effective">
      <div class="access-section-head"><div><h2>Droits effectifs</h2><p>Vérifiez exactement ce qu’un utilisateur peut voir avant de modifier son groupe d’accès.</p></div></div>
      <div class="card access-effective-picker"><label>Utilisateur<select id="access-effective-user"><option value="">Choisir un utilisateur…</option>${d.rows.map(u=>`<option value="${u.id}" ${String(usersUiState.selectedUserId||'')===String(u.id)?'selected':''}>${esc(u.username)}</option>`).join('')}</select></label></div>
      <div id="access-effective-preview"></div>
    </section>`;

  const showTab=tab=>{const valid=['accounts','groups','profiles','effective'].includes(tab)?tab:'accounts';usersUiState.tab=valid;$$('.access-tab').forEach(b=>b.classList.toggle('active',b.dataset.tab===valid));$$('.access-tab-panel').forEach(p=>p.hidden=p.dataset.panel!==valid);};
  $$('.access-tab').forEach(b=>b.onclick=()=>showTab(b.dataset.tab));
  showTab(usersUiState.tab);

  const applyUserFilters=()=>{usersUiState.query=String($('#access-user-search')?.value||'').trim().toLowerCase();usersUiState.status=$('#access-user-status')?.value||'all';usersUiState.group=$('#access-user-group')?.value??'all';let visible=0;$$('.access-user-row').forEach(r=>{const okQuery=!usersUiState.query||String(r.dataset.search||'').includes(usersUiState.query),okStatus=usersUiState.status==='all'||r.dataset.status===usersUiState.status,okGroup=usersUiState.group==='all'||String(r.dataset.group||'')===String(usersUiState.group);r.hidden=!(okQuery&&okStatus&&okGroup);if(!r.hidden)visible++;});const c=$('#access-user-visible-count');if(c)c.textContent=`${visible} compte(s) affiché(s)`;updateBulkCount();};
  $('#access-user-search')?.addEventListener('input',applyUserFilters);$('#access-user-status')?.addEventListener('change',applyUserFilters);$('#access-user-group')?.addEventListener('change',applyUserFilters);
  const updateBulkCount=()=>{if(!editable)return;const count=usersUiState.selectedUserIds.size,el=$('#access-selected-count'),btn=$('#access-bulk-apply');if(el)el.textContent=`${count} sélectionné(s)`;if(btn)btn.disabled=count===0;};
  $$('.access-user-select').forEach(cb=>cb.onchange=()=>{if(cb.checked)usersUiState.selectedUserIds.add(String(cb.value));else usersUiState.selectedUserIds.delete(String(cb.value));updateBulkCount();});
  $('#access-select-visible')?.addEventListener('change',e=>{$$('.access-user-row').filter(r=>!r.hidden).forEach(r=>{const cb=r.querySelector('.access-user-select');if(!cb)return;cb.checked=e.target.checked;if(cb.checked)usersUiState.selectedUserIds.add(String(cb.value));else usersUiState.selectedUserIds.delete(String(cb.value));});updateBulkCount();});
  $('#access-bulk-apply')?.addEventListener('click',async()=>{const ids=[...usersUiState.selectedUserIds],gid=$('#access-bulk-group')?.value||'';if(!ids.length)return;if(!confirm(`Affecter ${ids.length} compte(s) au groupe sélectionné ?`))return;try{for(const uid of ids)await api('/api/access-groups/member',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({user_id:uid,group_id:gid})});usersUiState.selectedUserIds.clear();await users();}catch(err){alert(err.message);}});
  $('#open-user-create')?.addEventListener('click',()=>{$('#user-create-details').open=true;$('#user-create-details').scrollIntoView({behavior:'smooth',block:'start'});});
  $('#open-group-create')?.addEventListener('click',()=>{$('#access-group-create-details').open=true;$('#access-group-create-details').scrollIntoView({behavior:'smooth',block:'start'});});
  $('#open-profile-create')?.addEventListener('click',()=>{$('#access-profile-create-details').open=true;$('#access-profile-create-details').scrollIntoView({behavior:'smooth',block:'start'});});

  const renderRightsPreview=uid=>{const host=$('#access-effective-preview');const u=d.rows.find(x=>String(x.id)===String(uid));if(!host)return;if(!u){host.innerHTML='<div class="card empty">Choisissez un utilisateur pour afficher ses droits effectifs.</div>';return;}const s=permissionSummary(u.effective_interface_permissions||{});host.innerHTML=`<section class="card access-effective-summary"><div><span class="eyebrow">${u.role==='admin'?'ADMINISTRATEUR SYSTÈME':'COMPTE STANDARD'}</span><h3>${esc(u.username)}</h3><p>${u.role==='admin'?'Accès total permanent':`Groupe d’accès : ${esc(u.access_group_name||'Non affecté')}`}</p></div><div class="access-effective-kpis"><span><b>${u.role==='admin'?'Tous':s.write}</b> modification</span><span><b>${u.role==='admin'?'Tous':s.read}</b> lecture</span><span><b>${(u.effective_permissions||{}).ani?'Oui':'Non'}</b> ANI</span></div></section><section class="card panel"><div class="panel-head"><div><h2>Interfaces réellement accessibles</h2><p>Résultat calculé par le backend pour ce compte.</p></div></div><div class="access-interface-grid single">${permissionSections(u.effective_interface_permissions||{},false)}</div></section><section class="card panel"><div class="panel-head"><div><h2>Périmètre métier effectif</h2><p>${esc(userScopeText(u))}</p></div></div></section>`;};
  $('#access-effective-user')?.addEventListener('change',e=>{usersUiState.selectedUserId=e.target.value||null;renderRightsPreview(usersUiState.selectedUserId);});
  $$('.inspect-user-rights').forEach(b=>b.onclick=()=>{usersUiState.selectedUserId=b.dataset.id;const sel=$('#access-effective-user');if(sel)sel.value=String(b.dataset.id);renderRightsPreview(b.dataset.id);showTab('effective');window.scrollTo({top:0,behavior:'smooth'});});
  renderRightsPreview(usersUiState.selectedUserId);

  const renderGroupEditor=gid=>{const host=$('#access-group-editor');if(!host)return;const g=d.access_groups.find(x=>String(x.id)===String(gid));if(!g){host.innerHTML='<div class="card empty">Sélectionnez un groupe d’accès.</div>';return;}usersUiState.selectedGroupId=String(g.id);$$('.access-group-list-item').forEach(b=>b.classList.toggle('active',String(b.dataset.id)===String(g.id)));const s=groupSummary(g);host.innerHTML=`<article class="card access-group-editor-card" data-group-id="${g.id}"><div class="access-group-editor-head"><div><span class="eyebrow">GROUPE D’ACCÈS</span><h2>${esc(g.name)}</h2><p>${esc(g.description||'Aucune description')}</p></div><div class="access-group-editor-kpis"><span>${Number(g.member_count||0)} membre(s)</span><span>${esc(s.rights)}</span><span>${esc(s.scope)}${s.locked?' · verrouillé':''}</span></div>${editable?`<div class="access-group-actions"><button class="button ghost small edit-access-group" data-id="${g.id}">Renommer</button><button class="button ghost small clone-access-group" data-id="${g.id}">Dupliquer</button><button class="button ghost small danger delete-access-group" data-id="${g.id}" ${Number(g.member_count||0)?'disabled':''}>Supprimer</button></div>`:''}</div>${editable&&(d.access_profiles||[]).length?`<details class="profile-apply-details"><summary>Appliquer un profil à ce groupe</summary><div class="profile-apply-row compact"><select class="apply-profile-select">${profileOptions()}</select><button class="button ghost small apply-access-profile" data-id="${g.id}">Appliquer</button></div></details>`:''}<section class="access-editor-section"><div class="access-editor-title"><div><h3>Droits des interfaces</h3><p>Ouvrez uniquement la section à modifier.</p></div>${editable?`<button class="button save-interface-permissions" data-id="${g.id}">Enregistrer les interfaces</button>`:''}</div><div class="access-interface-grid single">${permissionSections(g.interface_permissions||{},true)}</div><span class="form-result" id="iface-result-${g.id}"></span></section><section class="access-editor-section"><div class="sensitive-right-box compact"><label><span><strong>Voir ANI complet</strong><small>Donnée sensible distincte des interfaces.</small></span><select class="ani-access-level" ${editable?'':'disabled'}><option value="0" ${Number((g.permissions||{}).ani||0)===0?'selected':''}>Interdit</option><option value="1" ${Number((g.permissions||{}).ani||0)>=1?'selected':''}>Autorisé</option></select></label>${editable?`<button class="button ghost small save-ani-permission" data-id="${g.id}">Enregistrer ANI</button>`:''}</div>${scopeCard(g)}</section></article>`;bindGroupEditorActions();};
  const bindGroupEditorActions=()=>{if(!editable)return;$('.edit-access-group')?.addEventListener('click',()=>{const g=d.access_groups.find(x=>String(x.id)===String(usersUiState.selectedGroupId));const gf=$('#access-group-form'),cancel=$('#access-group-cancel'),box=$('#access-group-create-details');if(!g||!gf)return;gf.elements.id.value=g.id;gf.elements.name.value=g.name;gf.elements.description.value=g.description||'';gf.querySelector('button[type="submit"]').textContent='Enregistrer le groupe';cancel?.classList.remove('hidden');if(box)box.open=true;box?.scrollIntoView({behavior:'smooth',block:'start'});});$('.clone-access-group')?.addEventListener('click',async b=>{const g=d.access_groups.find(x=>String(x.id)===String(usersUiState.selectedGroupId));if(!g)return;const name=prompt('Nom du groupe dupliqué',`${g.name} - copie`);if(!name)return;try{await api('/api/access-groups/clone',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({source_group_id:g.id,name,description:g.description||''})});usersUiState.selectedGroupId=null;users();}catch(err){alert(err.message);}});$('.delete-access-group')?.addEventListener('click',async()=>{const g=d.access_groups.find(x=>String(x.id)===String(usersUiState.selectedGroupId));if(!g||!confirm(`Supprimer le groupe « ${g.name} » ?`))return;try{await api('/api/access-groups/delete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:g.id})});usersUiState.selectedGroupId=null;users();}catch(err){alert(err.message);}});$('.apply-access-profile')?.addEventListener('click',async b=>{const profileId=$('.apply-profile-select')?.value;if(!profileId){alert('Choisissez un profil.');return;}const g=d.access_groups.find(x=>String(x.id)===String(usersUiState.selectedGroupId)),p=(d.access_profiles||[]).find(x=>String(x.id)===String(profileId));if(!g||!confirm(`Appliquer le profil « ${p?.name||''} » au groupe « ${g.name} » ?\n\nLes droits, ANI et le périmètre seront remplacés. Les membres resteront affectés.`))return;try{await api('/api/access-profiles/apply',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({profile_id:profileId,group_id:g.id})});users();}catch(err){alert(err.message);}});$('.save-interface-permissions')?.addEventListener('click',async e=>{const b=e.currentTarget,card=b.closest('.access-group-editor-card'),permissions={};card.querySelectorAll('.interface-access-level').forEach(sel=>permissions[sel.dataset.interface]=Number(sel.value));const out=$(`#iface-result-${b.dataset.id}`);try{await api('/api/access-groups/interface-permissions',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({group_id:b.dataset.id,permissions})});out.textContent='Droits enregistrés.';setTimeout(users,350);}catch(err){out.textContent=err.message;}});$('.save-ani-permission')?.addEventListener('click',async e=>{const b=e.currentTarget,card=b.closest('.access-group-editor-card'),g=d.access_groups.find(x=>String(x.id)===String(b.dataset.id)),permissions={...(g?.permissions||{}),ani:Number(card.querySelector('.ani-access-level').value)};try{await api('/api/access-groups/permissions',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({group_id:b.dataset.id,permissions})});users();}catch(err){alert(err.message);}});$('.save-access-scope')?.addEventListener('click',async e=>{const b=e.currentTarget,card=b.closest('.access-group-editor-card'),mode=card.querySelector('.scope-mode').value,allowed=[...card.querySelectorAll('.scope-group:checked')].map(x=>x.value),defaultId=card.querySelector('.scope-default').value,locked=card.querySelector('.scope-locked').checked,out=$(`#scope-result-${b.dataset.id}`);try{await api('/api/access-groups/scope',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({group_id:b.dataset.id,scope_mode:mode,allowed_group_ids:allowed,default_group_id:defaultId,filter_locked:locked})});out.textContent='Périmètre enregistré.';setTimeout(users,350);}catch(err){out.textContent=err.message;}});};
  $$('.access-group-list-item').forEach(b=>b.onclick=()=>renderGroupEditor(b.dataset.id));
  if(!usersUiState.selectedGroupId||!d.access_groups.some(g=>String(g.id)===String(usersUiState.selectedGroupId)))usersUiState.selectedGroupId=d.access_groups[0]?.id||null;
  renderGroupEditor(usersUiState.selectedGroupId);

  if(editable){
    $('#user-form')?.addEventListener('submit',async e=>{e.preventDefault();const body=Object.fromEntries(new FormData(e.target));try{await api('/api/users',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});users();}catch(err){$('#user-result').textContent=err.message;}});
    $$('.toggle-user').forEach(b=>b.onclick=async()=>{try{await api('/api/users/toggle',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:b.dataset.id})});users();}catch(err){alert(err.message);}});
    $$('.user-access-group').forEach(sel=>sel.onchange=async()=>{try{await api('/api/access-groups/member',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({user_id:sel.dataset.userId,group_id:sel.value})});users();}catch(err){alert(err.message);users();}});
    const pf=$('#access-profile-form');if(pf)pf.onsubmit=async e=>{e.preventDefault();const body=Object.fromEntries(new FormData(pf));const out=$('#access-profile-result');try{await api('/api/access-profiles/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});out.textContent='Profil enregistré.';setTimeout(users,300);}catch(err){out.textContent=err.message;}};
    $$('.delete-access-profile').forEach(b=>b.onclick=async()=>{if(!confirm('Supprimer ce profil d’accès ? Aucun utilisateur ni groupe existant ne sera modifié.'))return;try{await api('/api/access-profiles/delete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:b.dataset.id})});users();}catch(err){alert(err.message);}});
    $$('.duplicate-access-profile').forEach(b=>b.onclick=async()=>{const p=(d.access_profiles||[]).find(x=>Number(x.id)===Number(b.dataset.id));if(!p)return;const name=prompt('Nom du nouveau profil',`${p.name} - copie`);if(!name)return;try{await api('/api/access-profiles/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name,description:p.description||'',source_profile_id:p.id})});users();}catch(err){alert(err.message);}});
    $$('.refresh-access-profile').forEach(b=>b.onclick=async()=>{const p=(d.access_profiles||[]).find(x=>Number(x.id)===Number(b.dataset.id)),row=b.closest('.access-profile-card'),sourceId=row?.querySelector('.profile-refresh-source')?.value;if(!p||!sourceId)return;if(!confirm(`Actualiser le profil « ${p.name} » depuis ce groupe d’accès ?\n\nAucun utilisateur ni groupe existant ne sera modifié.`))return;try{await api('/api/access-profiles/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:p.id,name:p.name,description:p.description||'',source_group_id:sourceId})});users();}catch(err){alert(err.message);}});
    $$('.create-group-from-profile').forEach(b=>b.onclick=async()=>{const p=(d.access_profiles||[]).find(x=>Number(x.id)===Number(b.dataset.id));if(!p)return;const name=prompt('Nom du nouveau groupe d’accès',p.name);if(!name)return;try{await api('/api/access-profiles/create-group',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({profile_id:p.id,name,description:p.description||''})});usersUiState.selectedGroupId=null;usersUiState.tab='groups';users();}catch(err){alert(err.message);}});
    const gf=$('#access-group-form'),cancel=$('#access-group-cancel');if(gf)gf.onsubmit=async e=>{e.preventDefault();const body=Object.fromEntries(new FormData(gf));try{await api('/api/access-groups/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});usersUiState.selectedGroupId=null;users();}catch(err){$('#access-group-result').textContent=err.message;}};if(cancel)cancel.onclick=()=>{gf.reset();gf.elements.id.value='';cancel.classList.add('hidden');gf.querySelector('button[type="submit"]').textContent='Créer le groupe';};
  }
  applyUserFilters();updateBulkCount();
}
let classificationSection='network';
function showClassificationSection(name){
  classificationSection=name||'network';
  if(location.hash.startsWith('#classification?')){try{history.replaceState(null,'','#classification?tab='+encodeURIComponent(classificationSection));}catch{}}
  app.dataset.groupEditor=classificationSection==='groups'?'true':'false';
  $$('.classification-tab').forEach(b=>b.classList.toggle('active',b.dataset.classTab===classificationSection));
  $$('.classification-section').forEach(x=>x.hidden=x.dataset.classSection!==classificationSection);
  if(classificationSection==='groups' && typeof groupWorkspaceMount==='function')groupWorkspaceMount();
}

function priorityMetricOptions(catalog,selected=''){
  return (catalog||[]).map(m=>`<option value="${esc(m.key)}" ${m.key===selected?'selected':''}>${esc(m.label)}${m.unit?` · ${esc(m.unit)}`:''}</option>`).join('');
}
function priorityOperatorOptions(operators,selected='>'){
  const labels={'>':'supérieur à','>=':'supérieur ou égal','<':'inférieur à','<=':'inférieur ou égal','==':'égal à','!=':'différent de'};
  return (operators||['>','>=','<','<=','==','!=']).map(op=>`<option value="${esc(op)}" ${op===selected?'selected':''}>${esc(op)} · ${esc(labels[op]||op)}</option>`).join('');
}
function priorityConditionRow(catalog,operators,c={}){
  const metric=c.metric||(catalog?.[0]?.key||'disconnects_per_day'),operator=c.operator||'>',value=c.value??1;
  return `<div class="priority-condition-row"><select class="priority-condition-metric" aria-label="Mesure">${priorityMetricOptions(catalog,metric)}</select><select class="priority-condition-operator" aria-label="Opérateur">${priorityOperatorOptions(operators,operator)}</select><input class="priority-condition-value" type="number" step="0.1" min="0" value="${esc(value)}" aria-label="Seuil"><button type="button" class="icon-btn remove-priority-condition" title="Supprimer la condition">×</button></div>`;
}
function priorityPolicyCard(p,catalog,operators,isNew=false){
  const fallback=!!p.is_fallback,conditions=(p.conditions||[]);
  const rows=(conditions.length?conditions:[{metric:'technical_score',operator:'>=',value:5}]).map(c=>priorityConditionRow(catalog,operators,c)).join('');
  const name=p.priority||'',rank=p.rank??100,color=/^#[0-9a-f]{6}$/i.test(String(p.color||''))?p.color:'#667085';
  return `<form class="card priority-policy-form ${isNew?'priority-new-policy':''}" data-priority="${esc(name)}" data-new="${isNew?'1':'0'}">
    <div class="priority-policy-head"><div><span class="priority-color-preview ${typeof priorityAdminColorClass==='function'?priorityAdminColorClass(color):''}"></span><div><h3>${isNew?'Nouveau niveau':esc(name)}</h3><p>${fallback?'Niveau de repli : utilisé si aucune règle supérieure ne correspond.':(p.match_mode==='ALL'?'Toutes les conditions doivent être vraies.':'Au moins une condition doit être vraie.')}</p></div></div>${!isNew&&!fallback?`<button type="button" class="button danger small delete-priority-policy">Supprimer</button>`:''}</div>
    <div class="priority-policy-settings">
      <label>Nom de l'état<input name="priority" maxlength="60" required value="${esc(name)}" placeholder="Ex. Urgent réseau, P1, À surveiller…"></label>
      <label>Rang / ordre<input name="rank" type="number" min="-10000" max="10000" step="1" value="${esc(rank)}"><small>Le plus grand rang est évalué en premier.</small></label>
      <label>Couleur<input name="color" type="color" value="${esc(color)}"></label>
      <label>Logique<select name="match_mode"><option value="ANY" ${p.match_mode!=='ALL'?'selected':''}>AU MOINS UNE condition (OU)</option><option value="ALL" ${p.match_mode==='ALL'?'selected':''}>TOUTES les conditions (ET)</option></select></label>
      <label class="switch-line"><input type="checkbox" name="enabled" ${p.enabled===0?'':'checked'} ${fallback?'disabled':''}><span class="switch"></span><span><strong>Niveau actif</strong><small>Un niveau désactivé est ignoré.</small></span></label>
      <label class="switch-line"><input type="checkbox" name="is_fallback" ${fallback?'checked':''}><span class="switch"></span><span><strong>Niveau de repli</strong><small>Un seul repli. Il n'utilise aucune condition.</small></span></label>
    </div>
    <div class="priority-conditions-editor" ${fallback?'hidden':''}><div class="priority-condition-title"><div><strong>Conditions</strong><small>Tu peux combiner plusieurs mesures et choisir l'opérateur de chaque seuil.</small></div><button type="button" class="button ghost small add-priority-condition">+ Condition</button></div><div class="priority-condition-list">${rows}</div></div>
    <div class="form-actions priority-policy-actions"><button class="button" type="submit">${isNew?'Créer le niveau':'Enregistrer'}</button><span class="form-result priority-policy-result"></span></div>
  </form>`;
}
function priorityPayloadFromForm(form){
  const isFallback=form.elements.is_fallback.checked;
  const conditions=isFallback?[]:[...form.querySelectorAll('.priority-condition-row')].map(row=>{
    const raw=row.querySelector('.priority-condition-value').value.trim();
    return {metric:row.querySelector('.priority-condition-metric').value,operator:row.querySelector('.priority-condition-operator').value,value:raw===''?NaN:Number(raw)};
  });
  return {original_priority:form.dataset.new==='1'?'':form.dataset.priority,priority:form.elements.priority.value,rank:Number(form.elements.rank.value),color:form.elements.color.value,match_mode:form.elements.match_mode.value,enabled:isFallback?true:form.elements.enabled.checked,is_fallback:isFallback,conditions};
}

async function classification(){
  const requestedTab=new URLSearchParams((location.hash.split('?')[1]||'')).get('tab');
  if(['network','groups','directory','exclusions','followup'].includes(requestedTab))classificationSection=requestedTab;
  const viewTicket=captureViewTicket();
  if(!canRead('classification')){redirectAllowed();return;} activate('classification'); setHead('Règles de tri','Réseau, groupes, annuaire partagé et exclusions du Support technique.');
  const d=await api('/api/classification');
  const policyMap=Object.fromEntries(d.policies.map(p=>[p.collector,p.default_site]));
  const siteOpts=v=>`<option value="SUR SITE" ${v==='SUR SITE'?'selected':''}>Sur site</option><option value="TELETRAVAIL" ${v==='TELETRAVAIL'?'selected':''}>Télétravail</option><option value="INCONNU" ${v==='INCONNU'?'selected':''}>Inconnu</option>`;
  const groupOpts=d.groups.map(g=>`<option value="${g.id}">${esc(g.name)}</option>`).join('');
  const memberMap=new Map(); d.groups.forEach(g=>memberMap.set(g.id,[])); d.members.forEach(m=>{if(memberMap.has(m.group_id))memberMap.get(m.group_id).push(m);});
  const groupCampaignMap=new Map(); d.groups.forEach(g=>groupCampaignMap.set(g.id,[])); (d.group_campaigns||[]).forEach(x=>{if(groupCampaignMap.has(x.group_id))groupCampaignMap.get(x.group_id).push(x);});
  const qualityCampaignChoices=[...(d.quality_campaigns||[])].sort((a,b)=>String(a).localeCompare(String(b),'fr'));
  const directoryMap=new Map((d.directory||[]).map(u=>[u.user_key,u]));
  const supportMap=new Map((d.support_candidates||[]).map(u=>[u.user_key,u]));
  const supportChoices=[...(d.support_candidates||[])].sort((a,b)=>String(a.display_name||a.user_identifier).localeCompare(String(b.display_name||b.user_identifier),'fr'));
  const sync=d.directory_sync||{};
  const importedCount=(d.directory||[]).filter(u=>u.imported_from_support).length;
  const exclusionKeys=new Set((d.support_exclusions||[]).map(x=>x.user_key));
  const exclusionChoices=(d.directory||[]).filter(u=>!exclusionKeys.has(u.user_key));
  const priorityPolicies=d.priority_policies||[],priorityMetrics=d.priority_metrics||[],priorityOperators=d.priority_operators||['>','>=','<','<=','==','!='];
  const scoreConfig=d.support_score_config||{};
  const nextPriorityRank=(priorityPolicies.length?Math.max(...priorityPolicies.map(p=>Number(p.rank)||0)):0)+100;

  if(!viewTicketIsCurrent(viewTicket))return;
  app.innerHTML=`
    <div class="classification-hub card">
      <div><span class="eyebrow">ADMINISTRATION · RÈGLES DE TRI</span><h2>Règles de classement</h2><p>Les modules utilisent le même annuaire. Les noms Support sont synchronisés dans l’annuaire sans écraser tes corrections manuelles.</p></div>
      <div class="classification-kpis"><span><b>${d.rules.length}</b> règle(s) réseau</span><span><b>${d.groups.length}</b> groupe(s)</span><span><b>${d.directory.length}</b> agent(s)</span><span><b>${d.support_exclusions.length}</b> exclu(s) Support</span></div>
    </div>
    <nav class="classification-tabs card" aria-label="Modules des règles de tri">
      <button type="button" class="classification-tab" data-class-tab="network"><b>Réseau & emplacement</b><small>IP, passerelle, collecteurs</small></button>
      <button type="button" class="classification-tab" data-class-tab="groups"><b>Groupes</b><small>Équipes et affectations</small></button>
      <button type="button" class="classification-tab" data-class-tab="directory"><b>Annuaire agents</b><small>Parc + Support Nelyio</small></button>
      <button type="button" class="classification-tab" data-class-tab="exclusions"><b>Exclusions Support</b><small>Agents ignorés des statistiques</small></button>
      <button type="button" class="classification-tab" data-class-tab="followup"><b>Suivi du parc</b><small>Intervalles et états admin</small></button>
    </nav>
    <div class="classification-section" data-class-section="followup">
      ${InventoryFollowup.render(d.followup_config,canWrite('classification'))}
    </div>
    <div class="classification-section" data-class-section="network">
      <div class="classification-hero card">
        <div><span class="eyebrow">RÉSEAU & EMPLACEMENT</span><h2>Collecteur + IP + passerelle + exceptions</h2><p>Détermine automatiquement si un poste est sur site, en télétravail ou inconnu.</p></div>
        <div class="logic-flow"><span>Diagnostic</span><b>→</b><span>Collecteur</span><b>+</b><span>IP</span><b>+</b><span>Passerelle</span><b>→</b><strong>Emplacement</strong></div>
      </div>
      <div class="grid2 config-grid">
        <section class="card panel"><div class="panel-head"><div><h2>Comportement par défaut</h2><p>Utilisé lorsqu'aucune règle IP prioritaire ne correspond.</p></div></div>
          <div class="policy-grid">${['DC1','DC2','*'].map(c=>`<form class="policy-form policy-card" data-collector="${c}"><div><strong>${c==='*'?'Autre collecteur':c}</strong><small>${c==='DC1'?'Ex. réseau local':c==='DC2'?'Ex. télétravail / VPN':'Collecteur non prévu'}</small></div><select name="default_site">${siteOpts(policyMap[c]||'INCONNU')}</select><button class="button small">Enregistrer</button></form>`).join('')}</div>
          <div class="network-help"><strong>Conseil :</strong> utilise les règles IP pour les réseaux connus et garde <b>Inconnu</b> pour ce qui ne correspond à rien.</div>
        </section>
        <section class="card panel"><div class="panel-head"><div><h2>Tester une classification</h2><p>Vérifie une combinaison avant de modifier le parc.</p></div></div>
          <form id="class-test" class="manage-form"><label>Collecteur<input name="collector" value="DC1" placeholder="DC1"></label><label>IP<input name="ip" value="192.168.100.25" placeholder="192.168.100.25"></label><label class="full">Passerelle (optionnelle)<input name="gateway" placeholder="192.168.100.254"></label><div class="full form-actions"><button class="button ghost">Tester</button><span id="class-test-result" class="form-result"></span></div></form>
        </section>
      </div>
      <section class="card panel"><div class="panel-head"><div><h2>Règles IP et exceptions</h2><p>Formats acceptés : IP unique, CIDR ou intervalle explicite. Les priorités les plus élevées passent en premier.</p></div></div>
        <form id="rule-form" class="rule-form">
          <label>Collecteur<select name="collector"><option>DC1</option><option>DC2</option><option value="*">Tous (*)</option></select></label>
          <label>IP / CIDR / intervalle<input name="network" required placeholder="192.168.100.20-80"></label>
          <label>Passerelle / CIDR / intervalle<input name="gateway_network" placeholder="192.168.100.1-10"></label>
          <label>Résultat<select name="result_site">${siteOpts('SUR SITE')}</select></label>
          <label>Priorité<input name="priority" type="number" value="100"></label>
          <label class="rule-label">Libellé<input name="label" placeholder="LAN principal, VPN agence, exception…"></label>
          <button class="button">+ Ajouter</button><span id="rule-result" class="form-result"></span>
        </form>
        <div class="table-wrap rule-table"><table><thead><tr><th>Priorité</th><th>Collecteur</th><th>IP / plage</th><th>Passerelle</th><th>Résultat</th><th>Libellé</th><th>État</th><th></th></tr></thead><tbody>${d.rules.map(r=>`<tr class="${r.enabled?'':'disabled-row'}"><td><strong>${r.priority}</strong></td><td><span class="collector-chip">${esc(r.collector)}</span></td><td><code>${esc(r.network)}</code></td><td>${r.gateway_network?`<code>${esc(r.gateway_network)}</code>`:'<span class="muted">Toutes</span>'}</td><td>${siteBadge(r.result_site)}</td><td>${esc(r.label||'—')}</td><td>${r.enabled?'<span class="fresh-badge fresh-green">Active</span>':'<span class="fresh-badge fresh-gray">Désactivée</span>'}</td><td><div class="row-actions"><button class="button ghost small toggle-rule" data-id="${r.id}">${r.enabled?'Désactiver':'Activer'}</button><button class="button danger small delete-rule" data-id="${r.id}">Supprimer</button></div></td></tr>`).join('')||'<tr><td colspan="8" class="empty">Aucune règle réseau.</td></tr>'}</tbody></table></div>
      </section>
    </div>

    <div class="classification-section" data-class-section="groups" hidden>
      <div id="group-workspace"></div>
    </div>

    <div class="classification-section" data-class-section="directory" hidden>
      <section class="card panel directory-sync-panel">
        <div class="panel-head"><div><h2>Annuaire partagé Parc + Support</h2><p>Les identifiants et noms trouvés dans les exports Support/SIMPLIFY2 alimentent automatiquement cet annuaire. Tes modifications manuelles restent prioritaires.</p></div><button type="button" class="button ghost" id="directory-sync">Synchroniser maintenant</button></div>
        <div class="directory-sync-status ${sync.error?'warn':'good'}"><strong>${sync.error?'Synchronisation partielle':'Synchronisation Support active'}</strong><span>${sync.error?esc(sync.error):`${sync.candidates||supportChoices.length} agent(s) détecté(s) dans Support · ${sync.created||0} créé(s) · ${sync.updated||0} nom(s) complété(s) à ce chargement · ${importedCount} entrée(s) marquée(s) origine Support.`}</span></div>
        <div class="grid2 directory-edit-grid">
          <form id="directory-form" class="stack-form"><h3>Ajouter / modifier un agent</h3><label>Identifiant utilisateur<input name="user_identifier" list="known-users" required placeholder="1001"></label><datalist id="known-users">${supportChoices.map(u=>`<option value="${esc(u.user_identifier)}">${esc(u.display_name)} · Support ${u.passages} ligne(s)</option>`).join('')}${d.discovered_users.map(u=>`<option value="${esc(u.user_key)}">${esc(u.exemple)} · Parc</option>`).join('')}</datalist><div class="name-grid"><label>Prénom<input name="first_name" placeholder="Ahmed"></label><label>Nom<input name="last_name" placeholder="Ben Salah"></label></div><label>Groupe<select name="group_id"><option value="">Aucun groupe</option>${groupOpts}</select></label><button class="button">Enregistrer l'utilisateur</button><small class="muted">Une modification manuelle du nom ne sera pas remplacée lors des prochains imports Support.</small><span id="directory-result" class="form-result"></span></form>
          <div class="directory-info-card"><h3>Source commune</h3><div><b>Support technique</b><span>fournit identifiant + nom agent</span></div><div><b>Administration</b><span>gère le groupe et les corrections de nom</span></div><div><b>Gestion du parc</b><span>réutilise le même annuaire</span></div><div><b>Recherche d’appels</b><span>affiche le même nom et groupe</span></div></div>
        </div>
        <div class="directory-table-wrap"><div class="panel-head compact"><div><h3>Annuaire configuré</h3><p>${d.directory.length} agent(s). Le badge Support indique une entrée créée automatiquement depuis les données Nelyio.</p></div></div><div class="table-wrap"><table><thead><tr><th>Identifiant</th><th>Nom affiché</th><th>Groupe</th><th>Origine</th><th></th></tr></thead><tbody>${(d.directory||[]).map(u=>`<tr><td><code>${esc(u.user_identifier)}</code></td><td><strong>${esc(([u.first_name,u.last_name].filter(Boolean).join(' '))||u.user_identifier)}</strong></td><td>${groupBadge(u.group_name)}</td><td>${u.imported_from_support?'<span class="fresh-badge fresh-blue">Support</span>':'<span class="fresh-badge fresh-gray">Administration</span>'}</td><td><button class="button danger small delete-directory" data-key="${esc(u.user_key)}">Supprimer</button></td></tr>`).join('')||'<tr><td colspan="5" class="empty">Aucun utilisateur dans l’annuaire.</td></tr>'}</tbody></table></div></div>
      </section>
    </div>

    <div class="classification-section" data-class-section="exclusions" hidden>
      <section class="card panel support-exclusion-panel">
        <div class="panel-head"><div><h2>Agents exclus du Support technique</h2><p>Un agent exclu reste dans la base, l’annuaire, les groupes et la Recherche d’appels, mais il est retiré des statistiques, graphiques et incidents de <strong>Support technique Nelyio</strong>.</p></div><span>${d.support_exclusions.length} exclu(s)</span></div>
        <div class="support-exclusion-warning">Cette règle n'efface aucune donnée. Retirer l'exclusion réintègre immédiatement l'agent aux calculs Support.</div>
        <form id="support-exclusion-form" class="exclusion-form"><label>Agent<input name="user_identifier" list="support-exclusion-users" required placeholder="Identifiant ou agent"></label><datalist id="support-exclusion-users">${exclusionChoices.map(u=>`<option value="${esc(u.user_identifier)}">${esc(([u.first_name,u.last_name].filter(Boolean).join(' '))||u.user_identifier)}${u.group_name?' · '+esc(u.group_name):''}</option>`).join('')}${supportChoices.filter(u=>!exclusionKeys.has(u.user_key)).map(u=>`<option value="${esc(u.user_identifier)}">${esc(u.display_name)} · Support</option>`).join('')}</datalist><label>Motif (optionnel)<input name="reason" maxlength="300" placeholder="Ex. compte test, superviseur, agent formation…"></label><button class="button">Exclure du Support</button><span id="support-exclusion-result" class="form-result"></span></form>
        <div class="table-wrap"><table><thead><tr><th>Agent</th><th>Identifiant</th><th>Groupe</th><th>Motif</th><th>Ajouté par</th><th></th></tr></thead><tbody>${(d.support_exclusions||[]).map(x=>`<tr><td><strong>${esc(x.display_name||x.user_identifier)}</strong></td><td><code>${esc(x.user_identifier)}</code></td><td>${groupBadge(x.group_name)}</td><td>${esc(x.reason||'—')}</td><td>${esc(x.created_by||'—')}<small class="sub">${esc(x.created_at||'')}</small></td><td><button class="button ghost small remove-support-exclusion" data-key="${esc(x.user_key)}">Réintégrer</button></td></tr>`).join('')||'<tr><td colspan="6" class="empty">Aucun agent exclu. Tous les agents sont pris en compte dans Support technique.</td></tr>'}</tbody></table></div>
      </section>
    </div>`;

  $$('.classification-tab').forEach(b=>b.onclick=()=>showClassificationSection(b.dataset.classTab));
  showClassificationSection(classificationSection);
  $$('.policy-form').forEach(f=>f.onsubmit=async e=>{e.preventDefault();try{await api('/api/classification/policy',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({collector:f.dataset.collector,default_site:f.default_site.value})});f.querySelector('button').textContent='Enregistré ✓';setTimeout(()=>f.querySelector('button').textContent='Enregistrer',900);}catch(err){alert(err.message);}});
  $('#class-test').onsubmit=async e=>{e.preventDefault();const body=Object.fromEntries(new FormData(e.target));try{const r=await api('/api/classification/test',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const x=r.result;$('#class-test-result').innerHTML=`${siteBadge(x.site)} <strong>${esc(x.reason)}</strong>${x.matched?' · règle #'+x.rule_id:' · comportement par défaut'}`;}catch(err){$('#class-test-result').textContent=err.message;}};
  $('#rule-form').onsubmit=async e=>{e.preventDefault();const body=Object.fromEntries(new FormData(e.target));try{await api('/api/classification/rule',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});classification();}catch(err){$('#rule-result').textContent=err.message;}};
  $$('.toggle-rule').forEach(b=>b.onclick=async()=>{await api('/api/classification/rule/toggle',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:b.dataset.id})});classification();});
  $$('.delete-rule').forEach(b=>b.onclick=async()=>{if(!confirm('Supprimer cette règle ?'))return;await api('/api/classification/rule/delete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:b.dataset.id})});classification();});
  $('#directory-form').onsubmit=async e=>{e.preventDefault();const body=Object.fromEntries(new FormData(e.target));try{await api('/api/directory/user',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});classification();}catch(err){$('#directory-result').textContent=err.message;}};
  $('#directory-sync').onclick=async()=>{const b=$('#directory-sync');b.disabled=true;b.textContent='Synchronisation…';try{await api('/api/directory/sync-support',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});classificationSection='directory';classification();}catch(err){alert(err.message);b.disabled=false;b.textContent='Synchroniser maintenant';}};
  $$('.delete-directory').forEach(b=>b.onclick=async()=>{if(!confirm('Supprimer cette entrée de l’annuaire ? Elle pourra être recréée automatiquement si l’agent existe encore dans Support.'))return;await api('/api/directory/user/delete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({user_key:b.dataset.key})});classification();});
  $('#support-exclusion-form').onsubmit=async e=>{e.preventDefault();const body=Object.fromEntries(new FormData(e.target));try{await api('/api/classification/support-exclusion',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});classificationSection='exclusions';classification();}catch(err){$('#support-exclusion-result').textContent=err.message;}};
  $$('.remove-support-exclusion').forEach(b=>b.onclick=async()=>{await api('/api/classification/support-exclusion/delete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({user_key:b.dataset.key})});classificationSection='exclusions';classification();});
  InventoryFollowup.bind(d.followup_config,{writable:canWrite('classification'),save:body=>api('/api/classification/followup',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}),onSaved:setFollowupConfig});
  const scoreForm=$('#support-score-form');
  if(scoreForm)scoreForm.onsubmit=async e=>{e.preventDefault();const fd=new FormData(scoreForm),body={};for(const [k,v] of fd.entries()){body[k]=['probable_closure_start_from','probable_closure_start_to'].includes(k)?v:Number(v);}body.probable_closure_enabled=scoreForm.elements.probable_closure_enabled.checked;const out=$('#support-score-result');try{await api('/api/classification/support-score',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});out.textContent='Moteur de score enregistré.';setTimeout(()=>out.textContent='',1600);}catch(err){out.textContent=err.message;}};
  $$('.priority-policy-form').forEach(f=>{
    const editor=f.querySelector('.priority-conditions-editor'),list=f.querySelector('.priority-condition-list'),fallback=f.elements.is_fallback,active=f.elements.enabled,color=f.elements.color,preview=f.querySelector('.priority-color-preview');
    const syncFallback=()=>{editor.hidden=fallback.checked;if(fallback.checked){active.checked=true;active.disabled=true;}else active.disabled=false;};
    fallback.onchange=syncFallback;color.oninput=()=>{if(preview&&typeof priorityAdminColorClass==='function')preview.className='priority-color-preview '+priorityAdminColorClass(color.value);};syncFallback();
    f.addEventListener('click',e=>{const add=e.target.closest('.add-priority-condition'),remove=e.target.closest('.remove-priority-condition');if(add){list.insertAdjacentHTML('beforeend',priorityConditionRow(priorityMetrics,priorityOperators,{metric:'technical_score',operator:'>=',value:5}));}if(remove){remove.closest('.priority-condition-row').remove();}});
    f.onsubmit=async e=>{e.preventDefault();const body=priorityPayloadFromForm(f),out=f.querySelector('.priority-policy-result');if(!body.is_fallback&&!body.conditions.length){out.textContent='Ajoute au moins une condition ou choisis ce niveau comme repli.';return;}if(!body.is_fallback&&body.conditions.some(c=>!Number.isFinite(c.value))){out.textContent='Chaque condition doit avoir une valeur.';return;}try{await api('/api/classification/support-priority',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});out.textContent=f.dataset.new==='1'?'Niveau créé.':'Politique enregistrée.';setTimeout(()=>{classificationSection='priorities';classification();},450);}catch(err){out.textContent=err.message;}};
  });
  $$('.delete-priority-policy').forEach(b=>b.onclick=async()=>{const f=b.closest('.priority-policy-form'),name=f.dataset.priority;if(!confirm(`Supprimer le niveau « ${name} » ?`))return;try{await api('/api/classification/support-priority/delete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({priority:name})});classificationSection='priorities';classification();}catch(err){alert(err.message);}});
  if(!canWrite('classification')){
    app.insertAdjacentHTML('afterbegin','<div class="flash warn">Mode lecture seule : les règles, groupes, annuaire et exclusions sont consultables mais non modifiables.</div>');
    $$('.classification-section input,.classification-section select,.classification-section textarea,.classification-section button').filter(el=>!el.closest('.followup-simulator')).forEach(el=>el.disabled=true);
  }
}

async function configuration(){
  const viewTicket=captureViewTicket();
  if(!canRead('config')){redirectAllowed();return;} activate('config'); setHead('Configuration','Base centrale, import diagnostic, réseau et sécurité HTTPS.');
  const [d,ret]=await Promise.all([api('/api/config'),api('/api/retention')]); const s=d.settings; const tlsOn=s.tls_enabled==='1';
  const rs=ret.settings||{}, rplan=ret.plan||{}, ritems=rplan.items||[], eligible=ritems.filter(x=>!x.held), held=ritems.filter(x=>x.held);
  const runtimeUrl=`${d.runtime.https?'https':'http'}://${d.runtime.host==='0.0.0.0'?(d.runtime.lan_ip||'IP-SERVEUR'):d.runtime.host}:${d.runtime.port}`;
  if(!viewTicketIsCurrent(viewTicket))return;
  app.innerHTML=`
    <div class="config-summary">
      <div class="card config-stat"><span>Base centrale</span><strong>${d.central_db.diagnostics}</strong><small>diagnostics · ${d.central_db.pcs} PC · ${d.central_db.size_mb} Mo</small></div>
      <div class="card config-stat"><span>Serveur actif</span><strong class="mono small-value">${esc(runtimeUrl)}</strong><small>configuration réellement utilisée maintenant</small></div>
      <div class="card config-stat"><span>Import auto</span><strong>${s.auto_import_enabled==='1'?'ACTIF':'ARRÊTÉ'}</strong><small>${esc(s.auto_import_minutes||'5')} minute(s)</small></div>
    </div>
    <div id="config-message"></div>
    <section class="card panel"><div class="panel-head"><div><h2>Importer / exporter la configuration</h2><p>Exporte ou restaure les paramètres réseau, règles de tri, groupes, liens vers les files et campagnes, annuaire et paramètres Support. Les diagnostics, comptes de connexion, mots de passe, affectations PC et notes ne sont pas inclus.</p></div></div>
      <div class="config-backup-row"><div><strong>Fichier JSON portable</strong><small>Pratique avant une modification importante ou pour reproduire la configuration sur une autre installation.</small></div><div class="form-actions"><a class="button ghost" href="/api/config/export">Exporter la configuration</a><label class="button file-button">Importer un fichier<input id="config-import-file" type="file" accept="application/json,.json"></label></div></div><div id="config-import-result"></div>
    </section>
    <div class="grid2 config-grid">
      <section class="card panel"><div class="panel-head"><div><h2>Source des diagnostics</h2><p>Chemin vers la base SQLite alimentée par ton système UDiagnostic.</p></div></div>
        <form id="source-form" class="config-form">
          <label>Chemin de diagnostic.db<input name="diagnostic_source_path" value="${esc(s.diagnostic_source_path||'')}" placeholder="D:/BMR-DC2/UDiagnostic/DB/diagnostic.db"></label>
          <div class="path-examples"><span>Exemples :</span><code>D:/BMR-DC2/UDiagnostic/DB/diagnostic.db</code><code>\\SERVEUR\\Partage\\diagnostic.db</code></div>
          <div class="source-status ${d.source_error?'bad':d.source_info?'good':''}">${d.source_error?`<strong>Source non disponible</strong><span>${esc(d.source_error)}</span>`:d.source_info?`<strong>Source valide</strong><span>${d.source_info.rows} lignes · dernière date ${esc(d.source_info.latest||'—')}</span>`:'<strong>Aucune source configurée</strong><span>La base centrale continue de fonctionner avec les données déjà importées.</span>'}</div>
          <div class="form-actions"><button type="button" id="test-source" class="button ghost">Tester la source</button><button type="button" id="import-now" class="button">Importer maintenant</button><span id="source-result" class="form-result"></span></div>
        </form>
      </section>
      <section class="card panel"><div class="panel-head"><div><h2>Serveur web</h2><p>Choisis l'adresse IP d'écoute et le port utilisés au prochain démarrage.</p></div></div>
        <div class="config-form">
          <label>IP d'écoute<input id="web-host" value="${esc(s.web_host||'127.0.0.1')}" placeholder="127.0.0.1"></label>
          <label>Port<input id="web-port" type="number" min="1" max="65535" value="${esc(s.web_port||'5000')}"></label>
          <label>Nom DNS public<input id="public-hostname" value="${esc(s.public_hostname||'stock-manager.nelyio.local')}" placeholder="stock-manager.nelyio.local"></label>
          <div class="network-help"><strong>Production recommandée :</strong> garde <code>127.0.0.1</code> ici et publie uniquement HTTPS/443 via Caddy ou IIS. Le backend Python reste inaccessible directement depuis le LAN.</div>
          <div class="security-note good">Sécurité : CSRF, session inactive 30 min, verrouillage après échecs, groupes d’accès par interface, CSP/HSTS, audit IP et source diagnostic en lecture seule.</div>
        </div>
      </section>
    </div>
    <section class="card panel"><div class="panel-head"><div><h2>HTTPS direct (optionnel)</h2><p>Pour le mode recommandé avec reverse proxy, laisse cette option désactivée. Active-la seulement si tu as un certificat et une clé privée PEM.</p></div></div>
      <div class="tls-grid">
        <label class="switch-line"><input type="checkbox" id="tls-enabled" ${tlsOn?'checked':''}><span class="switch"></span><span><strong>Activer HTTPS directement dans Python</strong><small>TLS 1.2 minimum. Redémarrage requis.</small></span></label>
        <label>Certificat PEM<input id="tls-cert" value="${esc(s.tls_cert_path||'')}" placeholder="C:/TECH-IN/StockManager/certs/stock-manager.crt.pem"></label>
        <label>Clé privée PEM<input id="tls-key" value="${esc(s.tls_key_path||'')}" placeholder="C:/TECH-IN/StockManager/certs/stock-manager.key.pem"></label>
      </div>
      <div class="security-note"><strong>Conseil :</strong> le paquet n’embarque plus Caddy. Place <code>caddy.exe</code> à la racine, dans <code>tools/</code>, dans le PATH ou définis <code>NELYIO_CADDY_EXE</code>. Le proxy écoute en HTTPS sur <code>9050</code> et transmet vers <code>127.0.0.1:9051</code>.</div>
    </section>
    <section class="card panel"><div class="panel-head"><div><h2>Synchronisation automatique</h2><p>L'import est incrémental : les événements déjà présents sont ignorés grâce à event_uuid.</p></div></div>
      <form id="config-form" class="auto-import-row">
        <label class="switch-line"><input type="checkbox" id="auto-import" ${s.auto_import_enabled==='1'?'checked':''}><span class="switch"></span><span><strong>Activer l'import automatique</strong><small>Import au démarrage puis selon l'intervalle ci-dessous.</small></span></label>
        <label class="interval-field">Intervalle<input id="auto-minutes" type="number" min="1" max="1440" value="${esc(s.auto_import_minutes||'5')}"><span>minutes</span></label>
        <button class="button" type="submit">Enregistrer la configuration</button>
      </form>
    </section>
    <section class="card panel retention-panel"><div class="panel-head"><div><h2>Rétention & archives · Étape 8</h2><p>Politique Option B : archivage mensuel vérifié avant suppression. Le mode simulation ne supprime aucune donnée.</p></div><span class="fresh-badge ${rs.retention_enabled==='1'?'fresh-red':'fresh-gray'}">${rs.retention_enabled==='1'?'PURGE RÉELLE AUTORISÉE':'DRY-RUN UNIQUEMENT'}</span></div>
      <div class="retention-summary"><div><strong>${eligible.length}</strong><span>mois éligible(s)</span></div><div><strong>${held.length}</strong><span>mois gelé(s)</span></div><div><strong>${esc(rplan.cutoffs?.operational||'—')}</strong><span>borne base active</span></div><div><strong>${esc(rplan.cutoffs?.details||'—')}</strong><span>borne Détails</span></div></div>
      <form id="retention-form" class="retention-form">
        <label class="switch-line full"><input type="checkbox" name="enabled" ${rs.retention_enabled==='1'?'checked':''}><span class="switch"></span><span><strong>Autoriser explicitement les exécutions destructives</strong><small>Désactivé par défaut. Même activé, une sauvegarde cohérente + archives vérifiées + confirmation PURGER restent obligatoires.</small></span></label>
        <label>Base active · mois<input type="number" min="1" max="120" name="operational_months" value="${esc(rs.retention_operational_months||'6')}"></label>
        <label>Détails · mois<input type="number" min="1" max="120" name="details_months" value="${esc(rs.retention_details_months||'12')}"></label>
        <label>Archive froide · mois<input type="number" min="1" max="240" name="archive_months" value="${esc(rs.retention_archive_months||'24')}"></label>
        <label>Agrégats · mois<input type="number" min="1" max="240" name="aggregate_months" value="${esc(rs.retention_aggregate_months||'36')}"></label>
        <label>Journaux sécurité · mois<input type="number" min="1" max="120" name="security_months" value="${esc(rs.retention_security_months||'12')}"></label>
        <label>Health points · jours<input type="number" min="1" max="3650" name="health_days" value="${esc(rs.retention_health_days||'30')}"></label>
        <label class="full">Dossier archives<input name="archive_dir" value="${esc(rs.retention_archive_dir||rplan.archive_dir||'')}"></label>
        <label class="full">Dossier sauvegardes avant purge<input name="backup_dir" value="${esc(rs.retention_backup_dir||rplan.backup_dir||'')}"></label>
        <div class="full form-actions"><button class="button" type="submit">Enregistrer la politique</button><button class="button ghost" type="button" id="retention-dry-run">Simuler maintenant</button><button class="button danger" type="button" id="retention-execute">Archiver + purger réellement</button><span id="retention-result" class="form-result"></span></div>
      </form>
      <div class="security-note"><strong>Sécurité :</strong> les archives sont créées en SQLite lecture seule logique avec manifeste, SHA-256, <code>PRAGMA integrity_check</code> et comptage des lignes. Les imports purgés reçoivent un tombstone pour empêcher leur réimport accidentel.</div>
      <div class="grid2 retention-subgrid">
        <div><h3>Gel / legal hold</h3><form id="retention-hold-form" class="stack-form"><label>Du<input type="date" name="start_day" required></label><label>Au<input type="date" name="end_day" required></label><label>Réévaluer le<input type="date" name="reevaluate_at"></label><label>Motif<textarea name="reason" rows="2" required placeholder="Incident ouvert, demande contractuelle, investigation…"></textarea></label><button class="button">Ajouter le gel</button></form></div>
        <div><h3>Gels actifs / historiques</h3><div class="table-wrap"><table><thead><tr><th>Période</th><th>Motif</th><th>État</th><th></th></tr></thead><tbody>${(ret.holds||[]).map(h=>`<tr><td>${esc(h.start_day)} → ${esc(h.end_day)}</td><td>${esc(h.reason)}</td><td>${h.active?'<span class="fresh-badge fresh-yellow">ACTIF</span>':'<span class="fresh-badge fresh-gray">LEVÉ</span>'}</td><td><button type="button" class="button ghost small retention-hold-toggle" data-id="${h.id}" data-active="${h.active?0:1}">${h.active?'Lever':'Réactiver'}</button></td></tr>`).join('')||'<tr><td colspan="4" class="empty">Aucun gel.</td></tr>'}</tbody></table></div></div>
      </div>
      <details><summary>Dernières exécutions de rétention</summary><div class="table-wrap"><table><thead><tr><th>Date</th><th>Mode</th><th>État</th><th>Utilisateur</th><th>Erreur</th></tr></thead><tbody>${(ret.runs||[]).map(r=>`<tr><td>${esc(r.finished_at||r.started_at)}</td><td>${esc(r.mode)}</td><td>${esc(r.status)}</td><td>${esc(r.actor||'SYSTEM')}</td><td>${esc(r.error||'—')}</td></tr>`).join('')||'<tr><td colspan="5" class="empty">Aucune exécution.</td></tr>'}</tbody></table></div></details>
    </section>

    <section class="card panel"><div class="panel-head"><div><h2>Bases de données</h2><p>La gestion reste dans la base principale. Les logs détaillés sont archivés séparément pour ne pas alourdir les autres interfaces.</p></div></div>
      <div class="db-path"><span>Base principale</span><code>${esc(d.central_db.path)}</code></div>
      <div class="db-path"><span>Base Détails</span><code>${esc(d.details_db?.path||'Nelyio_Details.db')}</code></div>
      <div class="data-map"><div><strong>${Number(d.details_db?.events||0).toLocaleString('fr-FR')}</strong><span>Logs archivés</span></div><div><strong>${Number(d.details_db?.imports||0)}</strong><span>Imports archivés</span></div><div><strong>${Number(d.details_db?.days||0)}</strong><span>Jours référencés</span></div><div><strong>${Number(d.details_db?.size_mb||0).toLocaleString('fr-FR')} Mo</strong><span>Taille base Détails</span></div></div>
    </section>
    <section class="card panel"><div class="panel-head"><div><h2>Historique des imports</h2><p>Les 12 dernières tentatives d'import.</p></div></div>
      <div class="table-wrap"><table><thead><tr><th>Date</th><th>Utilisateur</th><th>État</th><th>Source</th><th>Nouvelles</th><th>Ignorées</th><th>Erreur</th></tr></thead><tbody>${d.import_logs.map(x=>`<tr><td>${esc(x.finished_at||x.started_at)}</td><td>${esc(x.actor)}</td><td>${x.status==='OK'?'<span class="fresh-badge fresh-green">OK</span>':'<span class="fresh-badge fresh-red">Erreur</span>'}</td><td class="path-cell">${esc(x.source_path)}</td><td>${Number(x.imported_rows||0)}</td><td>${Number(x.skipped_rows||0)}</td><td>${esc(x.error||'—')}</td></tr>`).join('')||'<tr><td colspan="7" class="empty">Aucun import.</td></tr>'}</tbody></table></div>
    </section>`;

  const sourceInput=$('#source-form input[name="diagnostic_source_path"]');
  $('#test-source').onclick=async()=>{const out=$('#source-result');out.textContent='Test…';try{const r=await api('/api/config/test-source',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({source_path:sourceInput.value})});out.textContent=`Source valide : ${r.info.rows} ligne(s), dernière date ${r.info.latest||'—'}`;}catch(err){out.textContent=err.message;}};
  $('#import-now').onclick=async()=>{const out=$('#source-result');out.textContent='Import en cours…';try{const r=await api('/api/config/import',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({source_path:sourceInput.value})});out.textContent=`Import terminé : ${r.imported_rows} nouvelle(s), ${r.skipped_rows} déjà présente(s).`;setTimeout(configuration,800);}catch(err){out.textContent=err.message;}};
  $('#config-import-file').onchange=async e=>{const file=e.target.files&&e.target.files[0];if(!file)return;const out=$('#config-import-result');if(!confirm('Importer ce fichier remplacera les règles de tri, groupes et annuaire actuels. Continuer ?')){e.target.value='';return;}try{const text=await file.text();const body=JSON.parse(text);const r=await api('/api/config/import-settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});out.innerHTML=flash(`Configuration importée : ${r.rules} règle(s), ${r.groups} groupe(s), ${r.directory} utilisateur(s). Redémarre l'application si l'IP ou le port ont changé.`,'warn');setTimeout(configuration,1200);}catch(err){out.innerHTML=flash(err.message,'error');}finally{e.target.value='';}};
  $('#config-form').onsubmit=async e=>{e.preventDefault();const body={diagnostic_source_path:sourceInput.value,web_host:$('#web-host').value,web_port:$('#web-port').value,public_hostname:$('#public-hostname').value,tls_enabled:$('#tls-enabled').checked,tls_cert_path:$('#tls-cert').value,tls_key_path:$('#tls-key').value,auto_import_enabled:$('#auto-import').checked,auto_import_minutes:$('#auto-minutes').value};try{const r=await api('/api/config',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});$('#config-message').innerHTML=r.restart_required?flash(`Configuration enregistrée. Redémarre l'application pour appliquer ${r.host}:${r.port}.`,'warn'):flash('Configuration enregistrée.');setTimeout(()=>window.scrollTo({top:0,behavior:'smooth'}),50);}catch(err){$('#config-message').innerHTML=flash(err.message,'error');}};
  $('#retention-form').onsubmit=async e=>{e.preventDefault();const f=e.target,body=Object.fromEntries(new FormData(f));body.enabled=f.elements.enabled.checked;const out=$('#retention-result');try{await api('/api/retention/config',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});out.textContent='Politique enregistrée.';setTimeout(configuration,700);}catch(err){out.textContent=err.message;}};
  $('#retention-dry-run').onclick=async()=>{const out=$('#retention-result');out.textContent='Simulation en cours…';try{const r=await api('/api/retention/dry-run',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});out.textContent=`Simulation : ${r.eligible_months?.length||0} mois éligible(s), ${r.held_months?.length||0} gelé(s), aucune suppression.`;setTimeout(configuration,1200);}catch(err){out.textContent=err.message;}};
  $('#retention-execute').onclick=async()=>{const out=$('#retention-result');if(rs.retention_enabled!=='1'){out.textContent='Active d’abord explicitement la purge réelle puis enregistre la politique.';return;}const typed=prompt('Opération destructive. Tape exactement PURGER pour créer une sauvegarde, archiver, vérifier puis supprimer les mois éligibles.');if(String(typed||'').trim().toUpperCase()!=='PURGER'){out.textContent='Exécution annulée.';return;}if(!confirm('Dernière confirmation : lancer maintenant l’archivage + purge des mois éligibles ?'))return;out.textContent='Sauvegarde et archivage en cours…';try{const r=await api('/api/retention/execute',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({confirm:'PURGER'})});out.textContent=`Terminé : ${r.archives?.length||0} archive(s), ${r.purged?.length||0} purge(s).`;setTimeout(configuration,1200);}catch(err){out.textContent=err.message;}};
  $('#retention-hold-form').onsubmit=async e=>{e.preventDefault();const body=Object.fromEntries(new FormData(e.target));try{await api('/api/retention/hold',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});setTimeout(configuration,250);}catch(err){$('#retention-result').textContent=err.message;}};
  $$('.retention-hold-toggle').forEach(b=>b.onclick=async()=>{try{await api('/api/retention/hold/toggle',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:b.dataset.id,active:b.dataset.active})});configuration();}catch(err){$('#retention-result').textContent=err.message;}});
  if(!canWrite('config')){
    app.insertAdjacentHTML('afterbegin','<div class="flash warn">Mode lecture seule : la configuration est visible mais aucune modification ou import manuel n’est autorisé.</div>');
    app.querySelectorAll('input,select,textarea,button').forEach(el=>el.disabled=true);
    const fileLabel=app.querySelector('.file-button');if(fileLabel)fileLabel.classList.add('hidden');
  }
}

function securityCoverageBadge(row){
  const map={COMPLETE:['fresh-green','Import complet'],IMPORTED_NO_CALLS:['fresh-yellow','Importé · appels absents'],CALLS_ONLY:['fresh-orange','Appels seuls'],ARCHIVED:['fresh-gray','Archivé / purgé'],MISSING:['fresh-red','Non importé']};
  const [cls,label]=map[row.status]||['fresh-gray',row.label||row.status||'Inconnu'];
  return `<span class="fresh-badge ${cls}">${esc(label)}</span>`;
}
function renderSecurityCoverage(d){
  const s=d.summary||{},rows=d.rows||[];
  const overall=d.status==='COMPLETE'?`<div class="flash">Toutes les dates sélectionnées disposent de l'export activités et des appels.</div>`:d.status==='MISSING'?`<div class="flash error">Aucune des dates sélectionnées n'est disponible dans la base active.</div>`:`<div class="flash warn">La période est partiellement couverte. Consulte le détail ci-dessous.</div>`;
  return `${overall}
    <div class="security-import-summary">
      <div><span>Jours contrôlés</span><strong>${Number(d.days||0)}</strong></div>
      <div><span>Imports activités</span><strong>${Number(s.imported||0)}</strong></div>
      <div><span>Avec appels</span><strong>${Number(s.calls||0)}</strong></div>
      <div><span>Complets</span><strong>${Number(s.complete||0)}</strong></div>
      <div><span>Archivés</span><strong>${Number(s.archived||0)}</strong></div>
      <div><span>Manquants</span><strong>${Number(s.missing||0)}</strong></div>
    </div>
    <div class="table-wrap security-import-table"><table><thead><tr><th>Date</th><th>État</th><th>Activités</th><th>Appels</th><th>Fichier</th><th>Importé le</th><th>Par</th></tr></thead><tbody>${rows.map(r=>`<tr><td><strong>${esc(r.day)}</strong></td><td>${securityCoverageBadge(r)}</td><td>${r.activities_present?`${Number(r.activity_rows||0).toLocaleString('fr-FR')} ligne(s)`:'—'}</td><td>${r.calls_present?`${Number(r.call_rows||0).toLocaleString('fr-FR')} appel(s)`:'—'}</td><td class="mono import-file-cell">${esc(r.filename||'—')}${r.status==='ARCHIVED'&&r.purged_at?`<small>Archivé le ${esc(r.purged_at)}</small>`:''}</td><td>${esc(r.imported_at||'—')}</td><td>${esc(r.imported_by||'—')}</td></tr>`).join('')||'<tr><td colspan="7" class="empty">Aucun résultat.</td></tr>'}</tbody></table></div>`;
}

async function securityAudit(){
  const viewTicket=captureViewTicket();
  if(!canRead('security')){redirectAllowed();return;}
  activate('security'); setHead('Sécurité & audit','Connexions, actions sensibles, adresses IP et état du durcissement web.');
  const d=await api('/api/security-audit');
  if(!viewTicketIsCurrent(viewTicket))return;
  app.innerHTML=`
    <div class="cards status-cards security-cards">
      <div class="card metric"><span>Session inactive</span><b>${d.policy.idle_minutes} min</b><small>expiration automatique</small></div>
      <div class="card metric"><span>Verrouillage</span><b>${d.policy.max_failures}</b><small>échecs → ${d.policy.lock_minutes} min</small></div>
      <div class="card metric"><span>HTTPS runtime</span><b>${d.runtime.https?'OUI':'NON'}</b><small>${esc(d.runtime.mode)}</small></div>
      <div class="card metric"><span>Backend</span><b>${esc(d.runtime.host)}</b><small>port ${esc(d.runtime.port)}</small></div>
    </div>
    <section class="card panel security-import-check"><div class="panel-head"><div><h2>Contrôle des dates importées</h2><p>Vérifie rapidement si une date ou une plage est disponible pour Support Nelyio. La couverture activités et appels est contrôlée séparément.</p></div></div>
      <form id="security-import-form" class="security-import-form">
        <label>Date de début<input type="date" name="date_from" required></label>
        <label>Date de fin<input type="date" name="date_to" required></label>
        <div class="form-actions"><button class="button" type="submit">Vérifier</button><button class="button ghost" type="button" id="security-import-today">Aujourd'hui</button></div>
      </form>
      <div class="security-note">Le contrôle est limité à 31 jours. <strong>Import complet</strong> = export activités + appels présents. Une date <strong>Archivée / purgée</strong> a bien été importée auparavant mais n'est plus disponible dans la base active.</div>
      <div id="security-import-result" class="security-import-result"><div class="empty">Choisis une date ou une plage, puis clique sur « Vérifier ».</div></div>
    </section>
    <section class="card panel"><div class="panel-head"><div><h2>Derniers événements de sécurité</h2><p>Les actions sensibles et connexions sont journalisées ; les modifications PC disposent aussi de leur audit détaillé.</p></div></div>
      <div class="table-wrap"><table><thead><tr><th>Date</th><th>Utilisateur</th><th>IP source</th><th>Action</th><th>Détail</th></tr></thead><tbody>${d.events.map(x=>`<tr><td>${esc(x.created_at)}</td><td>${esc(x.username||'—')}</td><td><code>${esc(x.source_ip||'—')}</code></td><td><strong>${esc(x.action)}</strong></td><td>${esc(x.details||'—')}</td></tr>`).join('')||'<tr><td colspan="5" class="empty">Aucun événement.</td></tr>'}</tbody></table></div>
    </section>`;
  const form=$('#security-import-form'),result=$('#security-import-result'),todayBtn=$('#security-import-today');
  const localDay=()=>{const x=new Date(),y=new Date(x.getTime()-x.getTimezoneOffset()*60000);return y.toISOString().slice(0,10);};
  const setToday=()=>{const day=localDay();form.elements.date_from.value=day;form.elements.date_to.value=day;};
  const runCheck=async()=>{
    const from=form.elements.date_from.value,to=form.elements.date_to.value||from;
    if(!from){result.innerHTML='<div class="flash error">Choisis une date de début.</div>';return;}
    result.innerHTML='<div class="loading">Vérification de la couverture…</div>';
    try{const data=await api(`/api/security-import-coverage?date_from=${encodeURIComponent(from)}&date_to=${encodeURIComponent(to)}`);result.innerHTML=renderSecurityCoverage(data);}
    catch(err){result.innerHTML=`<div class="flash error">${esc(err.message)}</div>`;}
  };
  form.onsubmit=e=>{e.preventDefault();runCheck();};
  todayBtn.onclick=()=>{setToday();runCheck();};
  setToday();
}

function account(){
  activate('account'); setHead('Mon compte',`Connecté en tant que ${currentUser.username}.`);
  app.innerHTML=`<section class="card panel account-card"><div class="account-summary"><span class="avatar">${esc(currentUser.username.slice(0,2).toUpperCase())}</span><div><strong>${esc(currentUser.username)}</strong><small>${esc(currentUser.role==='admin'?'Administrateur système':(currentUser.group_name||'Compte standard'))}</small></div></div><div class="panel-head"><div><h2>Changer mon mot de passe</h2><p>Le mot de passe est hashé et conservé dans la base centrale.</p></div></div><form id="password-form" class="manage-form"><label class="full">Mot de passe actuel<input type="password" name="current_password" required></label><label class="full">Nouveau mot de passe<input type="password" name="new_password" required placeholder="12+ caractères : majuscule, minuscule, chiffre, spécial"></label><div class="full form-actions"><button class="button">Modifier</button><span id="password-result" class="form-result"></span></div></form></section>`;
  $('#password-form').onsubmit=async e=>{e.preventDefault();const body=Object.fromEntries(new FormData(e.target));try{await api('/api/change-password',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});$('#password-result').textContent='Mot de passe modifié.';e.target.reset();}catch(err){$('#password-result').textContent=err.message;}};
}

/* F2 : un module absent ne doit ni appeler une fonction inconnue ni garder
   le titre de l'ecran precedent. Les fichiers reels sont livres dans static/ ;
   ce controle ne les remplace pas et ne change aucun droit. */
const frontendRouteModules = {
  '#classification-groups': {fn:'groupWorkspaceView', file:'groups.js', view:'classification-groups', title:'Groupes', permission:'classification'},
  '#support-priority': {fn:'supportPrioritySettings', file:'priority_admin.js', view:'support-priority', title:'Priorités Support', permission:'classification'},
  '#live-quality-admin': {fn:'liveQualityAdminView', file:'live-quality-admin.js', view:'live-quality-admin', title:'Signalisation Qualité Live', permission:'config'},
  '#declarations': {fn:'declarationsView', file:'declarations.js', view:'declarations', title:'Déclarations', permission:'declarations'}
};
function frontendRouteUnavailable(hash){
  const entry=frontendRouteModules[hash];
  if(!entry || !canRead(entry.permission) || typeof window[entry.fn]==='function') return false;
  activate(entry.view);
  setHead(entry.title,'Le module de cette interface n’a pas pu être chargé.');
  app.innerHTML=`<section class="card panel" role="alert" data-frontend-missing="${esc(entry.file)}">
    <div class="flash error"><strong>Module non chargé : ${esc(entry.title)}</strong><p>Le fichier <code>static/${esc(entry.file)}</code> est absent, ancien ou bloqué. La cause précise reste à vérifier.</p></div>
    <p>Installez le paquet complet de réparation du frontend dans le dossier Nelyio utilisé par le serveur, puis rechargez la page. Vos données ne sont pas modifiées.</p>
    <button type="button" class="button" id="frontend-reload">Recharger la page</button>
  </section>`;
  document.getElementById('frontend-reload').onclick=()=>window.location.reload();
  return true;
}

async function route(){
  if(!currentUser) return;
  const requested=(location.hash.slice(1).split(/[/?]/)[0]||'dashboard');
  const requestedInterface=interfaceForView(requested);
  if(requestedInterface&&!canOpenInterface(requestedInterface)){redirectAllowed();return;}
  if(routeAbortController) routeAbortController.abort();
  routeAbortController=new AbortController();
  const ticket=captureViewTicket();ticket.revision=++routeRevision;
  try{
    const h=location.hash||'#dashboard';
    if(frontendRouteUnavailable(h)) return;
    if(h==='#consumables') return await (canRead('consumables')?consumablesView():redirectAllowed());
    if(h==='#support' || h.startsWith('#support?')) return await (canRead('support')?supportView():redirectAllowed());
    if(h==='#declarations') return await (canRead('declarations')?declarationsView():redirectAllowed());
    if(h==='#analytics') return await (canRead('analytics')?analyticsView():redirectAllowed());
    if(h==='#disconnect-details' || h.startsWith('#disconnect-details?')) return await (canRead('details')?disconnectDetailsView():redirectAllowed());
    if(h==='#details' || h.startsWith('#details?')) return await (canRead('details')?detailsView():redirectAllowed());
    if(h==='#calls' || h.startsWith('#calls?')) return await (canRead('calls')?callsView():redirectAllowed());
    if(h==='#reports'){
      if(!canRead('support')) return await (redirectAllowed());
      if(typeof reportsView==='function') return await (reportsView());
      activate('reports');setHead('Rapports PDF Nelyio','Le module Rapports n’a pas été chargé.');
      app.innerHTML='<div class="flash error">Le module <code>static/support.js</code> n’est pas chargé. Recopie le correctif complet puis fais Ctrl+F5.</div>';
      return;
    }
    if(h==='#supervision'){ location.hash='#support'; return; }
    if(h==='#dashboard') return await (dashboard());
    if(h==='#inventory') return await (inventory());
    if(h.startsWith('#inventory/')) return await (inventory(decodeURIComponent(h.slice(11))));
    if(h==='#add') return await (addPc());
    if(h==='#live-supervision') return await (canRead('collection')?liveSupervisionView():redirectAllowed());
    if(h==='#live-campaigns') return await (canRead('collection')?liveCampaignsView():redirectAllowed());
    if(h==='#live-incidents' || h.startsWith('#live-incidents?')) return await (canRead('collection')?liveIncidentsView():redirectAllowed());
    if(h==='#live-search' || h.startsWith('#live-search?')) return await (canRead('calls')?liveSearchView():redirectAllowed());
    if(h==='#collection') return await (canRead('collection')?collectionView():redirectAllowed());
    if(h==='#production-health') return await (canRead('config')?productionHealthView():redirectAllowed());
    if(h==='#config') return await (configuration());
    if(h==='#classification' || h.startsWith('#classification?')) return await (classification());
    if(h==='#support-priority') return await (supportPrioritySettings());
    if(h==='#live-quality-admin') return await (canRead('config')?liveQualityAdminView():redirectAllowed());
    if(h==='#analytics-home') return await (canRead('quality')?analyticsHomeView():redirectAllowed());
    if(h==='#quality-pilotage') return await (canRead('quality')?pilotageQualityView():redirectAllowed());
    if(h==='#suspicious-calls' || h.startsWith('#suspicious-calls?')) return await (canRead('quality')?suspiciousCallsView():redirectAllowed());
    if(h==='#quality-activity') return await (canRead('quality')?qualityActivityView():redirectAllowed());
    if(h==='#quality-distributions') return await (canRead('quality')?qualityDistributionsView():redirectAllowed());
    if(h==='#quality-overview') return await (canRead('quality')?qualityOverviewView():redirectAllowed());
    if(h==='#quality-agents') return await (canRead('quality')?qualityAgentsView():redirectAllowed());
    if(h==='#quality-bases') return await (canRead('quality')?qualityBasesView():redirectAllowed());
    if(h==='#classification-groups') return await (canRead('classification')?groupWorkspaceView():redirectAllowed());
    if(h==='#quality-priorities') return await (canRead('quality')?qualityPrioritiesView():redirectAllowed());
    if(h==='#quality-queues') return await (canRead('quality')?qualityQueuesView():redirectAllowed());
    if(h==='#quality-campaigns') return await (canRead('quality')?qualityCampaignsView():redirectAllowed());
    if(h==='#policies') return await (canRead('policies')?policiesView():redirectAllowed());
    if(h==='#users') return await (users());
    if(h==='#security') return await (securityAudit());
    if(h==='#account') return await (account());
    if(h.startsWith('#pc/')) return await (detail(decodeURIComponent(h.slice(4))));
    return await (dashboard());
  }catch(e){if(e && e.name==='AbortError')return;if(!viewTicketIsCurrent(ticket))return;app.innerHTML=flash(e.message,'error')+'<button type="button" class="button" id="route-retry">Réessayer</button>';$('#route-retry').onclick=()=>route();}
}
window.addEventListener('hashchange',route);
initAuth();

/* === v12 UI compact workspace: non-destructive presentation layer === */
(()=>{
  const APP=document.getElementById('app');
  if(!APP)return;
  document.body.classList.add('ui-v12');
  const $one=(s,r=document)=>r.querySelector(s), $all=(s,r=document)=>Array.from(r.querySelectorAll(s));
  const viewName=()=>{const h=String(location.hash||'#dashboard');if(h.startsWith('#pc/'))return'pc';if(h.startsWith('#calls'))return'calls';return h.replace(/^#/,'').split('?')[0]||'dashboard';};
  const titleText=el=>String(el?.querySelector('h2,h3')?.textContent||'').trim().toLowerCase();
  const byHeading=(needle)=>$all('section.card.panel',APP).filter(el=>titleText(el).includes(needle));

  function sidebar(){
    $all('.sidebar nav a').forEach(a=>{if(!a.title)a.title=String(a.textContent||'').trim();});
    const host=$one('.top-actions');if(!host||$one('#ui-sidebar-toggle'))return;
    const b=document.createElement('button');b.type='button';b.id='ui-sidebar-toggle';b.className='button ghost ui-sidebar-toggle';b.title='Réduire ou ouvrir le menu';b.setAttribute('aria-label',b.title);b.textContent='☰';
    b.onclick=()=>{document.body.classList.toggle('ui-sidebar-collapsed');localStorage.setItem('nelyio-ui-sidebar',document.body.classList.contains('ui-sidebar-collapsed')?'1':'0');};
    host.prepend(b);if(localStorage.getItem('nelyio-ui-sidebar')==='1')document.body.classList.add('ui-sidebar-collapsed');
  }

  function addPanelCollapse(){
    $all('section.card.panel:not(.ui-collapse-ready)',APP).forEach(panel=>{
      if(panel.tagName==='DETAILS'||panel.classList.contains('form-page'))return;
      const head=$one(':scope > .panel-head',panel);if(!head)return;
      panel.classList.add('ui-collapse-ready');
      const b=document.createElement('button');b.type='button';b.className='ui-collapse-button';b.title='Réduire cette section';b.setAttribute('aria-label',b.title);b.textContent='⌄';
      b.onclick=()=>{panel.classList.toggle('ui-panel-collapsed');b.title=panel.classList.contains('ui-panel-collapsed')?'Développer cette section':'Réduire cette section';b.setAttribute('aria-label',b.title);};
      head.appendChild(b);
    });
  }

  const filterConfig={
    inventory:{target:'.filter-card',form:'#filters',advanced:['[name="ip"]','[name="gateway"]','[name="status"]']},
    support:{target:'#support-filters',form:'#support-filters',advanced:['[name="min_disconnect"]','[name="call_scope"]','.support-exclusion-slots','[name="diagnosis"]','[name="status"]']},
    analytics:{target:'#analytics-filters',form:'#analytics-filters',advanced:['[name="min_disconnect"]','[name="call_scope"]','[name="cluster_window"]','[name="cluster_min_agents"]','.support-exclusion-slots']},
    calls:{target:'#calls-filters',form:'#calls-filters',advanced:['[name="call_id"]','[name="campaign"]','[name="reason"]','[name="call_type"]','[name="call_issue"]','[name="diagnosis"]','[name="status"]']}
  };
  function directField(form,sel){const el=$one(sel,form);if(!el)return null;return el.closest('label,fieldset')||el;}
  function addFilterProgressive(view){
    const cfg=filterConfig[view];if(!cfg)return;const box=$one(cfg.target,APP),form=$one(cfg.form,APP);if(!box||!form||box.classList.contains('ui-filter-ready'))return;
    // Diagnostic already owns an accessible native advanced-filter disclosure.
    if(view==='support'&&form.querySelector('details'))return;
    box.classList.add('ui-filter-ready');cfg.advanced.forEach(sel=>{const el=directField(form,sel);if(el)el.classList.add('ui-filter-advanced-field');});
    const header=document.createElement('div');header.className='ui-filter-header';header.innerHTML='<div><strong>Filtres</strong><small>Les critères courants restent visibles. Les options secondaires sont repliées.</small></div><div class="ui-filter-actions"></div>';
    const actions=$one('.ui-filter-actions',header),advanced=document.createElement('button'),collapse=document.createElement('button');
    advanced.type=collapse.type='button';advanced.className=collapse.className='ui-filter-action';advanced.textContent='Options avancées';collapse.textContent='Réduire';
    advanced.onclick=()=>{box.classList.toggle('ui-filter-show-advanced');advanced.textContent=box.classList.contains('ui-filter-show-advanced')?'Masquer les options':'Options avancées';};
    collapse.onclick=()=>{box.classList.toggle('ui-filter-collapsed');collapse.textContent=box.classList.contains('ui-filter-collapsed')?'Afficher les filtres':'Réduire';};
    actions.append(advanced,collapse);box.prepend(header);
    if(view==='calls')return; // Keep the daily time controls available after a search.
    if(form!==box)form.addEventListener('submit',()=>setTimeout(()=>{box.classList.add('ui-filter-collapsed');collapse.textContent='Afficher les filtres';},50));
    else form.addEventListener('submit',()=>setTimeout(()=>{form.classList.add('ui-filter-collapsed');collapse.textContent='Afficher les filtres';},50));
  }

  function workspaceDefinition(view){
    if(view==='dashboard')return[
      {id:'summary',label:'Synthèse',icon:'▦',els:()=>[$one('.overview-strip',APP),$one('.status-cards',APP),$one('.dashboard-info-grid',APP),$one('.rule-banner',APP)]},
      {id:'activity',label:'Activité du parc',icon:'↻',els:()=>[$one('.grid2',APP)]}
    ];
    if(view==='pc')return[
      {id:'summary',label:'Fiche du poste',icon:'PC',els:()=>[$one('.pc-hero',APP),$one('.grid2',APP)]},
      {id:'manual',label:'Audit manuel',icon:'✎',els:()=>byHeading('changements manuels')},
      {id:'history',label:'Historique automatique',icon:'↻',els:()=>byHeading('historique automatique')}
    ];
    if(view==='users')return[
      {id:'accounts',label:'Comptes',icon:'◎',els:()=>[$one('.access-hero',APP),$one('.access-top-grid',APP),...byHeading('utilisateurs existants')]},
      {id:'rights',label:'Groupes & droits',icon:'◇',els:()=>byHeading('groupes et permissions')}
    ];
    if(view==='config')return[
      {id:'imports',label:'Données & imports',icon:'↻',els:()=>[...byHeading('source des diagnostics'),...byHeading('synchronisation automatique'),...byHeading('historique des imports')]},
      {id:'network',label:'Réseau & HTTPS',icon:'⌁',els:()=>[...byHeading('serveur web'),...byHeading('https direct')]},
      {id:'maintenance',label:'Maintenance',icon:'⚙',els:()=>[...byHeading('sauvegarde de la configuration'),...byHeading('bases de données')]}
    ];
    if(view==='support')return[
      {id:'summary',label:'Synthèse',icon:'▦',els:()=>['#support-admin-link','#support-message','#support-integrity','#support-coverage','#support-cards','#support-brief','#support-anomalies'].map(s=>$one(s,APP))},
      {id:'analysis',label:'Analyse',icon:'⌁',els:()=>['#support-clusters','#support-charts'].map(s=>$one(s,APP))},
      {id:'agents',label:'Agents',icon:'◎',els:()=>['#support-agent-context','#support-technical-analysis'].map(s=>$one(s,APP))},
      {id:'signals',label:'Signaux',icon:'!',els:()=>[$one('.support-signals',APP),$one('#support-import-panel',APP)]}
    ];
    if(view==='analytics')return[
      {id:'overview',label:'Synthèse',icon:'▦',els:()=>[$one('#analytics-overview',APP)]},
      {id:'timeline',label:'Tendances',icon:'↻',els:()=>[$one('#analytics-timeline',APP)]},
      {id:'clusters',label:'Simultanés',icon:'⌁',els:()=>[$one('#analytics-clusters',APP)]},
      {id:'recurrence',label:'Récurrence',icon:'⟳',els:()=>[$one('#analytics-recurrence',APP)]},
      {id:'agents',label:'Concentration',icon:'PC',els:()=>[$one('#analytics-agents',APP)]},
      {id:'periods',label:'Périodes',icon:'⇄',els:()=>[$one('#analytics-periods',APP)]},
      {id:'anomalies',label:'Anomalies',icon:'!',els:()=>[$one('#analytics-anomalies',APP)]}
    ];
    if(view==='calls')return[
      {id:'results',label:'Résultats',icon:'☎',els:()=>[...byHeading('résultats de la recherche'),$one('#calls-live-observations',APP)]},
      {id:'summary',label:'Synthèse',icon:'▦',els:()=>[$one('#calls-cards',APP)]},
      {id:'import',label:'Import',icon:'↥',els:()=>[$one('#calls-import-panel',APP)]}
    ];
    return null;
  }

  function applyWorkspace(view){
    const defs=workspaceDefinition(view);if(!defs||!defs.length)return;
    let nav=$one('.ui-workspace-tabs',APP);if(!nav){nav=document.createElement('nav');nav.className='ui-workspace-tabs';nav.setAttribute('aria-label','Sections de cette interface');const diagHead=view==='support'?$one('.diag-workspace > .diag-page-head',APP):null;const hero=$one(':scope > .sup-hero, :scope > .pc-hero, :scope > .classification-hub',APP);if(diagHead&&diagHead.parentElement)diagHead.insertAdjacentElement('afterend',nav);else if(hero&&hero.nextSibling)APP.insertBefore(nav,hero.nextSibling);else APP.prepend(nav);}
    defs.forEach(def=>(def.els()||[]).filter(Boolean).forEach(el=>el.dataset.uiWorkspaceGroup=def.id));
    if(APP.dataset.uiWorkspaceView!==view){APP.dataset.uiWorkspaceView=view;APP.dataset.uiWorkspace='';nav.innerHTML='';}
    if(!nav.children.length){defs.forEach(def=>{const b=document.createElement('button');b.type='button';b.dataset.uiWorkspace=def.id;b.innerHTML=`<span>${def.icon}</span>${def.label}`;b.onclick=()=>setWorkspace(view,defs,def.id);nav.appendChild(b);});}
    const available=defs.filter(def=>(def.els()||[]).some(Boolean));
    $all('button[data-ui-workspace]',nav).forEach(b=>b.hidden=!available.some(d=>d.id===b.dataset.uiWorkspace));
    let active=APP.dataset.uiWorkspace; if(!available.some(d=>d.id===active))active=available[0]?.id||'';setWorkspace(view,defs,active,false);
  }
  function setWorkspace(view,defs,id,scroll=false){
    APP.dataset.uiWorkspace=id;
    defs.forEach(def=>(def.els()||[]).filter(Boolean).forEach(el=>el.classList.toggle('ui-workspace-hidden',def.id!==id)));
    $all('.ui-workspace-tabs button',APP).forEach(b=>b.classList.toggle('active',b.dataset.uiWorkspace===id));
    if(scroll){const nav=$one('.ui-workspace-tabs',APP);nav?.scrollIntoView({behavior:'smooth',block:'start'});}
  }

  function compactSupportMetrics(){
    const grid=$one('#support-cards .support-detail-metrics',APP);if(!grid)return;const items=Array.from(grid.children);items.forEach((el,i)=>el.classList.toggle('ui-secondary-metric',i>=6));
    let box=$one('#support-cards .ui-metrics-more',APP);if(items.length<=6){box?.remove();return;}if(box)return;
    box=document.createElement('div');box.className='ui-metrics-more';const b=document.createElement('button');b.type='button';b.textContent=`Voir les ${items.length-6} indicateurs supplémentaires`;b.onclick=()=>{grid.classList.toggle('ui-metrics-expanded');b.textContent=grid.classList.contains('ui-metrics-expanded')?'Réduire les indicateurs':`Voir les ${items.length-6} indicateurs supplémentaires`;};box.appendChild(b);grid.after(box);
  }

  function enhance(){
    sidebar();const view=viewName();addFilterProgressive(view);applyWorkspace(view);addPanelCollapse();compactSupportMetrics();
  }
  let scheduled=false;const schedule=()=>{if(scheduled)return;scheduled=true;requestAnimationFrame(()=>{scheduled=false;enhance();});};
  new MutationObserver(schedule).observe(APP,{childList:true,subtree:true});
  window.addEventListener('hashchange',()=>{APP.dataset.uiWorkspaceView='';APP.dataset.uiWorkspace='';schedule();});
  schedule();
})();

// RC29 Phase 5 - shared sortable-table contract outside the Live Center.
// Cycle: ASC -> DESC -> default. Missing/unknown values stay last in both directions.
const qualityTableSortState=new Map();
const qualityMissingSortStrings=new Set(['','—','-','inconnu','unknown','non observé','non observe','non calculable','n/a','null','none']);
function qualitySortTypeFromLabel(label){
 const x=String(label||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
 if(/date|heure|periode|debut|fin|derniere/.test(x))return 'date';
 if(/duree|temps|attente|asa|conversation|perdu/.test(x))return 'duration';
 if(/%|qos|taux|part/.test(x))return 'percentage';
 if(/etat|statut|activation|priorite|diagnostic/.test(x))return 'state';
 if(/recu|traite|abandon|appel|agent[s]? affecte|incident|nombre|total|jour[s]? actif|compteur/.test(x))return 'number';
 return 'string';
}
function qualitySortMissing(value){
 if(value===null||value===undefined)return true;
 if(typeof value==='number')return !Number.isFinite(value);
 return qualityMissingSortStrings.has(String(value).trim().toLocaleLowerCase('fr'));
}
function qualityParseLocalizedNumber(text){
 const t=String(text??'').trim().replace(/[\s\u00a0\u202f]/g,'').replace(',','.').replace(/%$/,'');
 const n=Number(t);if(Number.isFinite(n))return n;
 const m=t.match(/[-+]?\d+(?:\.\d+)?/);return m?Number(m[0]):null;
}
function qualityParseDuration(text){
 const t=String(text??'').trim().toLowerCase();if(qualitySortMissing(t))return null;
 if(/^\d+(?::\d{1,2}){1,2}$/.test(t)){const a=t.split(':').map(Number);return a.length===3?a[0]*3600+a[1]*60+a[2]:a[0]*60+a[1];}
 let total=0,found=false;for(const [re,mul] of [[/(\d+(?:[.,]\d+)?)\s*h/,3600],[/(\d+(?:[.,]\d+)?)\s*m(?:in)?\b/,60],[/(\d+(?:[.,]\d+)?)\s*s(?:ec)?\b/,1]]){const m=t.match(re);if(m){total+=Number(m[1].replace(',','.'))*mul;found=true;}}
 if(found)return total;return qualityParseLocalizedNumber(t);
}
function qualityParseDate(text){
 const t=String(text??'').trim();if(qualitySortMissing(t))return null;
 let m=t.match(/^(\d{2})\/(\d{2})\/(\d{4})(?:\s+(\d{1,2}):(\d{2})(?::(\d{2}))?)?/);if(m)return Date.UTC(+m[3],+m[2]-1,+m[1],+(m[4]||0),+(m[5]||0),+(m[6]||0));
 m=t.match(/^(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{1,2}):(\d{2})(?::(\d{2}))?)?/);if(m)return Date.UTC(+m[1],+m[2]-1,+m[3],+(m[4]||0),+(m[5]||0),+(m[6]||0));
 const n=Date.parse(t);return Number.isFinite(n)?n:null;
}
function qualityStateRank(text){
 const x=String(text||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().trim();
 const ranks=[['critique',90],['urgent',85],['eleve',80],['actif',70],['en appel',65],['disponible',60],['pause',50],['partiel',45],['post-appel',40],['inactif',30],['deconnecte',20],['non observe',10],['inconnu',0]];
 for(const [k,v] of ranks)if(x.includes(k))return v;return x;
}
function qualitySortValue(value,type='string'){
 if(qualitySortMissing(value))return null;const t=String(value).trim();
 if(type==='number'||type==='percentage')return qualityParseLocalizedNumber(t);
 if(type==='duration')return qualityParseDuration(t);
 if(type==='date'||type==='timestamp')return qualityParseDate(t);
 if(type==='state')return qualityStateRank(t);
 return t;
}
function qualitySortCompare(a,b,direction='asc',type='string'){
 const av=qualitySortValue(a,type),bv=qualitySortValue(b,type),am=av===null,bm=bv===null;
 if(am||bm){if(am&&bm)return 0;return am?1:-1;}
 let cmp;if(typeof av==='number'&&typeof bv==='number')cmp=av-bv;else cmp=String(av).localeCompare(String(bv),'fr',{numeric:true,sensitivity:'base'});
 return direction==='desc'?-cmp:cmp;
}
function qualitySortLoad(key){
 if(qualityTableSortState.has(key))return qualityTableSortState.get(key);
 try{const raw=sessionStorage.getItem('nelyio.rc29.sort.'+key);if(raw){const v=JSON.parse(raw);if(Number.isInteger(v.column)&&['asc','desc'].includes(v.direction)){qualityTableSortState.set(key,v);return v;}}}catch(_){}
 return null;
}
function qualitySortSave(key,state){qualityTableSortState.set(key,state);try{if(state)sessionStorage.setItem('nelyio.rc29.sort.'+key,JSON.stringify(state));else sessionStorage.removeItem('nelyio.rc29.sort.'+key);}catch(_){}}
function qualityMakeSortable(table,key){
 if(!table||!table.tHead||!table.tBodies.length||table.dataset.qualitySortReady)return;
 table.dataset.qualitySortReady='1';const headers=Array.from(table.tHead.rows[0].cells),body=table.tBodies[0],buttons=[];
 Array.from(body.rows).forEach((r,i)=>{if(r.dataset.rc29OriginalIndex===undefined)r.dataset.rc29OriginalIndex=String(i);});
 const apply=()=>{const state=qualitySortLoad(key),rows=Array.from(body.rows).filter(r=>r.cells.length===headers.length).map((row,index)=>({row,index,base:Number(row.dataset.rc29OriginalIndex??index)}));
  if(state){const h=headers[state.column],type=h?.dataset.sortType||qualitySortTypeFromLabel(h?.textContent||buttons[state.column]?.dataset.label||'');rows.sort((a,b)=>{const ac=a.row.cells[state.column],bc=b.row.cells[state.column],av=ac?.dataset.sortValue??ac?.textContent??'',bv=bc?.dataset.sortValue??bc?.textContent??'';return qualitySortCompare(av,bv,state.direction,type)||(a.base-b.base);});}
  else rows.sort((a,b)=>a.base-b.base);rows.forEach(x=>body.appendChild(x.row));
  headers.forEach((h,i)=>{const active=state&&i===state.column;h.setAttribute('aria-sort',active?(state.direction==='asc'?'ascending':'descending'):'none');if(buttons[i])buttons[i].textContent=buttons[i].dataset.label+(active?(state.direction==='asc'?' ↑':' ↓'):' ↕');});};
 headers.forEach((h,column)=>{const label=h.textContent.trim();if(!label||h.dataset.noSort==='1')return;const type=h.dataset.sortType||qualitySortTypeFromLabel(label);h.dataset.sortType=type;const button=document.createElement('button');button.type='button';button.className='quality-sort-button';button.dataset.label=label;button.textContent=label+' ↕';button.title='Trier par '+label;h.setAttribute('aria-sort','none');button.onclick=()=>{const prev=qualitySortLoad(key);let next;if(!prev||prev.column!==column)next={column,direction:'asc'};else if(prev.direction==='asc')next={column,direction:'desc'};else next=null;qualitySortSave(key,next);apply();};h.textContent='';h.appendChild(button);buttons[column]=button;});
 apply();
}
// End RC29 Phase 5 sortable-table contract.
