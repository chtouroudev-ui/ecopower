# RC29.3 — Étape 1 — Réalignement de 3 tests

Base : `Nelyio-ARCH V60.5 RC29.3 LIVE_SIMPLE`.

Périmètre strict : tests uniquement. Aucun code applicatif, formule QoS, tri, identité, distribution, signalisation, groupe ACTIVE, schéma ou donnée de base modifié.

## 1. `audit_regression_test.py::test_source_totals_filters_and_distribution`

### Ancienne assertion QoS
```python
assert t['qos_rate']==pytest.approx(200/3)
```

### Nouvelle assertion QoS
```python
assert t['qos_rate']==pytest.approx(100/3)  # 1 traité / (3 reçus - 0 clôturé - 0 racc. avant file)
```

Justification : la fixture contient, dans la fenêtre 08:00–19:00, 3 appels reçus, 1 appel traité, 0 clôturé et 0 raccroché avant file. La formule canonique RC29.1 donne donc `1 / (3 - 0 - 0) × 100 = 33,333... %`.

Le même test contenait une deuxième assertion devenue obsolète car `quality_distributions` expose désormais explicitement les composantes QoS :

### Ancienne assertion Distribution
```python
assert dist['total']=={'received':3,'treated':1,'answered':1,'abandoned':1}
```

### Nouvelle assertion Distribution
```python
assert dist['total']=={
    'received':3,
    'treated':1,
    'answered':1,
    'abandoned':1,
    'closed':0,
    'hangup_before_queue':0,
    'qos':pytest.approx(100/3),
}
```

Cette modification ne réduit pas le contrôle : elle vérifie davantage de champs et confirme la cohérence de la QoS dans Distributions.

## 2. `live_operations_phase15_test.py::test_live_ui_exposes_operational_agent_and_campaign_detail`

### Ancienne assertion
```python
assert 'Mise en attente appel' in live
```

### Nouvelles assertions
```python
assert "hold:'Mise en attente'" in live
assert 'Mise en attente obs.' in live
assert 'liveCallHold' in live
```

Justification : la fonctionnalité HOLD explicite n'a pas disparu. Dans RC29.3 :
- l'état `hold` est affiché comme `Mise en attente` ;
- le détail des appels affiche la colonne `Mise en attente obs.` ;
- le rendu dédié passe par `liveCallHold()`.

Le test reste donc strictement centré sur la mise en attente explicite observée, distincte de l'attente patient en file, et il est renforcé par trois preuves UI/code au lieu d'un seul ancien libellé.

## 3. `rc29_qos_supervision_patch_test.py::test_supervision_workstation_contract`

### Anciennes assertions
```python
assert 'Agents · supervision immédiate' in js
assert 'Périmètres · campagnes par défaut' in js
```

### Nouvelles assertions
```python
assert "sessionStorage.getItem('nelyio.live.layout')||'agents'" in js
assert '<option value="agents">Agents</option>' in js
assert '<option value="scopes">Campagnes / périmètres</option>' in js
assert '<option value="split">Double vue</option>' in js
assert 'live-supervision-rail' in js
assert 'live-detail-drawer' in js
```

Justification : RC29.3 ne livre plus les anciens titres RC29.1. Le contrat actuel est :
- vue Agents par défaut, mémorisée en session ;
- Campagnes/Périmètres en vue alternative ;
- Double vue optionnelle ;
- rail KPI ;
- tiroir Détails.

Les assertions CSS historiques du même test sont conservées (`workstation`, `grid`, en-têtes sticky). Le test vérifie donc toujours la présence de la disposition de supervision attendue, avec davantage de points structurels qu'avant.

## Exécution ciblée

Commande :
```text
python -m pytest -q \
  audit_regression_test.py::test_source_totals_filters_and_distribution \
  live_operations_phase15_test.py::test_live_ui_exposes_operational_agent_and_campaign_detail \
  rc29_qos_supervision_patch_test.py::test_supervision_workstation_contract
```

Résultat : **3 passed**.

## Intégrité

- Aucun fichier applicatif `.py` autre que les trois fichiers de test ci-dessus n'a été modifié.
- Aucun fichier frontend `.js/.css` n'a été modifié.
- Aucun fichier `.db`, `.db-wal`, `.db-shm` ou `.db-journal` n'a été modifié par cette étape.
- Aucune suite globale n'a été lancée : elle appartient à l'étape 2 et attend validation de l'étape 1.
