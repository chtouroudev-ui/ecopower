<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Support\Format;
use Illuminate\Support\Facades\DB;

class CertificateController extends Controller
{
    public function show(string $orderId)
    {
        $order = DB::table('orders')->where('id', $orderId)->first();
        if (! $order) {
            return response()->json(['error' => 'Certificat non trouvé pour cette commande'], 404);
        }

        $items = DB::table('order_items')->where('order_id', $orderId)->get();

        return response()->json([
            'orderId' => $order->id,
            'certificateSerial' => $order->certificate_serial ?: 'CERT-2026-'.$order->id,
            'issueDate' => Format::date($order->created_at),
            'customerName' => $order->customer_name,
            'customerPhone' => $order->customer_phone,
            'customerAddress' => ($order->customer_address ?: '').', '.($order->customer_city ?: '').' ('.($order->customer_governorate ?: '').')',
            'warrantyDuration' => '3 ANS (Eco-Sac garanti À VIE)',
            'standardConformity' => 'Normes Européennes ISO 9001 / ACS Attestation de Conformité Sanitaire / Delrin-Hostaform',
            'subtotal' => (float) $order->subtotal,
            'deliveryFee' => $order->delivery_fee !== null ? (float) $order->delivery_fee : 8.0,
            'total' => (float) $order->total,
            'items' => $items->map(fn ($i) => [
                'id' => (int) $i->id,
                'productId' => $i->product_id,
                'name' => $i->name,
                'price' => (float) $i->price,
                'quantity' => (int) $i->quantity,
                'serials' => Format::json($i->serials),
            ])->values(),
            'issuer' => [
                'company' => 'ECOPOWER TUNISIE / ECOGAM SARL',
                'technicalManager' => 'Pascal FABRE & Service Qualité',
                'phone' => '+216 98 000 000 / eceau-lo@orange.fr',
                'officialStamp' => 'CERTIFIÉ CONFORME AUX NORMES HYDRO-ÉCONOMIE',
            ],
        ]);
    }
}
