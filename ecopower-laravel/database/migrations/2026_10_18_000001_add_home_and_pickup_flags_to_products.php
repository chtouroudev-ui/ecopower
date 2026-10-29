<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;

/**
 * Choix depuis l'admin : produits affichés sur la page d'accueil
 * et produits remisés en cas de retrait au local.
 */
return new class extends Migration
{
    public function up(): void
    {
        $addHome = ! Schema::hasColumn('products', 'show_on_home');
        $addPickup = ! Schema::hasColumn('products', 'pickup_discount');

        Schema::table('products', function (Blueprint $table) use ($addHome, $addPickup) {
            if ($addHome) {
                $table->boolean('show_on_home')->default(false)->after('is_featured');
            }
            if ($addPickup) {
                $table->boolean('pickup_discount')->default(false)->after('show_on_home');
            }
        });

        // Reprend ce qui était codé en dur jusqu'ici.
        if ($addHome) {
            DB::table('products')->whereIn('id', ['pack-appartement-4l', 'pack-maison-4l'])->update(['show_on_home' => true]);
        }
        if ($addPickup) {
            DB::table('products')->whereIn('id', ['pack-base', 'pack-totale'])->update(['pickup_discount' => true]);
        }
    }

    public function down(): void
    {
        Schema::table('products', function (Blueprint $table) {
            $table->dropColumn(['show_on_home', 'pickup_discount']);
        });
    }
};
