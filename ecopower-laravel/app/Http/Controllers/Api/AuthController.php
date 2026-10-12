<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use App\Support\Format;
use App\Support\Jwt;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;

class AuthController extends Controller
{
    public function login(Request $request)
    {
        $email = $request->input('email');
        $password = $request->input('password');
        if (! $email || ! $password) {
            return response()->json(['error' => 'Email et mot de passe requis'], 400);
        }

        $dbUser = DB::table('users')->where('email', strtolower(trim((string) $email)))->first();

        // password_verify accepte les hash $2a$/$2b$ produits par bcryptjs.
        if (! $dbUser || ! password_verify((string) $password, $dbUser->password) || $dbUser->role !== 'admin') {
            return response()->json(['error' => 'Email ou mot de passe incorrect'], 401);
        }

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
