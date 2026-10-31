#!/usr/bin/env bash
# Fabrique le zip à extraire dans public_html sur cPanel (même contenu que
# ecopower-cpanel-public_html-2026-10-18-v3.zip) : site compilé + vendor/ sans
# dépendances de dev + images, sans .env (celui du serveur est conservé).
#
#   bash deploy/build-cpanel.sh                     -> ../ecopower-cpanel-public_html-AAAA-MM-JJ.zip
#   bash deploy/build-cpanel.sh mon-fichier.zip
#   BUILD_DIR=dossier bash deploy/build-cpanel.sh   -> garde aussi dossier/public_html
#
# Il faut : PHP 8.2+, Composer, Node 18+ / npm, zip.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:-$ROOT/../ecopower-cpanel-public_html-$(date +%F).zip}"
OUT="$(cd "$(dirname "$OUT")" && pwd)/$(basename "$OUT")"
BUILD_DIR="${BUILD_DIR:-$(mktemp -d)}"
SITE="$BUILD_DIR/public_html"

echo "==> Copie du projet dans $SITE"
rm -rf "$SITE"
mkdir -p "$SITE"
# Le dossier de travail tel quel (y compris les changements pas encore commités),
# sans ce qui est propre au PC ou regénéré plus bas.
tar -C "$ROOT" -c \
    --exclude=./node_modules --exclude=./vendor --exclude=./public/build \
    --exclude=./public/hot --exclude=./public/storage \
    --exclude=./.env --exclude=./.env.backup --exclude=./.env.production \
    --exclude=./.git --exclude=./.phpunit.result.cache --exclude=./.phpunit.cache \
    --exclude='./bootstrap/cache/*.php' --exclude='./storage/logs/*.log' \
    --exclude='./storage/framework/cache/data' --exclude='./storage/framework/views/*.php' \
    --exclude='./storage/framework/migrated-*' \
    . | tar -C "$SITE" -x

echo "==> Front React (npm ci + vite build)"
(cd "$SITE" && npm ci --no-audit --no-fund && npm run build)
rm -rf "$SITE/node_modules"

echo "==> Dépendances PHP sans dev (composer install --no-dev)"
(cd "$SITE" && composer install --no-dev --optimize-autoloader --no-interaction --no-progress --prefer-dist)
# Si Composer a dû cloner des paquets depuis git, retirer leurs .git (inutiles et très lourds)
find "$SITE/vendor" -name .git -type d -prune -exec rm -rf {} +

for f in public/build/manifest.json vendor/autoload.php .htaccess public/index.php; do
    [ -e "$SITE/$f" ] || { echo "ERREUR : $f manquant" >&2; exit 1; }
done

echo "==> Zip"
rm -f "$OUT"
(cd "$BUILD_DIR" && zip -qr -X "$OUT" public_html)
echo "OK : $OUT ($(du -h "$OUT" | cut -f1))"
