<?php

namespace App\Support;

use Carbon\Carbon;

/**
 * Mise en forme des lignes MySQL au format JSON attendu par le front React
 * (mêmes clés que l'ancienne API Express).
 */
class Format
{
    public static function date($value): ?string
    {
        if ($value === null) {
            return null;
        }

        return Carbon::parse($value, config('app.timezone'))->utc()->format('Y-m-d\TH:i:s.v\Z');
    }

    public static function json($value): array
    {
        if (is_array($value)) {
            return $value;
        }
        $decoded = is_string($value) ? json_decode($value, true) : null;

        return is_array($decoded) ? $decoded : [];
    }

    public static function product(object $p): array
    {
        return [
            'id' => $p->id,
            'name' => $p->name,
            'nameAr' => $p->name_ar,
            'category' => $p->category,
            'price' => (float) $p->price,
            'oldPrice' => $p->old_price ? (float) $p->old_price : null,
            'rating' => (float) $p->rating,
            'reviewsCount' => (int) $p->reviews_count,
            'warranty' => $p->warranty,
            'debit' => $p->debit,
            'image' => $p->image,
            'description' => $p->description,
            'features' => self::json($p->features),
            'stock' => (int) $p->stock,
            'isFeatured' => (bool) $p->is_featured,
            'showOnHome' => (bool) ($p->show_on_home ?? false),
            'pickupDiscount' => (bool) ($p->pickup_discount ?? false),
            'isHero' => (bool) ($p->is_hero ?? false),
        ];
    }

    /** Ligne brute (comme mysql2 la renvoyait) : JSON décodé, dates ISO. */
    public static function row(object $row): array
    {
        $data = (array) $row;
        foreach (['features', 'serials'] as $key) {
            if (array_key_exists($key, $data)) {
                $data[$key] = self::json($data[$key]);
            }
        }
        foreach (['created_at', 'updated_at', 'date'] as $key) {
            if (! empty($data[$key])) {
                $data[$key] = self::date($data[$key]);
            }
        }

        return $data;
    }
}
