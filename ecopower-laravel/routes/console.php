<?php

use Illuminate\Foundation\Inspiring;
use Illuminate\Support\Facades\Artisan;

Artisan::command('inspire', function () {
    $this->comment(Inspiring::quote());
})->purpose('Display an inspiring quote');

// Changer le mot de passe admin : php artisan ecopower:admin-password "NouveauMotDePasse" [email]
Artisan::command('ecopower:admin-password {password} {email=admin@ecopower.tn}', function (string $password, string $email) {
    $updated = \Illuminate\Support\Facades\DB::table('users')
        ->where('email', strtolower($email))
        ->update(['password' => password_hash($password, PASSWORD_BCRYPT, ['cost' => 10])]);
    $this->info($updated ? "Mot de passe mis à jour pour $email." : "Aucun compte $email.");
})->purpose('Changer le mot de passe administrateur');
