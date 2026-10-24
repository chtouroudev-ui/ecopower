<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;

/**
 * Schéma identique à celui créé par l'ancien serveur Express (server/db.js).
 * Chaque table n'est créée que si elle n'existe pas : la migration peut donc tourner
 * sur la base ecopower_db déjà en production sans rien perdre.
 */
return new class extends Migration
{
    public function up(): void
    {
        if (! Schema::hasTable('users')) {
            Schema::create('users', function (Blueprint $table) {
                $table->increments('id');
                $table->string('name', 150);
                $table->string('email', 191)->unique();
                $table->string('password', 255);
                $table->enum('role', ['admin', 'client'])->default('client');
                $table->string('phone', 50)->nullable();
                $table->dateTime('created_at')->useCurrent();
            });
        }

        if (! Schema::hasTable('products')) {
            Schema::create('products', function (Blueprint $table) {
                $table->string('id', 100)->primary();
                $table->string('name', 255);
                $table->string('name_ar', 255)->nullable();
                $table->string('category', 100)->nullable()->default('packs');
                $table->decimal('price', 10, 2);
                $table->decimal('old_price', 10, 2)->nullable();
                $table->decimal('rating', 3, 1)->nullable()->default(5.0);
                $table->integer('reviews_count')->nullable()->default(0);
                $table->string('warranty', 100)->nullable()->default('3 ans');
                $table->string('debit', 50)->nullable();
                $table->string('image', 255)->nullable();
                $table->text('description')->nullable();
                $table->json('features')->nullable();
                $table->integer('stock')->nullable()->default(100);
                $table->boolean('is_featured')->nullable()->default(false);
                $table->dateTime('created_at')->useCurrent();
                $table->dateTime('updated_at')->useCurrent()->useCurrentOnUpdate();
            });
        }

        if (! Schema::hasTable('orders')) {
            Schema::create('orders', function (Blueprint $table) {
                $table->string('id', 100)->primary();
                $table->integer('user_id')->nullable();
                $table->string('customer_name', 150);
                $table->string('customer_phone', 50)->index('idx_customer_phone');
                $table->string('customer_email', 191)->nullable()->index('idx_customer_email');
                $table->text('customer_address')->nullable();
                $table->string('customer_city', 100)->nullable();
                $table->string('customer_governorate', 100)->nullable();
                $table->decimal('subtotal', 10, 2);
                $table->decimal('delivery_fee', 10, 2)->default(8.00);
                $table->decimal('total', 10, 2);
                $table->string('payment_method', 50)->nullable()->default('cod');
                $table->string('status', 50)->nullable()->default('pending');
                $table->string('certificate_serial', 100)->nullable();
                $table->text('notes')->nullable();
                $table->dateTime('created_at')->useCurrent();
            });
        }

        if (! Schema::hasTable('order_items')) {
            Schema::create('order_items', function (Blueprint $table) {
                $table->increments('id');
                $table->string('order_id', 100)->index('idx_order_id');
                $table->string('product_id', 100);
                $table->string('name', 255);
                $table->decimal('price', 10, 2);
                $table->integer('quantity')->default(1);
                $table->json('serials')->nullable();
                $table->foreign('order_id', 'fk_order')->references('id')->on('orders')->cascadeOnDelete();
            });
        }

        if (! Schema::hasTable('leads')) {
            Schema::create('leads', function (Blueprint $table) {
                $table->string('id', 100)->primary();
                $table->dateTime('date')->useCurrent();
                $table->string('company', 255);
                $table->string('contact_person', 150);
                $table->string('role', 100)->nullable();
                $table->string('phone', 50);
                $table->string('email', 191)->nullable();
                $table->string('type', 50)->nullable()->default('entreprise');
                $table->integer('rooms_count')->nullable()->default(0);
                $table->string('current_water_bill_monthly', 100)->nullable();
                $table->string('interest', 255)->nullable();
                $table->string('status', 50)->nullable()->default('new');
                $table->text('notes')->nullable();
                $table->dateTime('created_at')->useCurrent();
            });
        }
    }

    public function down(): void
    {
        Schema::dropIfExists('order_items');
        Schema::dropIfExists('orders');
        Schema::dropIfExists('leads');
        Schema::dropIfExists('products');
        Schema::dropIfExists('users');
    }
};
