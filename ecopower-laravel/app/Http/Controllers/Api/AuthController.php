<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Support\Format;
use App\Support\Jwt;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\RateLimiter;

class AuthController extends Controller
{
    /** 5 mots de passe faux depuis la même adresse IP = connexion bloquée 24 h. */
    private const MAX_FAILED_LOGINS = 5;
    private const LOCKOUT_SECONDS = 24 * 3600;

    public function login(Request $request)
    {
        $lockKey = 'admin-login-failed:'.$request->ip();
        if (RateLimiter::tooManyAttempts($lockKey, self::MAX_FAILED_LOGINS)) {
            $hours = max(1, (int) ceil(RateLimiter::availableIn($lockKey) / 3600));

            return response()->json([
                'error' => "Trop de mots de passe incorrects. Connexion bloquée pendant encore {$hours} h.",
            ], 429);
        }

        $email = $request->input('email');
        $password = $request->input('password');
        if (! $email || ! $password) {
            return response()->json(['error' => 'Email et mot de passe requis'], 400);
        }

        $dbUser = DB::table('users')->where('email', strtolower(trim((string) $email)))->first();

        // password_verify accepte les hash $2a$/$2b$ produits par bcryptjs.
        if (! $dbUser || ! password_verify((string) $password, $dbUser->password) || $dbUser->role !== 'admin') {
            RateLimiter::hit($lockKey, self::LOCKOUT_SECONDS);
            $left = self::MAX_FAILED_LOGINS - RateLimiter::attempts($lockKey);

            return response()->json([
                'error' => $left > 0
                    ? "Email ou mot de passe incorrect ({$left} essai".($left > 1 ? 's' : '').' restant'.($left > 1 ? 's' : '').' avant blocage de 24 h)'
                    : 'Email ou mot de passe incorrect. Connexion bloquée pendant 24 h.',
            ], 401);
        }

        RateLimiter::clear($lockKey);

        $user = [
            'id' => (int) $dbUser->id,
            'name' => $dbUser->name,
            'email' => $dbUser->email,
            'role' => $dbUser->role,
            'phone' => $dbUser->phone,
        ];

        $token = Jwt::encode($user, config('ecopower.jwt_secret'), config('ecopower.jwt_ttl'));

        return response()->json(['message' => 'Connexion réussie', 'token' => $token, 'user' => $user]);
    }

    public function me(Request $request)
    {
        $jwtUser = $request->attributes->get('jwt_user');
        $row = DB::table('users')
            ->select('id', 'name', 'email', 'role', 'phone', 'created_at')
            ->where('id', $jwtUser['id'] ?? 0)
            ->first();

        if (! $row) {
            return response()->json(['error' => 'Utilisateur introuvable'], 404);
        }

        return response()->json(['user' => Format::row($row)]);
    }
}
