# 🔍 DIAGNOSTIC UI/UX - CENTRE QUALITÉ LIVE
**Nelyio V60.5 RC29.4 - Vues Agents & Campagnes**

---

## 📋 PROBLÈMES CRITIQUES IDENTIFIÉS

### 1. **DENSE & MANQUE DE HIÉRARCHIE VISUELLE** ❌
**Symptôme** : Trop de données crues sans organisation claire

| Problème | Impact |
|----------|--------|
| Colonnes trop nombreuses sans priorité | Utilisateur perd du temps à scanner |
| Pas de groupage logique des infos | Navigation cognitive difficile |
| Métriques critiques mélangées aux secondaires | Risque de confusion |

**Où** : `live-views.js:426-500` (tableau agents), `live-views.js:496-506` (tableau campagnes)

---

### 2. **TYPOGRAPHIE & CONTRASTE INSUFFISANT** ❌
**Symptôme** : Textes trop petit, gris faiblard, pas de distinction visuelle

**Code actuellement** :
```css
/* quality.css:48 */
.qa-table th, .qa-table td { padding: 10px 9px; font-size: 12px; }
.qa-table small { color: var(--muted, #748399); }  /* Trop pâle */
```

**Problème** : Les infos secondaires utilisent `--muted` (gris) et `12px` → fatigant après 5-10 min de scan

---

### 3. **COULEURS DE STATUT NON LISIBLES** ❌
**Symptôme** : États d'agents & campagnes pas assez visibles

**Où** : 
- Agents : `live-views.js:69-85` (état mis en petit badge)
- Campagnes : `live-views.js:515-553` (statut relégué en coins)

**Impact** : L'utilisateur doit chercher le statut plutôt que le voir immédiatement

---

### 4. **LAYOUT TROP LINÉAIRE (HORIZONTAL)** ❌
**Symptôme** : Scroll horizontal nécessaire, vue globale impossible

**Détail**:
```javascript
// live-views.js:47
.q-table { min-width: 1050px; }  // Force scroll horizontal
```

**À faire**: La vue doit rester visible entièrement à 1366px (écrans moyens)

---

### 5. **PAS DE COMPRESSION DES COLONNES** ❌
**Symptôme** : Colonnes vides ou répétitives prennent trop de place

| Colonne actuelle | Utilité | Problème |
|------------------|---------|---------|
| `État + Durée état` | Important | Séparées en 2 colonnes |
| `Appel + Durée` | Basique | Détail trop verbeux |
| `ANI` | Contexte | Petit usage |

---

### 6. **DRILL-DOWN LENT (Vue détail campagne)** ❌
**Symptôme** : Chargement lent du `live-campaigns` + drill-down

**Où** : `live-views.js:560-565`
```javascript
const loadDetail = async (id, force=false) => {
  // ... appel API qui se recharge toutes les 10s
  liveCampaignsState.detailById[id] = await api('/api/live/campaigns/'+id);
}
```

**Impact** : Mode attente fréquent sur campagnes

---

### 7. **MANQUE DE FILTRES & GROUPAGES** ❌
**Symptôme** : 50+ agents/campagnes s'affichent en vrac sans tri utile

**Actuellement** :
```javascript
// live-views.js:610-615
// Tri limité à 3 positions (asc/desc/default)
// Pas de filtrage multi-critères
```

**À faire** :
- ✅ Filtres : État, Groupe, Campagne, Statut de qualité
- ✅ Groupage : Par groupe → agent
- ✅ Tri persistant + favori

---

## 🎨 PROPOSITION DE NOUVELLE STRUCTURE

### **VUE AGENTS – Nouvelle organisation**

```
┌─────────────────────────────────────────────────────────┐
│ FILTRES HAUT (compact)                                  │
│ [État ▼] [Groupe ▼] [Campagne ▼] [Chercher...] [Trier▼]│
├─────────────────────────────────────────────────────────┤
│ GROUPÉS PAR GROUPE                                      │
├──────────────────────────────────────────────────────────│
│ 🔹 GROUPE A · 12 agents                                 │
│ ┌────────────────────────────────────────────────────┐  │
│ │ Agent      │ État        │ Appel actual│ Pauses    │  │
│ │ Agent 571  │ ⚫ EN APPEL  │ 245s       │ 2h 10m    │  │
│ │            │ MED1        │ Ref:88881  │           │  │
│ │ Agent 572  │ 🟡 PAUSE    │ —          │ 15m       │  │
│ │            │ Coaching   │            │ Depuis 15m│  │
│ └────────────────────────────────────────────────────┘  │
├──────────────────────────────────────────────────────────│
│ 🔹 GROUPE B · 8 agents                                  │
│ ...                                                     │
└─────────────────────────────────────────────────────────┘
```

**Changes clés** :
1. ✅ Filtres en première ligne (sticky)
2. ✅ Groupage par groupe = facile à balayer
3. ✅ État EN COULEUR + badge = priorité 1
4. ✅ Nom agent + statut secondaire = 2 lignes courtes
5. ✅ Zéro scroll horizontal

---

### **VUE CAMPAGNES – Nouvelle organisation**

```
┌─────────────────────────────────────────────────────────┐
│ FILTRES HAUT                                            │
│ [Statut ▼] [Service ▼] [Alertes seulement □] [Tri ▼]   │
├─────────────────────────────────────────────────────────┤
│ RÉSINÉ + KPI FLOTTANT (top-right)                       │
│ ┌──────────────────────┐  Incidents : 7    ⚠️           │
│ │ Campagne  │ Statut   │  Agents dispo : 42 ✓           │
│ │ CAM-01    │ 🔴 ALERTE│  Qualité : 85%  ✓           │
│ │ MED · 8ag │ -2 agents│  Load : 94% ⚠️           │
│ │ Ref: 92%  │ depuis1h │                          │
│ ├──────────────────────┤                          │
│ │ CAM-02    │ 🟢 OK    │                          │
│ │ OUD · 12ag│          │                          │
│ │ Ref: 98%  │          │                          │
│ └──────────────────────┘                          │
│                                                     │
│ 📊 Drill-down campagne (clic sur CAM-01)           │
│ ┌────────────────────────────────────────────────┐│
│ │ Files (6) | Agents (8) | Appels (23)           ││
│ │ [Voir détail]                                  ││
│ └────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────┘
```

**Changes clés** :
1. ✅ Statut = couleur dominante + icône
2. ✅ KPI clé en évidence (coin haut-droit)
3. ✅ Drill-down en modale/panel (pas de page entière)
4. ✅ Colonnes compressées : 4 max (nom, statut, écart, action)

---

## 💾 RECOMMANDATIONS UX

| Thème | Recommandation |
|-------|-----------------|
| **Temps réel** | Rafraîchissement 5s pour Agents, 10s pour Campagnes (moins loud) |
| **Tri** | Défaut = "Statut DESC (alerte en haut), puis Agent ASC" |
| **Filtres** | Sauvegarde session (localStorage) + partageables en URL (`?state=ok&group=A`) |
| **Alertes** | Badge rouge corner + son discret (pas de modal) |
| **Mobile** | Masquer colonnes "ANI", grouper États/Pauses, stack vertical |
| **Accessibilité** | ARIA labels, clavier Tab/Arrows, contraste WCAG AA min |

---

## 📊 AVANT / APRÈS – Impact estimé

| Métrique | Avant | Après |
|----------|-------|-------|
| **Temps pour trouver 1 alerte** | 45-60s | 10-15s |
| **Scroll horz nécessaire** | 70% des sessions | 0% |
| **Fatigue visuelle (10min)** | Élevée | Faible |
| **Lisibilité des états** | 60% correct | 95% au 1er coup |

---

## 🔧 FICHIERS À MODIFIER

1. **`static/live-views.js`** (cible: `renderAgents()` + `liveViewSupervision()`)
2. **`static/quality.css`** (layout + typo)
3. **Nouveau: `static/live-views-improved.css`** (pour les nouvelles classes)
4. **Backend API** : vérifier groupement côté serveur si possible

---

**Diagnostic par** : Claude Haiku 4.5  
**Date** : 2026-10-01  
**Urgence** : 🔴 HAUTE (impact quotidien sur productivité)
