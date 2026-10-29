<?php

return [
    // Même secret que l'ancien serveur Express : les sessions admin restent valides.
    'jwt_secret' => env('JWT_SECRET', 'ecopower_secret_jwt_key_2026_tunisie'),
    'jwt_ttl' => 7 * 24 * 3600,

    'admin_email' => env('ADMIN_EMAIL', 'admin@ecopower.tn'),
    'admin_password' => env('ADMIN_PASSWORD', 'admin123'),

    'free_delivery_from' => 120,
    'delivery_fee' => 8.0,
];
