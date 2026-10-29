# EcoPower Tunisie — version Laravel

Même site que la version React + Express (dossier parent), avec le back réécrit en **Laravel 12** :

- **Front** : le même React 18 + Tailwind 3, dans `resources/js`, compilé par Vite via `laravel-vite-plugin`.
  La page `resources/views/app.blade.php` reprend l'ancien `index.html` (SEO, Pixel Facebook, polices).
- **API** : mêmes URL et mêmes réponses JSON que `server/index.js` (`routes/api.php`, `app/Http/Controllers/Api`).
  Auth admin par jeton JWT (compatible avec les jetons de l'ancien serveur si `JWT_SECRET` est le même),
  commandes sans compte avec paiement à la livraison, suivi, certificat, prospects B2B, statistiques,
  mêmes limites anti-abus (connexion, commandes, suivi).
- **Base** : la même base MySQL `ecopower_db`. La migration ne crée que les tables absentes et le seeder
  ne remplit que les tables vides (données reprises de `server/data/*.json`, copiées dans `database/data`).

## Lancer en local (Windows)

Prérequis : PHP 8.2+ (extensions pdo_mysql, mbstring, openssl), Composer, Node 18+, MySQL.

```bash
composer install
copy .env.example .env        # puis renseigner DB_* et JWT_SECRET
php artisan key:generate
php artisan migrate --seed
npm install
npm run build                 # ou "npm run dev" pour le rechargement à chaud
php artisan serve             # http://localhost:8000
```

En développement, lancer `npm run dev` et `php artisan serve` dans deux terminaux.

Admin : `/admin`, identifiants `ADMIN_EMAIL` / `ADMIN_PASSWORD` du `.env` (par défaut admin@ecopower.tn / admin123,
à changer avant la mise en ligne).

## Garder le front à jour

Le front a été copié depuis `../src`. Si le projet d'origine change (ex. traduction en darija),
lancer `powershell -File sync-front.ps1` puis `npm run build`.

## Hébergement sur un petit VPS (1 vCPU, 2 Go)

Pile conseillée : Ubuntu 24.04, nginx, PHP 8.3-FPM avec OPcache, MySQL 8 (ou MariaDB).
Les fichiers de configuration prêts à copier sont dans `deploy/` :

| Fichier | Rôle |
| --- | --- |
| `nginx-ecopower.conf` | sert `/build`, `/products`, `/logos` directement (cache long, gzip), le reste à PHP |
| `php-fpm-ecopower.conf` | 8 workers max, adapté à 2 Go |
| `opcache-ecopower.ini` | OPcache + JIT, sans vérification des fichiers (rapide) |
| `mysql-petit-vps.cnf` | MySQL limité à ~256 Mo de cache, fuseau +01:00 |
| `deploy.sh` | mise à jour : composer, build, migrations, caches |

Dans le `.env` de production : `APP_ENV=production`, `APP_DEBUG=false`, `APP_URL=https://eco-power.tn`,
un `JWT_SECRET` long et aléatoire, un vrai `ADMIN_PASSWORD`. Puis `php artisan optimize`.

Pourquoi c'est aussi rapide que l'ancienne version : nginx sert seul les fichiers statiques et le JS/CSS compilés
(c'était Express avant), la page HTML est une vue Blade mise en cache sans session ni cookie, et l'API fait les
mêmes requêtes SQL que l'ancien serveur.
