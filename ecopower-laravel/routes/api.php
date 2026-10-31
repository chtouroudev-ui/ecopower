<?php

use App\Http\Controllers\Api\AuthController;
use App\Http\Controllers\Api\CertificateController;
use App\Http\Controllers\Api\LeadController;
use App\Http\Controllers\Api\OrderController;
use App\Http\Controllers\Api\ProductController;
use App\Http\Controllers\Api\StatsController;
use Illuminate\Support\Facades\Route;

// Préfixe /api ajouté dans bootstrap/app.php. Les limiteurs sont définis dans AppServiceProvider.

// 1. Auth (admin uniquement : les acheteurs n'ont pas de compte)
Route::post('/auth/login', [AuthController::class, 'login'])->middleware('throttle:login');
Route::get('/auth/me', [AuthController::class, 'me'])->middleware('jwt');

// 2. Produits
Route::get('/products', [ProductController::class, 'index']);
Route::get('/products/{id}', [ProductController::class, 'show']);

// 3. Commandes publiques (paiement à la livraison) et suivi
Route::post('/orders', [OrderController::class, 'store'])->middleware('throttle:orders');
Route::get('/orders/track/{query}', [OrderController::class, 'track'])->middleware('throttle:tracking');

// 3 bis. Paiement par carte (Konnect)
Route::get('/payments/methods', [OrderController::class, 'paymentMethods']);
Route::get('/payments/konnect/webhook', [OrderController::class, 'konnectWebhook'])->middleware('throttle:tracking');
Route::post('/orders/{id}/payment/check', [OrderController::class, 'checkPayment'])->middleware('throttle:tracking');
Route::post('/orders/{id}/payment/retry', [OrderController::class, 'retryPayment'])->middleware('throttle:orders');

// 4. Certificat de garantie
Route::get('/certificate/{orderId}', [CertificateController::class, 'show']);

// 5. Demandes B2B
Route::post('/leads', [LeadController::class, 'store'])->middleware('throttle:orders');

// Administration
Route::middleware('jwt:admin')->group(function () {
    Route::post('/products', [ProductController::class, 'store']);
    Route::post('/products/image', [ProductController::class, 'uploadImage']);
    Route::put('/products/{id}', [ProductController::class, 'update']);
    Route::delete('/products/{id}', [ProductController::class, 'destroy']);

    Route::get('/orders', [OrderController::class, 'index']);
    Route::put('/orders/{id}/status', [OrderController::class, 'update']);
    Route::put('/orders/{id}', [OrderController::class, 'update']);

    Route::get('/leads', [LeadController::class, 'index']);
    Route::put('/leads/{id}', [LeadController::class, 'update']);

    Route::get('/stats', StatsController::class);
});

Route::any('/{any}', fn () => response()->json(['error' => 'Route API introuvable'], 404))->where('any', '.*');
