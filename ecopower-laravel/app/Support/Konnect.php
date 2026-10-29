<?php

namespace App\Support;

use Illuminate\Support\Facades\Http;
use RuntimeException;

/**
 * Passerelle de paiement Konnect (cartes bancaires tunisiennes, e-DINAR, wallet Konnect).
 * Doc : https://api.konnect.network/api/v2/konnect-gateway
 */
class Konnect
{
    public static function enabled(): bool
    {
        return config('ecopower.konnect.api_key') && config('ecopower.konnect.wallet_id');
    }

    private static function baseUrl(): string
    {
        return rtrim(config('ecopower.konnect.base_url') ?: (config('ecopower.konnect.sandbox')
            ? 'https://api.sandbox.konnect.network/api/v2'
            : 'https://api.konnect.network/api/v2'), '/');
    }

    private static function http()
    {
        return Http::withHeaders(['x-api-key' => config('ecopower.konnect.api_key')])
            ->acceptJson()
            ->timeout(15);
    }

    /** Crée un paiement et renvoie ['payUrl' => ..., 'paymentRef' => ...]. */
    public static function initPayment(object $order): array
    {
        $names = preg_split('/\s+/', trim($order->customer_name), 2);
        $returnUrl = rtrim(config('app.url'), '/').'/tracking?commande='.urlencode($order->id).'&paiement=retour';

        $response = self::http()->post(self::baseUrl().'/payments/init-payment', array_filter([
            'receiverWalletId' => config('ecopower.konnect.wallet_id'),
            'token' => 'TND',
            'amount' => (int) round($order->total * 1000), // en millimes
            'type' => 'immediate',
            'description' => 'Commande EcoPower '.$order->id,
            'acceptedPaymentMethods' => ['bank_card', 'e-DINAR', 'wallet'],
            'lifespan' => 30,
            'checkoutForm' => false,
            'addPaymentFeesToAmount' => false,
            'firstName' => $names[0] ?? '',
            'lastName' => $names[1] ?? '',
            'phoneNumber' => $order->customer_phone,
            'email' => $order->customer_email,
            'orderId' => $order->id,
            'webhook' => rtrim(config('app.url'), '/').'/api/payments/konnect/webhook',
            'silentWebhook' => true,
            'successUrl' => $returnUrl,
            'failUrl' => $returnUrl,
            'theme' => 'light',
        ], fn ($v) => $v !== null && $v !== ''));

        if (! $response->successful() || ! $response->json('payUrl') || ! $response->json('paymentRef')) {
            throw new RuntimeException('Konnect init-payment '.$response->status().': '.mb_substr($response->body(), 0, 500));
        }

        return ['payUrl' => $response->json('payUrl'), 'paymentRef' => $response->json('paymentRef')];
    }

    /** Détails d'un paiement tels que Konnect les connaît (statut « completed » = payé). */
    public static function payment(string $paymentRef): array
    {
        $response = self::http()->get(self::baseUrl().'/payments/'.rawurlencode($paymentRef));
        if (! $response->successful()) {
            throw new RuntimeException('Konnect payment '.$response->status().': '.mb_substr($response->body(), 0, 500));
        }

        return (array) $response->json('payment', []);
    }
}
