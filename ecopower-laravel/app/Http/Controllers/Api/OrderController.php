<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Support\Format;
use App\Support\Konnect;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;
use App\Support\PublicError;
use Throwable;

class OrderController extends Controller
{
    private const STATUSES = ['pending', 'confirmed', 'shipped', 'delivered', 'cancelled'];

    /** Liste complète (admin). */
    public function index()
    {
        $orders = DB::table('orders')->orderByDesc('created_at')->get();
        $items = DB::table('order_items')->get()->groupBy('order_id');

        return response()->json($orders->map(fn ($o) => [
            'id' => $o->id,
            'date' => Format::date($o->created_at),
            'customer' => [
                'fullName' => $o->customer_name,
                'phone' => $o->customer_phone,
                'email' => $o->customer_email ?: '',
                'address' => $o->customer_address ?: '',
                'city' => $o->customer_city ?: '',
                'governorate' => $o->customer_governorate ?: 'Tunis',
            ],
            'items' => ($items[$o->id] ?? collect())->map(fn ($i) => [
                'id' => (int) $i->id,
                'productId' => $i->product_id,
                'name' => $i->name,
                'price' => (float) $i->price,
                'quantity' => (int) $i->quantity,
                'serials' => Format::json($i->serials),
            ])->values(),
            'subtotal' => (float) $o->subtotal,
            'deliveryFee' => (float) $o->delivery_fee,
            'deliveryMethod' => $o->delivery_method ?? 'delivery',
            'discount' => (float) ($o->discount ?? 0),
            'total' => (float) $o->total,
            'paymentMethod' => $o->payment_method,
            'paymentStatus' => $o->payment_status ?? 'unpaid',
            'status' => $o->status,
            'certificateGenerated' => (bool) $o->certificate_serial,
            'certificateSerial' => $o->certificate_serial,
            'notes' => $o->notes ?: '',
        ])->values());
    }

    /** Suivi public par référence ECO-xxxx ou numéro de téléphone. */
    public function track(string $query)
    {
        $clean = strtoupper(trim($query));
        $digits = preg_replace('/^216/', '', preg_replace('/[^0-9]/', '', $clean));
        if (preg_match('/^[0-9\s+]+$/', $clean) && strlen($digits) === 8) {
            $clean = $digits;
        }

        $orders = DB::table('orders')
            ->where('id', $clean)
            ->orWhere('customer_phone', $clean)
            ->orderByDesc('created_at')
            ->limit(5)
            ->get();

        if ($orders->isEmpty()) {
            return response()->json(['error' => 'Aucune commande trouvée avec cette référence ou ce numéro de téléphone.'], 404);
        }

        $items = DB::table('order_items')->whereIn('order_id', $orders->pluck('id'))->get()->groupBy('order_id');

        return response()->json($orders->map(fn ($o) => [
            'id' => $o->id,
            'date' => Format::date($o->created_at),
            'customerName' => $o->customer_name,
            'customerPhone' => $o->customer_phone,
            'governorate' => $o->customer_governorate,
            'items' => ($items[$o->id] ?? collect())->map(fn ($i) => [
                'name' => $i->name,
                'quantity' => (int) $i->quantity,
                'price' => (float) $i->price,
                'serials' => Format::json($i->serials),
            ])->values(),
            'total' => (float) $o->total,
            'deliveryFee' => (float) $o->delivery_fee,
            'deliveryMethod' => $o->delivery_method ?? 'delivery',
            'discount' => (float) ($o->discount ?? 0),
            'status' => $o->status,
            'paymentMethod' => $o->payment_method,
            'paymentStatus' => $o->payment_status ?? 'unpaid',
            'certificateSerial' => $o->certificate_serial,
        ])->values());
    }

    /** Commande publique sans compte : espèces (livraison / retrait) ou carte bancaire via Konnect. */
    public function store(Request $request)
    {
        $customer = $request->input('customer');
        $items = $request->input('items');
        $notes = $request->input('notes', '');
        $customer = is_array($customer) ? $customer : [];
        $deliveryMethod = $request->input('deliveryMethod') === 'pickup' ? 'pickup' : 'delivery';

        $phone = preg_replace('/^216/', '', preg_replace('/[^0-9]/', '', (string) ($customer['phone'] ?? '')));
        if (trim((string) ($customer['fullName'] ?? '')) === '' || ! is_array($items) || ! $items
            || ($deliveryMethod === 'delivery' && trim((string) ($customer['address'] ?? '')) === '')) {
            return response()->json(['error' => 'Veuillez renseigner votre nom, votre adresse et au moins un article.'], 400);
        }
        if (! preg_match('/^[2-9][0-9]{7}$/', $phone)) {
            return response()->json(['error' => 'Numéro de téléphone invalide (8 chiffres attendus).'], 400);
        }
        $customer['phone'] = $phone;
        $paymentMethod = $request->input('paymentMethod') === 'card' ? 'card' : 'cod';
        if ($paymentMethod === 'card' && ! Konnect::enabled()) {
            return response()->json(['error' => 'Le paiement par carte n\'est pas disponible pour le moment.'], 400);
        }

        try {
            $order = DB::transaction(function () use ($customer, $items, $notes, $paymentMethod, $deliveryMethod) {
                $last = DB::selectOne(
                    "SELECT MAX(CAST(SUBSTRING(id, 5) AS UNSIGNED)) AS lastNum FROM orders WHERE id LIKE 'ECO-%' FOR UPDATE"
                );
                $orderId = 'ECO-'.(max(1000, (int) ($last->lastNum ?? 0)) + 1);
                $certSerial = 'CERT-'.date('Y').'-'.$orderId;

                $subtotal = 0.0;
                $pickupPacksTotal = 0.0;
                $enriched = [];

                foreach ($items as $item) {
                    $productId = $item['productId'] ?? null;
                    $prod = DB::table('products')->where('id', $productId)->first();
                    if (! $prod) {
                        throw new PublicError('Le produit « '.(($item['name'] ?? null) ?: $productId).' » n\'est plus disponible.');
                    }

                    $price = (float) $prod->price;
                    $qty = min(99, max(1, (int) ($item['quantity'] ?? 1) ?: 1));
                    $subtotal += $price * $qty;
                    if (! empty($prod->pickup_discount)) {
                        $pickupPacksTotal += $price * $qty;
                    }

                    $serials = [];
                    for ($i = 0; $i < $qty; $i++) {
                        $serials[] = self::serial($productId);
                    }

                    $enriched[] = [
                        'productId' => $productId,
                        'name' => $prod->name,
                        'price' => $price,
                        'quantity' => $qty,
                        'serials' => $serials,
                    ];

                    DB::update('UPDATE products SET stock = GREATEST(0, stock - ?) WHERE id = ?', [$qty, $productId]);
                }

                // Retrait au local : réservé aux commandes avec un pack éligible,
                // sans frais de livraison et avec une remise sur ces packs seulement.
                if ($deliveryMethod === 'pickup' && $pickupPacksTotal <= 0) {
                    throw new PublicError('Le retrait au local n\'est pas disponible pour les produits de votre panier.');
                }
                $discount = $deliveryMethod === 'pickup'
                    ? round($pickupPacksTotal * config('ecopower.pickup_discount_rate'), 2)
                    : 0.0;
                $deliveryFee = $deliveryMethod === 'pickup' || $subtotal >= config('ecopower.free_delivery_from')
                    ? 0 : config('ecopower.delivery_fee');
                $total = $subtotal - $discount + $deliveryFee;

                DB::table('orders')->insert([
                    'id' => $orderId,
                    'user_id' => null,
                    'customer_name' => mb_substr(trim((string) $customer['fullName']), 0, 150),
                    'customer_phone' => $customer['phone'],
                    'customer_email' => ($customer['email'] ?? null) ?: null,
                    'customer_address' => ($customer['address'] ?? null) ?: '',
                    'customer_city' => ($customer['city'] ?? null) ?: '',
                    'customer_governorate' => ($customer['governorate'] ?? null) ?: 'Tunis',
                    'subtotal' => $subtotal,
                    'delivery_fee' => $deliveryFee,
                    'delivery_method' => $deliveryMethod,
                    'discount' => $discount,
                    'total' => $total,
                    'payment_method' => $paymentMethod,
                    'payment_status' => $paymentMethod === 'card' ? 'pending' : 'unpaid',
                    'status' => 'pending',
                    'certificate_serial' => $certSerial,
                    'notes' => mb_substr((string) ($notes ?: ''), 0, 1000),
                ]);

                DB::table('order_items')->insert(array_map(fn ($i) => [
                    'order_id' => $orderId,
                    'product_id' => $i['productId'],
                    'name' => $i['name'],
                    'price' => $i['price'],
                    'quantity' => $i['quantity'],
                    'serials' => json_encode($i['serials']),
                ], $enriched));

                return [
                    'id' => $orderId,
                    'date' => now()->utc()->format('Y-m-d\TH:i:s.v\Z'),
                    'customer' => $customer,
                    'items' => $enriched,
                    'subtotal' => round($subtotal, 2),
                    'deliveryFee' => $deliveryFee,
                    'deliveryMethod' => $deliveryMethod,
                    'discount' => $discount,
                    'total' => round($total, 2),
                    'paymentMethod' => $paymentMethod,
                    'paymentStatus' => $paymentMethod === 'card' ? 'pending' : 'unpaid',
                    'status' => 'pending',
                    'certificateGenerated' => true,
                    'certificateSerial' => $certSerial,
                    'notes' => $notes,
                ];
            });
        } catch (PublicError $e) {
            return response()->json(['error' => $e->getMessage()], 400);
        } catch (Throwable $e) {
            report($e);

            return response()->json(['error' => 'Erreur lors de la validation de la commande'], 500);
        }

        if ($paymentMethod === 'card') {
            try {
                $order['payUrl'] = $this->startPayment($order['id']);
            } catch (Throwable $e) {
                report($e);
                $this->discard($order['id']);

                return response()->json(['error' => 'Le paiement par carte est momentanément indisponible. Réessayez ou choisissez le paiement en espèces.'], 502);
            }
        }

        return response()->json($order, 201);
    }

    /** Moyens de paiement disponibles et infos de retrait au local, pour le front. */
    public function paymentMethods()
    {
        return response()->json([
            'card' => Konnect::enabled(),
            'pickup' => [
                'address' => config('ecopower.pickup_address'),
                'hours' => config('ecopower.pickup_hours'),
                'mapUrl' => config('ecopower.pickup_map_url'),
                'productIds' => DB::table('products')->where('pickup_discount', 1)->pluck('id'),
            ],
        ]);
    }

    /** Konnect appelle cette URL (GET ?payment_ref=...) quand un paiement change d'état. */
    public function konnectWebhook(Request $request)
    {
        $ref = (string) $request->query('payment_ref', '');
        $order = $ref !== '' ? DB::table('orders')->where('payment_ref', $ref)->first() : null;
        if ($order) {
            $this->syncPayment($order);
        }

        return response()->json(['ok' => true]);
    }

    /** Retour du client après la page Konnect : on redemande l'état du paiement à Konnect. */
    public function checkPayment(string $id)
    {
        $order = DB::table('orders')->where('id', $id)->where('payment_method', 'card')->first();
        if (! $order) {
            return response()->json(['error' => 'Commande non trouvée'], 404);
        }

        return response()->json(['id' => $id, 'paymentStatus' => $this->syncPayment($order), 'total' => (float) $order->total]);
    }

    /** Nouveau lien de paiement si le premier essai a échoué ou a expiré. */
    public function retryPayment(string $id)
    {
        $order = DB::table('orders')->where('id', $id)->where('payment_method', 'card')->first();
        if (! $order || $order->status === 'cancelled') {
            return response()->json(['error' => 'Commande non trouvée'], 404);
        }
        if ($this->syncPayment($order) === 'paid') {
            return response()->json(['error' => 'Cette commande est déjà payée.'], 400);
        }

        try {
            return response()->json(['payUrl' => $this->startPayment($id)]);
        } catch (Throwable $e) {
            report($e);

            return response()->json(['error' => 'Le paiement par carte est momentanément indisponible. Réessayez plus tard.'], 502);
        }
    }

    private function startPayment(string $orderId): string
    {
        $order = DB::table('orders')->where('id', $orderId)->first();
        $payment = Konnect::initPayment($order);
        DB::table('orders')->where('id', $orderId)->update(['payment_ref' => $payment['paymentRef'], 'payment_status' => 'pending']);

        return $payment['payUrl'];
    }

    /** Met la commande à jour d'après Konnect (seule source fiable) et renvoie le statut de paiement. */
    private function syncPayment(object $order): string
    {
        if (($order->payment_status ?? '') === 'paid' || ! $order->payment_ref) {
            return $order->payment_status ?? 'unpaid';
        }

        try {
            $payment = Konnect::payment($order->payment_ref);
        } catch (Throwable $e) {
            report($e);

            return $order->payment_status;
        }

        $paid = ($payment['status'] ?? '') === 'completed'
            && (int) ($payment['amount'] ?? 0) >= (int) round($order->total * 1000);
        $status = $paid ? 'paid' : (in_array($payment['status'] ?? '', ['failed', 'expired', 'canceled', 'cancelled'], true) ? 'failed' : 'pending');

        $fields = ['payment_status' => $status];
        if ($paid && $order->status === 'pending') {
            $fields['status'] = 'confirmed';
        }
        DB::table('orders')->where('id', $order->id)->update($fields);

        return $status;
    }

    /** Annule une commande carte dont le paiement n'a pas pu démarrer (remise en stock). */
    private function discard(string $orderId): void
    {
        DB::transaction(function () use ($orderId) {
            foreach (DB::table('order_items')->where('order_id', $orderId)->get(['product_id', 'quantity']) as $item) {
                DB::update('UPDATE products SET stock = stock + ? WHERE id = ?', [$item->quantity, $item->product_id]);
            }
            DB::table('order_items')->where('order_id', $orderId)->delete();
            DB::table('orders')->where('id', $orderId)->delete();
        });
    }

    /** Statut et/ou notes (admin), avec remise en stock à l'annulation. */
    public function update(Request $request, string $id)
    {
        $status = $request->input('status');
        $hasNotes = $request->exists('notes');
        $notes = $request->input('notes');

        if ($status !== null && ! in_array($status, self::STATUSES, true)) {
            return response()->json(['error' => 'Statut de commande invalide'], 400);
        }
        if ($status === null && ! $hasNotes) {
            return response()->json(['error' => 'Aucune donnée à mettre à jour'], 400);
        }

        try {
            $result = DB::transaction(function () use ($id, $status, $hasNotes, $notes) {
                $order = DB::table('orders')->where('id', $id)->lockForUpdate()->first(['status']);
                if (! $order) {
                    return null;
                }

                $wasCancelled = $order->status === 'cancelled';
                $willBeCancelled = $status ? $status === 'cancelled' : $wasCancelled;
                if ($wasCancelled !== $willBeCancelled) {
                    $sql = $willBeCancelled
                        ? 'UPDATE products SET stock = stock + ? WHERE id = ?'
                        : 'UPDATE products SET stock = GREATEST(0, stock - ?) WHERE id = ?';
                    foreach (DB::table('order_items')->where('order_id', $id)->get(['product_id', 'quantity']) as $item) {
                        DB::update($sql, [$item->quantity, $item->product_id]);
                    }
                }

                $fields = [];
                if ($status) {
                    $fields['status'] = $status;
                }
                if ($hasNotes) {
                    $fields['notes'] = mb_substr((string) $notes, 0, 2000);
                }
                DB::table('orders')->where('id', $id)->update($fields);

                return ['id' => $id, 'status' => $status ?: $order->status, 'notes' => $notes];
            });
        } catch (Throwable $e) {
            report($e);

            return response()->json(['error' => 'Erreur mise à jour commande'], 500);
        }

        if ($result === null) {
            return response()->json(['error' => 'Commande non trouvée'], 404);
        }

        return response()->json($result);
    }

    private static function serial(?string $productId): string
    {
        $prefix = substr(preg_replace('/[^A-Z0-9]/', '', strtoupper($productId ?: 'PROD')), 0, 4);

        return 'SN-'.$prefix.'-'.date('Y').'-'.random_int(1000, 9999);
    }
}
