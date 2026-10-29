-- EcoPower : mise à jour du 18/10/2026 (choix des produits de la page d'accueil
-- et des produits remisés au retrait, depuis l'admin), pour une base DÉJÀ en ligne.
-- À importer UNE seule fois dans phpMyAdmin (onglet Importer ou SQL).
-- (Avec le Terminal cPanel, « php artisan migrate --force » fait la même chose.)
SET NAMES utf8mb4;

ALTER TABLE `products`
  ADD COLUMN `show_on_home` tinyint(1) NOT NULL DEFAULT 0 AFTER `is_featured`,
  ADD COLUMN `pickup_discount` tinyint(1) NOT NULL DEFAULT 0 AFTER `show_on_home`;

UPDATE `products` SET `show_on_home` = 1 WHERE `id` IN ('pack-appartement-4l', 'pack-maison-4l');
UPDATE `products` SET `pickup_discount` = 1 WHERE `id` IN ('pack-base', 'pack-totale');
