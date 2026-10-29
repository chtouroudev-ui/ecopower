-- EcoPower : mise à jour du 15/10/2026 (paiement par carte Konnect), pour une base DÉJÀ en ligne.
-- À importer APRÈS mise-a-jour-2026-10-13-packs-retrait.sql, UNE seule fois.
-- (Avec le Terminal cPanel, « php artisan migrate --force » fait la même chose.)
SET NAMES utf8mb4;

ALTER TABLE `orders`
  ADD COLUMN `payment_status` varchar(20) NOT NULL DEFAULT 'unpaid' AFTER `payment_method`,
  ADD COLUMN `payment_ref` varchar(100) DEFAULT NULL AFTER `payment_status`,
  ADD INDEX `idx_payment_ref` (`payment_ref`);
