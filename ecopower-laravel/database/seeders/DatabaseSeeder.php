<?php

namespace Database\Seeders;

use Carbon\Carbon;
use Illuminate\Database\Seeder;
use Illuminate\Support\Facades\DB;

/**
 * Données initiales reprises de server/data/*.json (copiées dans database/data).
 * Comme l'ancien serveur, chaque table n'est remplie que si elle est vide.
 */
class DatabaseSeeder extends Seeder
{
    public function run(): void
    {
        if (! DB::table('users')->exists()) {
            DB::table('users')->insert([
                'name' => 'Direction EcoPower',
                'email' => strtolower(config('ecopower.admin_email')),
                'password' => password_hash(config('ecopower.admin_password'), PASSWORD_BCRYPT, ['cost' => 10]),
                'role' => 'admin',
                'phone' => '+216 98 000 000',
            ]);
        }

        if (! DB::table('products')->exists()) {
            foreach ($this->load('products') as $p) {
                DB::table('products')->insert([
                    'id' => $p['id'],
                    'name' => $p['name'],
                    'name_ar' => $p['nameAr'] ?? null,
                    'category' => $p['category'] ?? 'packs',
                    'price' => $p['price'] ?? 0,
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
                ]);
            }
        }

        if (! DB::table('orders')->exists()) {
            foreach ($this->load('orders') as $o) {
                $c = $o['customer'] ?? [];
                DB::table('orders')->insert([
                    'id' => $o['id'],
                    'customer_name' => ($c['fullName'] ?? null) ?: 'Client',
                    'customer_phone' => $c['phone'] ?? '',
                    'customer_email' => ($c['email'] ?? null) ?: null,
                    'customer_address' => $c['address'] ?? '',
                    'customer_city' => $c['city'] ?? '',
                    'customer_governorate' => ($c['governorate'] ?? null) ?: 'Tunis',
                    'subtotal' => $o['subtotal'] ?? 0,
                    'delivery_fee' => $o['deliveryFee'] ?? 0,
                    'total' => $o['total'] ?? 0,
                    'payment_method' => ($o['paymentMethod'] ?? null) ?: 'cod',
                    'status' => ($o['status'] ?? null) ?: 'pending',
                    'certificate_serial' => ($o['certificateSerial'] ?? null) ?: 'CERT-2026-'.$o['id'],
                    'notes' => $o['notes'] ?? '',
                    'created_at' => $this->date($o['date'] ?? null),
                ]);

                foreach ($o['items'] ?? [] as $item) {
                    DB::table('order_items')->insert([
                        'order_id' => $o['id'],
                        'product_id' => ($item['productId'] ?? null) ?: 'item',
                        'name' => ($item['name'] ?? null) ?: 'Produit',
                        'price' => $item['price'] ?? 0,
                        'quantity' => $item['quantity'] ?? 1,
                        'serials' => json_encode($item['serials'] ?? []),
                    ]);
                }
            }
        }

        if (! DB::table('leads')->exists()) {
            foreach ($this->load('leads') as $l) {
                $date = $this->date($l['date'] ?? null);
                DB::table('leads')->insert([
                    'id' => $l['id'],
                    'date' => $date,
                    'company' => $l['company'] ?? '',
                    'contact_person' => $l['contactPerson'] ?? '',
                    'role' => $l['role'] ?? '',
                    'phone' => $l['phone'] ?? '',
                    'email' => ($l['email'] ?? null) ?: null,
                    'type' => ($l['type'] ?? null) ?: 'entreprise',
                    'rooms_count' => $l['roomsCount'] ?? 0,
                    'current_water_bill_monthly' => (string) ($l['currentWaterBillMonthly'] ?? ''),
                    'interest' => $l['interest'] ?? '',
                    'status' => ($l['status'] ?? null) ?: 'new',
                    'notes' => $l['notes'] ?? '',
                    'created_at' => $date,
                ]);
            }
        }
    }

    private function load(string $name): array
    {
        $file = database_path("data/$name.json");

        return is_file($file) ? json_decode(file_get_contents($file), true) ?? [] : [];
    }

    private function date(?string $iso): string
    {
        return ($iso ? Carbon::parse($iso) : Carbon::now())->setTimezone(config('app.timezone'))->format('Y-m-d H:i:s');
    }
}
