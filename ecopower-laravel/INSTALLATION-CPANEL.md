# Mettre EcoPower en ligne sur cPanel

Aucun Node ni build sur le serveur : le zip contient déjà les dépendances PHP (`vendor/`) et le site compilé (`public/build/`).
Il faut seulement PHP 8.2 ou plus et une base MySQL.

## 1. PHP
cPanel > **Sélectionner une version PHP** (ou MultiPHP Manager) : choisir **PHP 8.2 ou 8.3**,
avec les extensions `pdo_mysql`, `mbstring`, `openssl`, `fileinfo` cochées.

## 2. Base de données
1. cPanel > **Bases de données MySQL** : créer une base (ex. `cpaneluser_ecopower`) et un utilisateur, puis donner **tous les privilèges** à cet utilisateur sur la base.
2. cPanel > **phpMyAdmin** : ouvrir la base, onglet **Importer**, choisir `database/ecopower.sql` (tables + produits + commandes de démonstration + compte admin).

## 3. Fichiers
1. cPanel > **Gestionnaire de fichiers** > `public_html` : téléverser le zip et faire **Extraire**.
   Le contenu doit être directement dans `public_html` (on doit voir `public_html/app`, `public_html/public`, `public_html/.htaccess`...).
2. Copier les dossiers d'images `products` et `logos` (dans `public/` du projet sur ton PC) vers `public_html/public/`.
3. Afficher les fichiers cachés (Paramètres > « Afficher les fichiers cachés »), éditer `public_html/.env` et remplir
   `DB_DATABASE`, `DB_USERNAME`, `DB_PASSWORD` avec ceux de l'étape 2, et `APP_URL` avec ton domaine.
4. Vérifier que les dossiers `storage` et `bootstrap/cache` sont en permissions **755** (ou 775).

Le `.htaccess` à la racine envoie les visiteurs vers `public/` et bloque l'accès à `.env`, `vendor`, `storage`, etc.

## 4. Sécurité (important)
Le compte admin importé est `admin@ecopower.tn` / `admin123`. Change-le tout de suite :
- avec le **Terminal** de cPanel : `cd public_html && php artisan ecopower:admin-password "TonNouveauMotDePasse"`
- sans Terminal : dans phpMyAdmin, table `users`, remplacer `password` par un hash bcrypt généré sur un site de confiance.

`APP_KEY` et `JWT_SECRET` sont déjà générés dans le `.env` ; ne les partage pas.

## 5. Accélérer (optionnel, avec le Terminal)
```bash
cd public_html
php artisan config:cache
php artisan route:cache
php artisan view:cache
```
À relancer après chaque modification du `.env` (ou `php artisan optimize:clear` pour annuler).

## Option : domaine pointé sur `public/`
Si ton cPanel permet de choisir la racine du domaine (Domaines > Gérer), mets le projet dans `/home/USER/ecopower`
et pointe le domaine vers `/home/USER/ecopower/public`. Le `.htaccess` racine devient alors inutile.

## Mise à jour du 13/10/2026 : Pack de Base, Pack Total et retrait au local
Si le site est **déjà en ligne** avec une base importée avant cette date :
1. Téléverser le nouveau zip dans `public_html` et l'extraire en remplaçant les fichiers (garder ton `.env` actuel : ne pas écraser celui du serveur, ou recopier tes valeurs `DB_*`, `APP_KEY`, `JWT_SECRET` dedans).
2. phpMyAdmin > ta base > **Importer** `database/mise-a-jour-2026-10-13-packs-retrait.sql`, **une seule fois**
   (ou, avec le Terminal : `php artisan migrate --force`).
3. Si tu as lancé `php artisan config:cache`, le relancer.

Nouvelle installation : importer simplement `database/ecopower.sql`, il contient déjà tout.

Réglages (dans `config/ecopower.php`) : `pickup_packs` (packs éligibles au retrait) et `pickup_discount_rate` (0.10 = -10 %).
Si tu changes la liste, changer aussi `resources/js/lib/pickup.js` puis refaire `npm run build`.

## Mise à jour du 15/10/2026 : paiement par carte (Konnect) et adresse du local
1. Extraire le nouveau zip comme ci-dessus (en gardant ton `.env`).
2. phpMyAdmin > **Importer** `database/mise-a-jour-2026-10-15-paiement-carte.sql`, **une seule fois**
   (après celui du 13/10 si tu ne l'avais pas encore importé). Avec le Terminal : `php artisan migrate --force`.
3. Créer un compte marchand sur https://konnect.network, puis dans ton `.env` ajouter :
   ```
   KONNECT_API_KEY=ta_cle_api
   KONNECT_WALLET_ID=ton_wallet_id
   KONNECT_SANDBOX=true      # mettre false une fois les tests faits, pour encaisser pour de vrai
   ```
   `APP_URL` doit être l'adresse exacte du site (https://...) : Konnect y renvoie le client et y confirme les paiements.
   Tant que la clé et le wallet sont vides, le site ne propose que le paiement en espèces.
4. Si tu as lancé `php artisan config:cache`, le relancer.

Adresse et horaires du retrait au local : `pickup_address`, `pickup_hours`, `pickup_map_url` dans `config/ecopower.php`.

### Sécurité de la connexion admin
Après 5 mots de passe faux depuis la même adresse IP, la connexion admin est bloquée 24 h pour cette adresse.
Si tu te bloques toi-même : Terminal `php artisan cache:clear`, ou supprimer le contenu de `storage/framework/cache/data` dans le Gestionnaire de fichiers.

## Mise à jour du 18/10/2026 : page d'accueil et remise retrait choisies dans l'admin

1. Extraire le zip dans le Gestionnaire de fichiers, à côté de `public_html`, puis remplacer les fichiers de `public_html` (le zip ne contient **pas** de `.env` : celui du serveur est conservé).
2. Rien à importer : au premier chargement du site, les nouvelles colonnes de la base sont ajoutées automatiquement (app/Support/AutoMigrate.php). Le fichier `database/mise-a-jour-2026-10-18-accueil-retrait.sql` reste disponible si besoin.
3. Admin → **Produits & stock** : colonnes « Page d'accueil » et « -10% retrait » (clic sur Oui/Non). Au départ : Pack Appartement 4L et Pack Maison 4L sur l'accueil, Pack de Base et Pack Total remisés au retrait.

Corrigé aussi : le menu de l'admin reste en place au défilement, la fenêtre de commande se ferme en cliquant à côté (ou Échap) et n'est plus coupée en haut.

Ajouté ensuite le même jour :
- **Produit vedette** : colonne « Vedette » (un seul produit) = la grande carte en haut à droite de l'accueil, avec son nom, sa description, sa photo et son prix.
- **Photos** : dans la fiche produit (clic sur le produit ou le crayon), bouton « Changer la photo » (JPG, PNG, WEBP, 5 Mo max), enregistrée dans `public/products/uploads`.
