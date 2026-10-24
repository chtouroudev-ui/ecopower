#!/usr/bin/env bash
# Mise à jour du site sur le VPS : bash deploy/deploy.sh
set -e
cd "$(dirname "$0")/.."
php artisan down || true
composer install --no-dev --optimize-autoloader --no-interaction
npm ci && npm run build
php artisan migrate --force
php artisan db:seed --force          # ne remplit que les tables vides
php artisan optimize                 # cache config + routes + vues
sudo systemctl reload php8.3-fpm     # vide l'OPcache (validate_timestamps=0)
php artisan up
