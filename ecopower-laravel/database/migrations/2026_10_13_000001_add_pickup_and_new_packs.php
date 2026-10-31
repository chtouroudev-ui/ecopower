<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;

/**
 * Pack de Base et Pack Total (accord client du 13/10/2026) + option « retrait au local »
 * sur les commandes. Ne touche à rien de ce qui existe déjà.
 */
return new class extends Migration
{
    public function up(): void
    {
        Schema::table('orders', function (Blueprint $table) {
            if (! Schema::hasColumn('orders', 'delivery_method')) {
                $table->string('delivery_method', 20)->default('delivery')->after('delivery_fee');
            }
            if (! Schema::hasColumn('orders', 'discount')) {
                $table->decimal('discount', 10, 2)->default(0)->after('delivery_method');
            }
        });

        foreach (self::packs() as $pack) {
            if (! DB::table('products')->where('id', $pack['id'])->exists()) {
                DB::table('products')->insert($pack);
            }
        }
    }

    public function down(): void
    {
        DB::table('products')->whereIn('id', array_column(self::packs(), 'id'))->delete();
        Schema::table('orders', function (Blueprint $table) {
            $table->dropColumn(['delivery_method', 'discount']);
        });
    }

    public static function packs(): array
    {
        $data = json_decode(file_get_contents(database_path('data/products.json')), true) ?? [];
        $packs = array_values(array_filter($data, fn ($p) => in_array($p['id'], ['pack-base', 'pack-totale'], true)));

        return array_map(fn ($p) => [
            'id' => $p['id'],
            'name' => $p['name'],
            'name_ar' => $p['nameAr'] ?? null,
            'category' => $p['category'],
            'price' => $p['price'],
            'old_price' => ($p['oldPrice'] ?? null) ?: null,
            'rating' => $p['rating'] ?? 5,
            'reviews_count' => $p['reviewsCount'] ?? 0,
            'warranty' => $p['warranty'] ?? '3 ans',
            'debit' => $p['debit'] ?? null,
            'image' => $p['image'] ?? null,
            'description' => $p['description'] ?? '',
            'features' => json_encode($p['features'] ?? [], JSON_UNESCAPED_UNICODE),
            'stock' => $p['stock'] ?? 100,
            'is_featured' => ! empty($p['isFeatured']),
        ], $packs);
    }
};
