-- EcoPower : mise à jour du 13/10/2026 pour une base DÉJÀ en ligne (importée avant cette date).
-- Ajoute le Pack de Base, le Pack Total et l'option « retrait au local » sur les commandes.
-- phpMyAdmin > ta base > Importer ce fichier, UNE seule fois.
-- (Avec le Terminal cPanel, « php artisan migrate --force » fait la même chose.)

SET NAMES utf8mb4;

ALTER TABLE `orders`
  ADD COLUMN `delivery_method` varchar(20) NOT NULL DEFAULT 'delivery' AFTER `delivery_fee`,
  ADD COLUMN `discount` decimal(10,2) NOT NULL DEFAULT 0.00 AFTER `delivery_method`;

INSERT IGNORE INTO `products` VALUES ('pack-base','Pack de Base','الباك الأساسي','packs',39.90,NULL,5.0,0,'3 ans','5 L/min','/products/pack_appartement_5l.webp','L\'essentiel pour commencer à économiser : 1 hydro-économe 5L/min pour la cuisine et 1 régulateur de douche, avec le sac débit-mètre offert. -10% et sans frais de livraison en retrait au local.','[\"1x Hydro-économe 5L\\/min pour robinet de cuisine\",\"1x Régulateur douche 5L\\/min\",\"1x Sac Débit-mètre offert\",\"Retrait au local : -10% et sans frais de livraison\",\"Garantie 3 ans\"]',100,1,'2026-10-13 18:43:28','2026-10-13 18:43:28');
INSERT IGNORE INTO `products` VALUES ('pack-totale','Pack Total','الباك الكامل','packs',79.10,NULL,5.0,0,'3 ans (Eco-Sac à vie)','5 L/min','/products/pack_maison_5l.webp','Toute la maison équipée : cuisine, lavabo de salle de bain, douche et toilettes, plus l\'Eco-Sac WC et le sac débit-mètre offert. -10% et sans frais de livraison en retrait au local.','[\"1x Hydro-économe 5L\\/min pour robinet de cuisine\",\"1x Hydro-économe 5L\\/min pour lavabo de salle de bain\",\"1x Régulateur douche 5L\\/min\",\"1x Régulateur toilette 5L\\/min\",\"1x Eco-Sac WC (garanti à vie)\",\"1x Sac Débit-mètre offert\",\"Retrait au local : -10% et sans frais de livraison\"]',100,1,'2026-10-13 18:43:28','2026-10-13 18:43:28');
