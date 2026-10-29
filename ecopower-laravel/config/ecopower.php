<?php

return [
    // Même secret que l'ancien serveur Express : les sessions admin restent valides.
    'jwt_secret' => env('JWT_SECRET', 'ecopower_secret_jwt_key_2026_tunisie'),
    'jwt_ttl' => 7 * 24 * 3600,

    'admin_email' => env('ADMIN_EMAIL', 'admin@ecopower.tn'),
    'admin_password' => env('ADMIN_PASSWORD', 'admin123'),

    'free_delivery_from' => 120,
    'delivery_fee' => 8.0,

    // Retrait au local : pas de frais de livraison et remise sur les produits cochés
    // « Remise retrait au local » dans l'admin (colonne products.pickup_discount).
    // Garder le même taux dans resources/js/lib/pickup.js.
    'pickup_discount_rate' => 0.10,
    'pickup_address' => 'Local EcoPower, rue Ibn Zohr, Tunis',
    'pickup_hours' => 'du lundi au samedi, de 7h à 12h',
    'pickup_map_url' => 'https://www.google.com/maps?q=36.822639,10.183694',

    // Paiement par carte bancaire via Konnect (konnect.network).
    // Le paiement par carte n'apparaît sur le site que si la clé API et le wallet sont renseignés.
    'konnect' => [
        'api_key' => env('KONNECT_API_KEY'),
        'wallet_id' => env('KONNECT_WALLET_ID'),
        // true = environnement de test Konnect (aucun vrai débit)
        'sandbox' => (bool) env('KONNECT_SANDBOX', true),
        'base_url' => env('KONNECT_BASE_URL'),
    ],
];
