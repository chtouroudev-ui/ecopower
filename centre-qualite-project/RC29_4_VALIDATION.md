# Nelyio-ARCH V60.5 RC29.4 — Validation finale

## Périmètre

RC29.4 part de RC29.3 Live Native et traite deux chantiers : automatiser le Collecteur Live sans clic quotidien et rendre le Centre Qualité Live plus lisible et plus rapide, puis corriger les KPI Campagnes/Disponibles observés dans les dernières itérations UI.

## Avant / après — Collecteur Live

### Avant RC29.4

Chaque journée nécessitait Administration > Collecteur Live > Tester le navigateur > Démarrer cette journée. Sans session déjà créée, l'ouverture ultérieure d'Edge ne déclenchait rien. Le bouton Tester pouvait en outre enregistrer l'identifiant CDP précis d'un onglet, ce qui fragilisait une reconnexion après recréation de cet onglet.

### Après RC29.4

- `auto_capture` est persistant et activé par défaut.
- `active_days`, heure de début et heure de fin sont persistants. Tous les jours sont actifs par défaut afin de ne pas inventer une règle lundi-vendredi.
- Dans la plage autorisée, le service crée au plus une session automatique du jour avec `actor=auto`, puis utilise le `claim/lease` existant. Deux workers concurrents ne créent pas deux sessions.
- Un arrêt manuel est persistant pour la journée : l'automatisme ne redémarre pas derrière l'utilisateur. Le lendemain, le verrou n'est plus applicable. Une réactivation explicite autorise un nouveau démarrage le même jour.
- Une session automatique utilise toujours `target_id=''`. Si un seul onglet correspond, il est pris automatiquement. Zéro ou plusieurs onglets produisent un état d'attente et un nouvel essai toutes les 5–10 s.
- Edge ou l'onglet peut être fermé puis rouvert pendant la journée : la session reste vivante et se reconnecte sans recréer la journée.
- Le changement de jour clôture une session antérieure arrivée à terme puis autorise la nouvelle session quotidienne.
- L'interface affiche clairement Détection automatique, En attente d'Edge, Onglet détecté, Capture en cours et Arrêtée manuellement. Tester / Démarrer / Arrêter restent disponibles en secours.

### Désactiver l'automatisme

Dans **Administration > Collecteur Live**, désactiver l'interrupteur **Détection automatique**. Le réglage est enregistré. Pour arrêter uniquement la journée courante tout en gardant l'automatisme pour demain, utiliser **Arrêter** : Nelyio marque la journée comme arrêtée manuellement et ne relance pas la capture avant le lendemain. Une réactivation explicite de Détection automatique lève ce blocage pour la journée courante.

## Avant / après — Centre Qualité Live

### Lisibilité

- Rail desktop porté à 220–240 px et repliable, avec état mémorisé.
- Qualité globale, nombre d'alertes actives et fraîcheur Hermes toujours visibles.
- Texte opérationnel >= 12 px dans les règles finales de RC29.4.
- États agents distingués par texte + couleur + symbole.
- En-têtes collants et scroll vertical interne par colonne opérationnelle.
- Sur tablette, Agents / Campagnes / Double vue masque réellement les panneaux selon la sélection.

### Rapidité d'usage

- Puces avec compteurs : Tous, En appel (appel + HOLD), Disponible, Pause, Post-appel, Non observé.
- Clic sur une alerte : recentrage direct vers l'agent ou la campagne lorsque cette identité est disponible.
- Groupe et disposition mémorisés.
- Mode Mur d'écran optionnel.

### Campagnes et agents — R10

- Campagnes reste sans colonne Statut et affiche Attente, En cours, Reçus, Traités, Abandonnés, QoS et Agents.
- Le bug de portée JavaScript `latestPayload` dans le rendu Campagnes est supprimé : les diagnostics Hermes sont passés explicitement à la fonction de rendu.
- Les états Hermes `Ready` et `Available` rejoignent les états `Waiting`, `Disponible`, `Prêt` dans la catégorie Disponible. `Mise en attente` / HOLD reste une catégorie d'appel distincte.
- La jointure campagne/file utilise d'abord la configuration, puis les couples campagne+LineId réellement observés. RC29.4 ajoute uniquement un fallback exact `InitQueue.name == campaign_name`; aucun fuzzy matching n'est utilisé.
- Un agent réellement observé sur le LineId/campagne n'est plus retiré du périmètre Live parce qu'une affectation ACTIVE importée manque. Cela ne modifie ni groupe historique ni KPI importé.
- Pour une campagne mono-file uniquement, le compteur UpQuR `agents_available_on_queue` peut servir de fallback lorsque l'état individuel Disponible n'est pas observable. Les compteurs de plusieurs files ne sont jamais additionnés afin d'éviter un double compte.
- Traités / Abandonnés / QoS viennent d'UpQuH lorsqu'il est présent. Sans preuve UpQuH, l'interface garde `—`.
- QoS native conserve la formule canonique : `Traités / (Reçus - Clôturés - Raccrochés avant file) × 100`; dénominateur <= 0 => `—`.
- Agents : `Appel total` est séparé de la durée de l'état; pendant HOLD, la durée HOLD et la durée totale de l'appel sont visibles simultanément. Traités, Pauses, Déconnecté et ANI sont conservés.
- Les campagnes sont toutes dans le scroll interne, sans pagination de 10 lignes.

## Tests et régressions

La suite complète du projet a été exécutée après mise à jour des cinq assertions de texte/version devenues obsolètes avec l'interface RC29.4. Résultat final : **296 tests passés, 0 échec**. Les tests couvrent notamment création automatique, absence de doublon, race Stop/auto, changement de jour, claim/lease, attente Edge, onglet recréé, reconnexion de la même session, interface Collecteur, lisibilité/usage Centre Live, mapping Campagnes, compteurs natifs UpQuR/UpQuH et invariants HOLD/Waiting.

La syntaxe Python des fichiers racine et la syntaxe JavaScript de `static/*.js` sont vérifiées pendant le gate final.

## Invariants vérifiés

- Formule QoS canonique inchangée; `—` si dénominateur <= 0.
- Inconnu != zéro; Non observé conservé.
- Tri 3 états et valeurs absentes en bas conservés.
- Réconciliation des lignes Agents par `agent_id` conservée.
- Protection contre réponses API obsolètes conservée.
- CDP local 127.0.0.1; aucune exécution JavaScript dans la page; collecte ANI toujours soumise à l'option/permission existante.
- Une journée par session, données brutes du jour courant.
- Permissions `collection` et scopes groupes inchangés.
- Aucune migration destructive ni reset de base métier.

## Limites de la validation dans cet environnement

Le gate automatisé ne remplace pas une recette sur le serveur Windows réel avec votre session Hermes authentifiée. Le comportement Edge/CDP a été validé par tests unitaires/intégration du Manager et du store, mais pas contre votre navigateur Edge Windows réel dans ce conteneur. `OPEN_EDGE_CAPTURE.ps1` n'a volontairement pas été ajouté à l'autostart Windows, car cette partie était optionnelle.

Sur le serveur cible, la recette finale doit donc confirmer visuellement : ouverture d'Edge de collecte, détection automatique de l'onglet, apparition des UpQuR/UpQuH dans Campagnes, fermeture/réouverture de l'onglet et respect d'un Stop manuel.
