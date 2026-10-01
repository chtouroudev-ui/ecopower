# 📖 GUIDE D'IMPLÉMENTATION - CENTRE QUALITÉ LIVE

**Nelyio V60.5 RC29.4** | Réparation UI/UX Agents & Campagnes

---

## 🚀 ÉTAPES D'INTÉGRATION

### 1️⃣ AJOUTER LES FICHIERS

#### CSS amélioré
```bash
cp live-views-improved.css → /static/live-views-improved.css
```

#### JavaScript amélioré
```bash
cp live-views-improvements.js → /static/live-views-improvements.js
```

### 2️⃣ CHARGER LES RESSOURCES

Dans `index.html`, après les CSS existants :

```html
<!-- Après les stylesheets existants -->
<link rel="stylesheet" href="/static/live-views-improved.css?v=RC29_4-FIX1">
```

Et après les scripts, avant `app.js` :

```html
<!-- Avant app.js, après live-views.js -->
<script src="/static/live-views-improvements.js?v=RC29_4-FIX1"></script>
```

### 3️⃣ INTÉGRER LES FONCTIONS RENDU

Dans `static/live-views.js`, remplacer les fonctions de rendu des agents et campagnes :

#### Agents - Trouver et remplacer

**Avant (lignes ~420-430)** :
```javascript
// Ancien : renderAgentsTable(rows) {...}
```

**Après** :
```javascript
// Utiliser la nouvelle fonction
function renderAgentsTable(rows) {
  if (!window.LiveImprovements) {
    // Fallback sur ancien code
    return oldRenderAgentsTable(rows);
  }
  return window.LiveImprovements.renderAgentsImproved({
    agents: rows
  }, window.LiveImprovements.filters.agentFilters.state);
}
```

#### Campagnes - Même approche

**Avant (~ligne 544)** :
```javascript
// Ancien : liveViewSupervision() -> rendu campagnes
```

**Après** :
```javascript
// Dans la section campagnes
if (window.LiveImprovements) {
  app.innerHTML = window.LiveImprovements.renderCampaignsImproved(
    {campaigns: d.campaigns || []},
    window.LiveImprovements.filters.campaignFilters.state
  );
} else {
  // Ancien code fallback
}
```

---

## 🎨 CUSTOMISATION

### Couleurs des états

**Fichier** : `live-views-improved.css` (lignes 176-210)

```css
.live-agent-state.in-call {
  background: #fed7d7;    /* Rouge clair */
  color: #742a2a;         /* Texte rouge foncé */
}
```

Adapter les couleurs à ta charte :
- `--alert`: Rouge (#f56565)
- `--warning`: Orange (#ed8936)
- `--ok`: Vert (#48bb78)
- `--muted`: Gris (#718096)

### Taille police

Pour agrandir les colonnes agents (notamment sur mobile) :

```css
.live-agents-table td {
  font-size: 14px;  /* Actuellement 14px, augmenter à 15px si besoin */
  padding: 12px;    /* Hauteur ligne */
}
```

### Nombre de colonnes campagnes

```css
.live-campaigns-grid {
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  /* Changer 240px pour + ou - de colonnes */
  /* 200px = grille dense, 280px = aérée */
}
```

---

## ✅ CHECKLIST DE TEST

### Agents
- [ ] Filtres s'affichent (État, Groupe, Campagne)
- [ ] États agents = colorés (rouge/vert/orange/gris)
- [ ] Groupage par groupe = lisible
- [ ] Zéro scroll horizontal sur écran 1366px
- [ ] Recherche agent fonctionne
- [ ] Tri persisté en sessionStorage
- [ ] Mobile : stack vertical OK

### Campagnes
- [ ] Grille 3 colonnes (ou +) responsive
- [ ] Badges statut colorés (🔴 alerte, 🟡 warning, 🟢 ok)
- [ ] KPI panel sticky (en haut-droite)
- [ ] Cards cliquables (hover shadow)
- [ ] Filtres Statut & Alertes seulement
- [ ] Total incidents visible en KPI
- [ ] Mobile : 1 colonne OK

### Performance
- [ ] Rafraîchissement 5s (agents) & 10s (campagnes)
- [ ] Pas de lag lors du scroll
- [ ] Animations fluides (~60fps)
- [ ] Cache localStorage/sessionStorage OK

### Accessibilité
- [ ] Tab navigation OK
- [ ] Contraste WCAG AA (4.5:1 min)
- [ ] ARIA labels sur filtres
- [ ] Clavier Arrows dans tables

---

## 🔧 TROUBLESHOOTING

### Problème : Filtres ne persistent pas
**Cause** : sessionStorage désactivé ou blocage navigateur

**Fix** :
```javascript
// Dans live-views-improvements.js, ligne 25
try {
  sessionStorage.setItem(...)
} catch (e) {
  console.warn('SessionStorage unavailable, using memory cache');
}
```

### Problème : Statuts agents gris (pas colorés)
**Cause** : Classes CSS non trouvées

**Check** :
```bash
# Vérifier que live-views-improved.css est chargé
curl http://localhost:9051/static/live-views-improved.css
# Devrait retourner le CSS, pas 404
```

### Problème : Groupage non appliqué
**Cause** : Données agents sans `group_id` ou `group`

**Fix** :
```javascript
// Ajouter fallback dans backend
// live_quality.py
agents = [
  {
    ...agent,
    group_id: agent.group_id or agent.group or 'Non assigné',
  }
  for agent in agents
]
```

### Problème : KPI panel ne s'affiche pas
**Cause** : Écran < 1200px (se passe en 1 colonne sur mobile, normal)

**Vérifier** : Devtools → Responsive → Desktop 1400px

---

## 📊 AVANT/APRÈS – CODE

### Avant (live-views.js:426)
```javascript
const key='live-agents';
return `<tr>
  ${rc29SortHeader(key,'agent','Agent','string')}
  ${rc29SortHeader(key,'state','État','state')}
  ${rc29SortHeader(key,'callDuration','Appel total','duration')}
  ${rc29SortHeader(key,'campaign','Campagne','string')}
  ${rc29SortHeader(key,'handled','Traités','number')}
  ${rc29SortHeader(key,'pauseDuration','Pauses','duration')}
  ${rc29SortHeader(key,'offlineDuration','Déconnecté','duration')}
  ${rc29SortHeader(key,'ani','ANI','string')}
</tr>`;
```
**Problem** : 8 colonnes, scroll horizontal nécessaire

### Après (live-views-improvements.js)
```javascript
return `<tr>
  ${rc29SortHeader(key,'agent','Agent','string')}
  ${rc29SortHeader(key,'state','État','state')}        <!-- Coloré -->
  ${rc29SortHeader(key,'callDuration','Appel','duration')}
  ${rc29SortHeader(key,'pauseDuration','Pauses','duration')}
</tr>`;
```
**Solution** : 4 colonnes max, responsive

---

## 🌍 DÉPLOIEMENT EN PRODUCTION

### 1. Test local
```bash
# Lancer serveur local
python app.py
# Vérifier sur http://localhost:9051/#live-supervision
```

### 2. Feature flag (optionnel)
```python
# app.py ou routes_quality.py
USE_IMPROVED_LIVE_UI = os.getenv('LIVE_UI_IMPROVED', '1') == '1'

@route('/api/live/config')
def live_config():
  return {
    'use_improved_ui': USE_IMPROVED_LIVE_UI,
    ...
  }
```

Puis dans JS :
```javascript
if (config.use_improved_ui) {
  html = window.LiveImprovements.renderAgentsImproved(...);
} else {
  html = oldRender(...);
}
```

### 3. Déployer
```bash
# Versionner les fichiers
cp live-views-improved.css → static/
cp live-views-improvements.js → static/

# Mettre à jour index.html (lien CSS + script)
# Commit & push
git add static/live-views-improved.*
git commit -m "live-ui: improve clarity, add grouping & colors"
git push
```

---

## 📈 MONITORING

### Métriques à tracker (Google Analytics ou similaire)
```javascript
// Dans live-views-improvements.js
if (window.gtag) {
  gtag('event', 'live_agents_filter_applied', {
    filter_type: 'state',
    filter_value: filters.state
  });
}
```

### Erreurs à monitorer
```javascript
try {
  window.LiveImprovements.renderAgentsImproved(...);
} catch (e) {
  console.error('LiveUI render error:', e);
  sentry.captureException(e); // si Sentry setup
  // Fallback sur ancien rendu
}
```

---

## 📝 NOTES IMPORTANTES

1. **Backward Compatibility** : L'ancien code reste disponible (fallback)
   - Si JS échoue, tableau complet s'affiche (ancien style)
   - Si CSS échoue, tables restent lisibles

2. **Performance** :
   - Groupage JS côté client (pas API supplémentaire)
   - Filtres en sessionStorage (~5KB max)
   - Pas de requête supplémentaire

3. **Évolutivité** :
   - Config en haut du fichier (couleurs, refresh, etc.)
   - Facile à adapter à de nouveaux statuts
   - Extensible pour drill-down campagnes

---

## 🤝 SUPPORT

**Questions ?**
- Voir `DIAGNOSTIC_UI_UX.md` pour contexte complet
- Voir `MOCKUP_UI_REPAIRED.html` pour maquette visuelle
- Vérifier tests sur `#live-supervision` & `#live-campaigns`

**Maintenance** :
- Mise à jour tous les 6 mois (nouveaux états agents)
- Alerte : si plus de 200 agents/campagnes, optimiser `groupBy()`

---

**Version** : RC29.4 FIX1  
**Auteur** : Claude Haiku 4.5  
**Date** : 2026-10-01
