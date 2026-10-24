<?php

namespace App\Http\Middleware;

use App\Support\Jwt;
use Closure;
use Illuminate\Http\Request;
use Symfony\Component\HttpFoundation\Response;

/** Équivalent de authenticateToken (+ requireAdmin avec le paramètre "admin"). */
class AdminToken
{
    public function handle(Request $request, Closure $next, ?string $role = null): Response
    {
        $token = $request->bearerToken();
        if (! $token) {
            return response()->json(['error' => 'Accès non autorisé: token requis'], 401);
        }

        $user = Jwt::decode($token, config('ecopower.jwt_secret'));
        if (! $user) {
            return response()->json(['error' => 'Token invalide ou expiré'], 403);
        }

        if ($role === 'admin' && ($user['role'] ?? null) !== 'admin') {
            return response()->json(['error' => 'Accès refusé: privilèges administrateur requis'], 403);
        }

        $request->attributes->set('jwt_user', $user);

        return $next($request);
    }
}
