<?php

namespace App\Support;

use Illuminate\Support\Facades\Artisan;
use Throwable;

/**
 * Sur cPanel sans Terminal : applique les migrations en attente au premier appel
 * après une mise à jour, au lieu d'importer un fichier SQL à la main.
 * Un fichier témoin par version évite de relancer la vérification à chaque requête.
 */
class AutoMigrate
{
    public static function run(): void
    {
        $files = glob(database_path('migrations/*.php')) ?: [];
        $marker = storage_path('framework/migrated-'.md5(implode('|', array_map('basename', $files))));
        if (is_file($marker)) {
            return;
        }

        try {
            Artisan::call('migrate', ['--force' => true]);
            @file_put_contents($marker, date('c'));
        } catch (Throwable $e) {
            report($e);
        }
    }
}
