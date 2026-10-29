<?php

namespace App\Providers;

use App\Support\AutoMigrate;
use Illuminate\Cache\RateLimiting\Limit;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\RateLimiter;
use Illuminate\Support\ServiceProvider;

class AppServiceProvider extends ServiceProvider
{
    public function register(): void
    {
        //
    }

    public function boot(): void
    {
        // Mêmes limites que l'ancien serveur Express (par adresse IP).
        $limit = fn (int $minutes, int $max, string $message) => fn (Request $request) => Limit::perMinutes($minutes, $max)
            ->by($request->ip())
            ->response(fn () => response()->json(['error' => $message], 429));

        RateLimiter::for('login', $limit(15, 20, 'Trop de tentatives de connexion. Veuillez patienter 15 minutes.'));
        RateLimiter::for('orders', $limit(10, 20, 'Trop de requêtes de commande. Veuillez patienter quelques minutes.'));
        RateLimiter::for('tracking', $limit(5, 40, 'Trop de recherches de commande. Veuillez patienter.'));

        if (! $this->app->runningInConsole()) {
            AutoMigrate::run();
        }
    }
}
