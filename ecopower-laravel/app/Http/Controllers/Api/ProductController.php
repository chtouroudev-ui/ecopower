<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Support\Format;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use Throwable;

class ProductController extends Controller
{
    public function index()
    {
        $products = DB::table('products')
            ->orderByDesc('is_featured')
            ->orderBy('price')
            ->get()
            ->map(fn ($p) => Format::product($p));

        return response()->json($products);
    }

    public function show(string $id)
    {
        $product = DB::table('products')->where('id', $id)->first();
        if (! $product) {
            return response()->json(['error' => 'Produit non trouvé'], 404);
        }

        return response()->json(Format::product($product));
    }

    public function store(Request $request)
    {
        $p = $request->all();
        $id = ($p['id'] ?? null) ?: 'prod-'.(int) round(microtime(true) * 1000);

        try {
            DB::table('products')->insert([
                'id' => $id,
                'name' => $p['name'] ?? null,
                'name_ar' => ($p['nameAr'] ?? null) ?: null,
                'category' => ($p['category'] ?? null) ?: 'packs',
                'price' => ($p['price'] ?? null) ?: 0,
                'old_price' => ($p['oldPrice'] ?? null) ?: null,
                'rating' => ($p['rating'] ?? null) ?: 5,
                'reviews_count' => ($p['reviewsCount'] ?? null) ?: 0,
                'warranty' => ($p['warranty'] ?? null) ?: '3 ans',
                'debit' => ($p['debit'] ?? null) ?: null,
                'image' => ($p['image'] ?? null) ?: '/products/bague_mousseur_complet.jpg',
                'description' => ($p['description'] ?? null) ?: '',
                'features' => json_encode($p['features'] ?? [], JSON_UNESCAPED_UNICODE),
                'stock' => array_key_exists('stock', $p) ? $p['stock'] : 50,
                'is_featured' => ! empty($p['isFeatured']) ? 1 : 0,
                'show_on_home' => ! empty($p['showOnHome']) ? 1 : 0,
                'pickup_discount' => ! empty($p['pickupDiscount']) ? 1 : 0,
                'is_hero' => ! empty($p['isHero']) ? 1 : 0,
            ]);
            if (! empty($p['isHero'])) {
                DB::table('products')->where('id', '!=', $id)->update(['is_hero' => 0]);
            }
        } catch (Throwable $e) {
            report($e);

            return response()->json(['error' => 'Erreur création produit'], 500);
        }

        return response()->json(array_merge(['id' => $id], $p), 201);
    }

    public function update(Request $request, string $id)
    {
        $map = [
            'name' => 'name', 'nameAr' => 'name_ar', 'category' => 'category', 'price' => 'price',
            'oldPrice' => 'old_price', 'stock' => 'stock', 'warranty' => 'warranty', 'debit' => 'debit',
            'description' => 'description', 'image' => 'image',
        ];

        $input = $request->all();
        $fields = [];
        foreach ($map as $key => $column) {
            if (array_key_exists($key, $input)) {
                $fields[$column] = $input[$key];
            }
        }
        if (array_key_exists('features', $input)) {
            $fields['features'] = json_encode($input['features'], JSON_UNESCAPED_UNICODE);
        }
        foreach (['isFeatured' => 'is_featured', 'showOnHome' => 'show_on_home', 'pickupDiscount' => 'pickup_discount', 'isHero' => 'is_hero'] as $key => $column) {
            if (array_key_exists($key, $input)) {
                $fields[$column] = $input[$key] ? 1 : 0;
            }
        }

        if (! $fields) {
            return response()->json(['error' => 'Aucun champ à mettre à jour'], 400);
        }

        try {
            if (! DB::table('products')->where('id', $id)->exists()) {
                return response()->json(['error' => 'Produit non trouvé'], 404);
            }
            DB::table('products')->where('id', $id)->update($fields);
            // Un seul produit vedette à la fois.
            if (! empty($fields['is_hero'])) {
                DB::table('products')->where('id', '!=', $id)->update(['is_hero' => 0]);
            }
        } catch (Throwable $e) {
            report($e);

            return response()->json(['error' => 'Erreur mise à jour produit'], 500);
        }

        return response()->json(Format::row(DB::table('products')->where('id', $id)->first()));
    }

    /** Envoi d'une photo produit depuis l'admin : enregistrée dans public/products/uploads. */
    public function uploadImage(Request $request)
    {
        // Type vérifié sur le contenu du fichier, extension choisie par le serveur.
        $types = ['image/jpeg' => 'jpg', 'image/png' => 'png', 'image/webp' => 'webp'];
        $file = $request->file('image');
        if (! $file || ! $file->isValid() || ! isset($types[$file->getMimeType()]) || $file->getSize() > 5 * 1024 * 1024) {
            return response()->json(['error' => 'Image invalide : JPG, PNG ou WEBP, 5 Mo maximum.'], 422);
        }
        $name = date('Ymd-His').'-'.Str::lower(Str::random(6)).'.'.$types[$file->getMimeType()];
        $dir = public_path('products/uploads');
        if (! is_dir($dir)) {
            @mkdir($dir, 0755, true);
        }

        try {
            $file->move($dir, $name);
        } catch (Throwable $e) {
            report($e);

            return response()->json(['error' => 'Impossible d\'enregistrer l\'image sur le serveur.'], 500);
        }

        return response()->json(['url' => '/products/uploads/'.$name], 201);
    }

    public function destroy(string $id)
    {
        if (! DB::table('products')->where('id', $id)->delete()) {
            return response()->json(['error' => 'Produit non trouvé'], 404);
        }

        return response()->json(['message' => 'Produit supprimé avec succès']);
    }
}
