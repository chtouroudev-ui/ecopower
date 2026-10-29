<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;

/** Produit vedette : la grande carte en haut à droite de la page d'accueil (un seul produit). */
return new class extends Migration
{
    public function up(): void
    {
        if (Schema::hasColumn('products', 'is_hero')) {
            return;
        }

        Schema::table('products', function (Blueprint $table) {
            $table->boolean('is_hero')->default(false)->after('pickup_discount');
        });
        DB::table('products')->where('id', 'pack-appartement-4l')->update(['is_hero' => true]);
    }

    public function down(): void
    {
        Schema::table('products', function (Blueprint $table) {
            $table->dropColumn('is_hero');
        });
    }
};
