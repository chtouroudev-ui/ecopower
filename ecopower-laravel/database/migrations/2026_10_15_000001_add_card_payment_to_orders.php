<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

/** Paiement par carte (Konnect) : statut du paiement et référence Konnect sur chaque commande. */
return new class extends Migration
{
    public function up(): void
    {
        Schema::table('orders', function (Blueprint $table) {
            if (! Schema::hasColumn('orders', 'payment_status')) {
                // unpaid = espèces à la livraison / au retrait ; pending, paid, failed = carte
                $table->string('payment_status', 20)->default('unpaid')->after('payment_method');
            }
            if (! Schema::hasColumn('orders', 'payment_ref')) {
                $table->string('payment_ref', 100)->nullable()->index('idx_payment_ref')->after('payment_status');
            }
        });
    }

    public function down(): void
    {
        Schema::table('orders', function (Blueprint $table) {
            $table->dropIndex('idx_payment_ref');
            $table->dropColumn(['payment_status', 'payment_ref']);
        });
    }
};
