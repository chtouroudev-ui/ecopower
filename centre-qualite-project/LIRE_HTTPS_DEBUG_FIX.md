# Nelyio RC2K - HTTPS DEBUG FIX

## Correction
`START_NELYIO_HTTPS_DEBUG.bat` n'utilise plus `-NoBrowser`.

Le backend reste volontairement sur `http://127.0.0.1:9051` en interne.
Caddy expose ensuite Nelyio en HTTPS sur le port 9050.
Une fois HTTPS valide, le navigateur est ouvert sur :

- `https://stock-manager.nelyio.local:9050/` si le nom DNS/certificat est valide ;
- sinon `https://localhost:9050/`.

Aucune logique applicative, base de donnees ou configuration Caddy n'est modifiee.
