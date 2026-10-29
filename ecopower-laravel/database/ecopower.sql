/*M!999999\- enable the sandbox mode */ 

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;
DROP TABLE IF EXISTS `leads`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `leads` (
  `id` varchar(100) NOT NULL,
  `date` datetime NOT NULL DEFAULT current_timestamp(),
  `company` varchar(255) NOT NULL,
  `contact_person` varchar(150) NOT NULL,
  `role` varchar(100) DEFAULT NULL,
  `phone` varchar(50) NOT NULL,
  `email` varchar(191) DEFAULT NULL,
  `type` varchar(50) DEFAULT 'entreprise',
  `rooms_count` int(11) DEFAULT 0,
  `current_water_bill_monthly` varchar(100) DEFAULT NULL,
  `interest` varchar(255) DEFAULT NULL,
  `status` varchar(50) DEFAULT 'new',
  `notes` text DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

LOCK TABLES `leads` WRITE;
/*!40000 ALTER TABLE `leads` DISABLE KEYS */;
INSERT INTO `leads` VALUES
('LEAD-201','2026-10-01 12:20:00','Hôtel Thalassa Sousse Resort & Aquapark','M. Khaled Mahjoub','Directeur Technique','+216 73 241 500','technique@thalassa-sousse.com','hotel',280,'18 500 DT','Audit complet et équipement chambres + spa','in_progress','Rendez-vous téléphonique fixé pour devis sur site.','2026-10-01 12:20:00'),
('LEAD-202','2026-10-02 16:10:00','Clinique Hannibal International','Dr. Walid Ghorbel','Directeur d\'Exploitation','+216 71 889 000','w.ghorbel@clinique-hannibal.com','clinique',95,'9 200 DT','Mousseurs Delrin aux normes sanitaires médicales ISO','new','Demande reçue via le formulaire pro.','2026-10-02 16:10:00'),
('LEAD-203','2026-10-02 21:51:45','Hotel Palmier Sousse','Montassir Trabelsi','Directeur Technique','73456789','direction@hotelpalmier.tn','hotel',120,'3500','Diagnostic et audit gratuit','new','Urgence reduction factures ete','2026-10-02 21:51:45');
/*!40000 ALTER TABLE `leads` ENABLE KEYS */;
UNLOCK TABLES;
DROP TABLE IF EXISTS `order_items`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `order_items` (
  `id` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `order_id` varchar(100) NOT NULL,
  `product_id` varchar(100) NOT NULL,
  `name` varchar(255) NOT NULL,
  `price` decimal(10,2) NOT NULL,
  `quantity` int(11) NOT NULL DEFAULT 1,
  `serials` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL CHECK (json_valid(`serials`)),
  PRIMARY KEY (`id`),
  KEY `idx_order_id` (`order_id`),
  CONSTRAINT `fk_order` FOREIGN KEY (`order_id`) REFERENCES `orders` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=10 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

LOCK TABLES `order_items` WRITE;
/*!40000 ALTER TABLE `order_items` DISABLE KEYS */;
INSERT INTO `order_items` VALUES
(1,'ECO-1006','pack-appartement-4l','Pack Appartement 4 Litres',66.00,1,'[\"SN-PACK-2026-5314\"]'),
(2,'ECO-1006','ecosac-wc-3l','Eco-Sac WC 3 Litres Imputrescible',22.90,2,'[\"SN-ECOS-2026-2451\",\"SN-ECOS-2026-1863\"]'),
(3,'ECO-1005','ecosac-wc-3l','Eco-Sac WC 3 Litres Imputrescible',22.90,2,'[\"SN-ECOS-2026-2518\",\"SN-ECOS-2026-9342\"]'),
(4,'ECO-1001','pack-appartement-4l','Pack Appartement 4 Litres',66.00,1,'[\"SN-PA4-2026-0041\"]'),
(5,'ECO-1002','pack-maison-4l','Pack Maison / Villa 4 Litres',109.00,1,'[\"SN-PM4-2026-0082\"]'),
(6,'ECO-1002','pomme-douche-chromee','Pomme de Douche Chromée Jets Massants 6L/min',29.75,1,'[\"SN-PDC-2026-0112\"]'),
(7,'ECO-1003','ecosac-wc-3l','Eco-Sac WC 3 Litres Imputrescible',22.90,2,'[\"SN-EWC-2026-0301\",\"SN-EWC-2026-0302\"]'),
(8,'ECO-1003','hydro-econome-4l','Hydro-Économe 4L/min',17.50,2,'[\"SN-HE4-2026-0410\",\"SN-HE4-2026-0411\"]'),
(9,'ECO-1004','pack-appartement-5l','Pack Appartement 5 Litres',66.00,1,'[\"SN-PA5-2026-0095\"]');
/*!40000 ALTER TABLE `order_items` ENABLE KEYS */;
UNLOCK TABLES;
DROP TABLE IF EXISTS `orders`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `orders` (
  `id` varchar(100) NOT NULL,
  `user_id` int(11) DEFAULT NULL,
  `customer_name` varchar(150) NOT NULL,
  `customer_phone` varchar(50) NOT NULL,
  `customer_email` varchar(191) DEFAULT NULL,
  `customer_address` text DEFAULT NULL,
  `customer_city` varchar(100) DEFAULT NULL,
  `customer_governorate` varchar(100) DEFAULT NULL,
  `subtotal` decimal(10,2) NOT NULL,
  `delivery_fee` decimal(10,2) NOT NULL DEFAULT 8.00,
  `total` decimal(10,2) NOT NULL,
  `payment_method` varchar(50) DEFAULT 'cod',
  `status` varchar(50) DEFAULT 'pending',
  `certificate_serial` varchar(100) DEFAULT NULL,
  `notes` text DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  KEY `idx_customer_phone` (`customer_phone`),
  KEY `idx_customer_email` (`customer_email`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

LOCK TABLES `orders` WRITE;
/*!40000 ALTER TABLE `orders` DISABLE KEYS */;
INSERT INTO `orders` VALUES
('ECO-1001',NULL,'Mohamed Ben Ali','+216 98 123 456','m.benali@gmail.com','Résidence Les Jardins, Apt B12, Ennasr 2','Ariana','Ariana',66.00,8.00,74.00,'cod','delivered','CERT-2026-ECO-1001','Livré avec succès à Ennasr 2.','2026-10-01 15:32:00'),
('ECO-1002',NULL,'Sarra Trabelsi','+216 55 889 900','sarra.trabelsi@yahoo.fr','14 Rue Habib Bourguiba, Sahloul','Sousse','Sousse',138.75,0.00,138.75,'cod','shipped','CERT-2026-ECO-1002','Colis confié au transporteur express ce matin.','2026-10-02 10:15:00'),
('ECO-1003',NULL,'Hatem Dridi','+216 22 445 566','hatem.dridi@topnet.tn','Avenue Habib Thameur, Nabeul','Nabeul','Nabeul',80.80,8.00,88.80,'cod','confirmed','CERT-2026-ECO-1003','Client contacté par téléphone pour confirmation.','2026-10-02 17:45:00'),
('ECO-1004',NULL,'Ines Mansour','+216 99 778 811','ines.mansour@gnet.tn','Route de Téniour Km 2, Sfax','Sfax','Sfax',66.00,8.00,74.00,'cod','confirmed','CERT-2026-ECO-1004','Nouvelle commande en attente de vérification.','2026-10-02 20:20:00'),
('ECO-1005',NULL,'Test Client','55123456','test@test.tn','12 Rue Test','Tunis','Tunis',45.80,8.00,53.80,'cod','pending','CERT-2026-ECO-1005','Test commande','2026-10-02 21:45:52'),
('ECO-1006',NULL,'Ahmed Ben Salah','22334455','ahmed@test.tn','45 Rue de la Paix','Sousse','Sousse',111.80,8.00,119.80,'cod','pending','CERT-2026-ECO-1006','Test commande complete','2026-10-02 21:51:33');
/*!40000 ALTER TABLE `orders` ENABLE KEYS */;
UNLOCK TABLES;
DROP TABLE IF EXISTS `products`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `products` (
  `id` varchar(100) NOT NULL,
  `name` varchar(255) NOT NULL,
  `name_ar` varchar(255) DEFAULT NULL,
  `category` varchar(100) DEFAULT 'packs',
  `price` decimal(10,2) NOT NULL,
  `old_price` decimal(10,2) DEFAULT NULL,
  `rating` decimal(3,1) DEFAULT 5.0,
  `reviews_count` int(11) DEFAULT 0,
  `warranty` varchar(100) DEFAULT '3 ans',
  `debit` varchar(50) DEFAULT NULL,
  `image` varchar(255) DEFAULT NULL,
  `description` text DEFAULT NULL,
  `features` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL CHECK (json_valid(`features`)),
  `stock` int(11) DEFAULT 100,
  `is_featured` tinyint(1) DEFAULT 0,
  `created_at` datetime NOT NULL DEFAULT current_timestamp(),
  `updated_at` datetime NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

LOCK TABLES `products` WRITE;
/*!40000 ALTER TABLE `products` DISABLE KEYS */;
INSERT INTO `products` VALUES
('ampoule-led-detecteur','Ampoule LED Détecteur de Mouvement IP20 2.5W','لمبة ليد بمستشعر حركة 2.5 واط','energie',26.20,34.00,5.0,58,'2 ans','2.5W (Équiv. 30W)','/products/ampoule_led_detecteur.jpg','Ampoule LED intelligente avec capteur de mouvement infrarouge intégré. S\'allume automatiquement dès qu\'une personne entre et s\'éteint après départ. Idéal pour couloirs, entrées, escaliers et WC.','[\"Consommation ultra-basse : seulement 2.5W\",\"Détecteur de présence PIR intégré\",\"Durée de vie supérieure à 25 000 heures\",\"Culot à vis standard E27\"]',90,0,'2026-10-12 14:20:15','2026-10-12 14:20:15'),
('bague-inox-femelle','Bague Inox Femelle + Joint','حلقة إينوكس أنثى مع جوان','accessoires',5.90,8.00,5.0,31,'3 ans','Standard F22','/products/bague_inox_femelle.jpg','Bague filetée en Inox pour robinets à filetage extérieur (femelle F22). Livrée avec joint d\'étanchéité.','[\"Acier Inoxydable chromé\",\"Filetage F22 standard\",\"Joint d\'étanchéité haute résistance\"]',150,0,'2026-10-12 14:20:15','2026-10-12 14:20:15'),
('bague-inox-male','Bague Inox Mâle + Joint','حلقة إينوكس ذكر مع جوان','accessoires',5.90,8.00,5.0,39,'3 ans','Standard M24','/products/bague_inox_male.jpg','Bague filetée en Inox pour robinets à filetage intérieur (mâle M24). Livrée avec joint d\'étanchéité.','[\"Acier Inoxydable de qualité marine\",\"Filetage M24 standard\",\"Joint en caoutchouc résistant aux températures élevées\"]',150,0,'2026-10-12 14:20:15','2026-10-12 14:20:15'),
('ecosac-wc-3l','Eco-Sac WC 3 Litres Imputrescible','كيس توفير ماء للمرحاض 3 لتر','wc',22.90,29.00,5.0,184,'À vie','3 L économisés / chasse','/products/ecosac_wc_3l.jpg','Se remplit d\'eau et s\'accroche dans le réservoir des toilettes. Économise 3 litres à chaque chasse d\'eau sans gêner le mécanisme. Plus de 30 000 litres économisés par an pour une famille.','[\"Économise 30% d\'eau à chaque chasse\",\"Plastique haute résistance imputrescible à vie\",\"Attache rapide sur la paroi interne du réservoir\",\"Garantie à vie\"]',136,1,'2026-10-12 14:20:15','2026-10-12 14:20:15'),
('hydro-econome-2l','Hydro-Économe 2L/min Jets Aiguilles','موفر ماء 2 لتر/دقيقة نفث إبري','robinets',18.20,22.00,5.0,42,'3 ans','2 L/min','/products/cartouche_hydro_rose_verte.jpg','Technologie jets aiguilles haute précision. Économise jusqu\'à 80% d\'eau sur les lave-mains et sanitaires publics ou résidentiels.','[\"Débit ultra-économique 2 Litres \\/ minute\",\"Matériau Delrin \\/ Hostaform anticalcaire\",\"Résiste jusqu\'à 25 bars de pression\",\"Garantie 3 ans\"]',80,0,'2026-10-12 14:20:15','2026-10-12 14:20:15'),
('hydro-econome-3l','Hydro-Économe 3L/min','موفر ماء 3 لتر/دقيقة','robinets',17.90,21.00,5.0,35,'3 ans','3 L/min','/products/cartouche_hydro_verte.jpg','Régulateur haut rendement pour lavabos salle de bain et sanitaires.','[\"Débit calibré à 3 L\\/min\",\"Système anti-tartre automatique\",\"Certifié normes sanitaires internationales\",\"Garantie 3 ans\"]',90,0,'2026-10-12 14:20:15','2026-10-12 14:20:15'),
('hydro-econome-4l','Hydro-Économe 4L/min','موفر ماء 4 لتر/دقيقة','robinets',17.50,21.00,5.0,110,'3 ans','4 L/min','/products/cartouche_hydro_verte_paire.jpg','Le classique le plus recommandé pour cuisine et salle de bain. Économie de 60% sans baisse de confort.','[\"Débit 4 Litres \\/ minute\",\"Aération du jet brevetée\",\"Nettoyage aisé et résistance au chlore\",\"Garantie 3 ans\"]',120,0,'2026-10-12 14:20:15','2026-10-12 14:20:15'),
('hydro-econome-5l','Hydro-Économe 5L/min','موفر ماء 5 لتر/دقيقة','robinets',16.90,20.00,5.0,95,'3 ans','5 L/min','/products/bague_mousseur_complet.jpg','Confort maximal pour évier de cuisine avec rinçage rapide et économie de 55%.','[\"Débit 5 L\\/min puissant\",\"Insensible aux coups de bélier et pressions SONEDE\",\"Matériau breveté Hostafom\",\"Garantie 3 ans\"]',200,0,'2026-10-12 14:20:15','2026-10-12 14:20:15'),
('pack-appartement-4l','Pack Appartement 4 Litres','باك الشقة 4 لتر','packs',78.00,99.00,5.0,142,'3 ans (Eco-Sac à vie)','4 L/min','/products/pack_appartement_4l.webp','Solution complète pour appartement (F2-F3). Réduit immédiatement votre facture SONEDE de 50% et STEG de 25%. Comprend 2 mousseurs 4L/min, 1 régulateur douche, 1 Eco-Sac WC 3L et 1 Sac Débit-mètre offert.','[\"2x Hydro-économes 4L\\/min pour robinets\",\"1x Régulateur douche 5L\\/min en Delrin\",\"1x Eco-Sac WC 3L garanti à vie\",\"1x Sac Débit-mètre de mesure offert\",\"Installation sans outils en 2 minutes\",\"Garantie 3 ans & Satisfait ou Remboursé 14 jours\"]',49,1,'2026-10-12 14:20:15','2026-10-12 14:20:15'),
('pack-appartement-5l','Pack Appartement 5 Litres','باك الشقة 5 لتر','packs',78.00,99.00,5.0,98,'3 ans (Eco-Sac à vie)','5 L/min','/products/pack_appartement_5l.webp','Idéal pour un confort de débit standard avec 50% d\'économie. Comprend 2 mousseurs 5L/min, 1 régulateur douche 7L/min, 1 Eco-Sac WC et 1 Débit-mètre offert.','[\"2x Hydro-économes 5L\\/min pour robinets\",\"1x Régulateur douche 7L\\/min\",\"1x Eco-Sac WC 3L garanti à vie\",\"1x Sac Débit-mètre offert\",\"Confort de jet mousseux aéré\",\"Garantie 3 ans\"]',45,1,'2026-10-12 14:20:15','2026-10-12 14:20:15'),
('pack-maison-4l','Pack Maison / Villa 4 Litres','باك الفيلا و الدار 4 لتر','packs',129.00,159.00,5.0,87,'3 ans (Eco-Sacs à vie)','4 L/min','/products/pack_maison_4l.webp','Équipement complet pour grande maison ou villa avec 2 salles de bain. Économies maximales jusqu\'à 60% d\'eau.','[\"4x Hydro-économes 4L\\/min pour robinets cuisine & SDB\",\"2x Régulateurs Inox pour douches et flexibles\",\"2x Eco-Sacs WC 3L imputrescibles\",\"1x Sac Débit-mètre gradué gratuit\",\"Notice d\'installation rapide\",\"Garantie 3 ans\"]',35,1,'2026-10-12 14:20:15','2026-10-12 14:20:15'),
('pack-maison-5l','Pack Maison / Villa 5 Litres','باك الفيلا و الدار 5 لتر','packs',129.00,159.00,5.0,64,'3 ans (Eco-Sacs à vie)','5 L/min','/products/pack_maison_5l.webp','Pour maison individuelle recherchant un équilibre parfait entre confort et économie d\'énergie.','[\"4x Hydro-économes 5L\\/min pour robinets\",\"2x Régulateurs Inox douches 7L\\/min\",\"2x Eco-Sacs WC 3L imputrescibles\",\"1x Sac Débit-mètre gradué gratuit\",\"Garantie 3 ans\"]',40,1,'2026-10-12 14:20:15','2026-10-12 14:20:15'),
('pomme-douche-blanche','Pomme de Douche Blanche Anticalcaire 6.3L/min','مرش دوش أبيض مضاد للكلس 6.3 لتر/دقيقة','douches',24.90,32.00,5.0,51,'3 ans','6.3 L/min','/products/pomme_douche_blanche.jpg','Douchette ergonomique blanche avec picots autonettoyants en silicone. Résiste aux eaux calcaires de toutes les régions tunisiennes.','[\"Débit maîtrisé 6.3 L\\/min\",\"Picots élastomères anticalcaire faciles à détartrer d\'un coup de doigt\",\"Excellente prise en main ergonomique\",\"Garantie 3 ans\"]',75,0,'2026-10-12 14:20:15','2026-10-12 14:20:15'),
('pomme-douche-chromee','Pomme de Douche Chromée Jets Massants 6L/min','مرش دوش كروم نفث مساج 6 لتر/دقيقة','douches',29.75,38.00,5.0,78,'3 ans','6 L/min','/products/pomme_douche_chromee.jpg','Pommeau de douche haut de gamme au design chromé luxueux. Combine hydro-économie et confort de jets massants toniques.','[\"Débit régulé à 6 Litres \\/ minute (au lieu de 20L habituels)\",\"Finitions chromées miroir résistantes à l\'oxydation\",\"Buses massantes anticalcaire\",\"Se visse sur tout flexible standard 15\\/21\",\"Garantie 3 ans\"]',65,1,'2026-10-12 14:20:15','2026-10-12 14:20:15'),
('regulateur-douche-5l','Régulateur Inox Douche / Flexible 5L/min','معدل تدفق إينوكس للدوش 5 لتر/دقيقة','douches',19.90,25.00,5.0,63,'3 ans','5 L/min','/products/bague_mousseur_grille_bleue.jpg','Se place directement entre le robinet mélangeur et le flexible de douche ou flexible toilette. Réduit la consommation de 60%.','[\"Corps en Inox massif inoxydable\",\"Cartouche interne Hostaform\",\"Compatible douchette et douchette hygiénique WC\",\"Garantie 3 ans\"]',100,0,'2026-10-12 14:20:15','2026-10-12 14:20:15'),
('regulateur-douche-7l','Régulateur Inox Douche / Flexible 7L/min','معدل تدفق إينوكس للدوش 7 لتر/دقيقة','douches',19.90,25.00,5.0,44,'3 ans','7 L/min','/products/bague_mousseur_complet.jpg','Régulateur de débit inox assurant un jet tonique et généreux tout en réduisant de moitié le débit d\'eau chaude.','[\"Débit stable 7 L\\/min sous toutes pressions\",\"Économie directe sur le gaz chauffe-eau STEG\",\"Garantie 3 ans\"]',110,0,'2026-10-12 14:20:15','2026-10-12 14:20:15');
/*!40000 ALTER TABLE `products` ENABLE KEYS */;
UNLOCK TABLES;
DROP TABLE IF EXISTS `users`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8mb4 */;
CREATE TABLE `users` (
  `id` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `name` varchar(150) NOT NULL,
  `email` varchar(191) NOT NULL,
  `password` varchar(255) NOT NULL,
  `role` enum('admin','client') NOT NULL DEFAULT 'client',
  `phone` varchar(50) DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  UNIQUE KEY `users_email_unique` (`email`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

LOCK TABLES `users` WRITE;
/*!40000 ALTER TABLE `users` DISABLE KEYS */;
INSERT INTO `users` VALUES
(1,'Direction EcoPower','admin@ecopower.tn','$2y$10$PPFzQ6v4Ao7/qH93Rb2maevvM.AldnFgJINg.knusDPGnw3a.JrMu','admin','+216 98 000 000','2026-10-12 14:20:15');
/*!40000 ALTER TABLE `users` ENABLE KEYS */;
UNLOCK TABLES;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

