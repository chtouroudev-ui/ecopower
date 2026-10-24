<?php

namespace App\Support;

/**
 * JWT HS256 minimal, compatible avec les jetons émis par l'ancien serveur Express (jsonwebtoken).
 */
class Jwt
{
    public static function encode(array $payload, string $secret, int $ttlSeconds): string
    {
        $now = time();
        $payload['iat'] = $now;
        $payload['exp'] = $now + $ttlSeconds;

        $header = self::b64(json_encode(['alg' => 'HS256', 'typ' => 'JWT']));
        $body = self::b64(json_encode($payload, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES));
        $signature = self::b64(hash_hmac('sha256', "$header.$body", $secret, true));

        return "$header.$body.$signature";
    }

    /** Retourne le payload, ou null si le jeton est invalide ou expiré. */
    public static function decode(string $token, string $secret): ?array
    {
        $parts = explode('.', $token);
        if (count($parts) !== 3) {
            return null;
        }
        [$header, $body, $signature] = $parts;

        $head = json_decode(self::unb64($header), true);
        if (($head['alg'] ?? null) !== 'HS256') {
            return null;
        }

        $expected = self::b64(hash_hmac('sha256', "$header.$body", $secret, true));
        if (! hash_equals($expected, $signature)) {
            return null;
        }

        $payload = json_decode(self::unb64($body), true);
        if (! is_array($payload) || (isset($payload['exp']) && time() >= $payload['exp'])) {
            return null;
        }

        return $payload;
    }

    private static function b64(string $data): string
    {
        return rtrim(strtr(base64_encode($data), '+/', '-_'), '=');
    }

    private static function unb64(string $data): string
    {
        return (string) base64_decode(strtr($data, '-_', '+/'));
    }
}
