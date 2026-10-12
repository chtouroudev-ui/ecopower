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
