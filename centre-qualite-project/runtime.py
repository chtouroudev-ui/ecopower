import errno
import ipaddress
import os
import socket
import ssl
import threading
import time

import app_config as cfg
from app_db import get_setting
from diagnostic_import import import_diagnostic_source
from error_log import log_unexpected_error

ACTIVE_HOST = cfg.DEFAULT_HOST
ACTIVE_PORT = cfg.DEFAULT_PORT
AUTO_IMPORT_STOP = threading.Event()

def validate_host(value):
    value = str(value or "").strip()
    try:
        ipaddress.ip_address(value)
        return value
    except ValueError:
        raise ValueError("IP d'écoute invalide. Exemples : 127.0.0.1, 192.168.100.77 ou 0.0.0.0")

def local_lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return ""

def auto_import_loop():
    last_attempt = 0.0
    while not AUTO_IMPORT_STOP.wait(20):
        try:
            if get_setting("auto_import_enabled", "0") != "1":
                continue
            source = get_setting("diagnostic_source_path", "").strip()
            if not source:
                continue
            try:
                minutes = max(1, min(1440, int(get_setting("auto_import_minutes", "5"))))
            except Exception:
                log_unexpected_error('app.auto_import_loop.L2455')
                minutes = 5
            now_mono = time.monotonic()
            if last_attempt and (now_mono - last_attempt) < minutes * 60:
                continue
            last_attempt = now_mono
            try:
                result = import_diagnostic_source(source, "AUTO_IMPORT")
                if result["imported_rows"]:
                    print(f"Import auto : {result['imported_rows']} nouveau(x) diagnostic(s)")
            except Exception as exc:
                log_unexpected_error('app.auto_import_loop.L2465')
                print("Import auto échoué :", exc)
        except Exception as exc:
            log_unexpected_error('app.auto_import_loop.L2467')
            print("Boucle import auto :", exc)

def create_server(host, port):
    from production_http import Handler, ProductionHTTPServer as ThreadingHTTPServer

    # The HTTPS production layout uses Caddy on 9050 and a backend fixed on
    # 127.0.0.1:9051. Falling back silently to 5050-5100 leaves Caddy pointing
    # at an empty 9051 socket and produces misleading HTTP 502/MIME errors in
    # the browser. In reverse-proxy mode the backend port therefore stays
    # strict and startup fails clearly if 9051 is unavailable.
    strict_env = os.environ.get("TECHIN_STRICT_PORT", "").strip().lower()
    strict_port = strict_env in {"1", "true", "yes", "on"}
    strict_port = strict_port or (host in {"127.0.0.1", "::1"} and int(port) == 9051)
    ports = [port] if strict_port else [port] + [p for p in cfg.FALLBACK_PORTS if p != port]

    last_error = None
    for candidate in ports:
        try:
            return ThreadingHTTPServer((host, candidate), Handler), candidate
        except OSError as exc:
            last_error = exc
            winerror = getattr(exc, "winerror", None)
            if winerror in (10013, 10048) or exc.errno in (errno.EACCES, errno.EADDRINUSE):
                if strict_port:
                    raise RuntimeError(
                        f"Port backend {host}:{port} indisponible. "
                        "En mode HTTPS 9050/9051, Nelyio ne change plus de port automatiquement. "
                        "Fermez l'ancien processus qui utilise 9051 puis relancez le backend/Caddy."
                    ) from exc
                continue
            raise
    raise RuntimeError(f"Aucun port disponible. Dernière erreur : {last_error}")

def configured_network():
    host = os.environ.get("TECHIN_HOST", get_setting("web_host", cfg.DEFAULT_HOST)).strip() or cfg.DEFAULT_HOST
    try:
        host = validate_host(host)
    except Exception:
        log_unexpected_error('app.configured_network.L2490')
        host = cfg.DEFAULT_HOST
    try:
        port = int(os.environ.get("TECHIN_PORT", get_setting("web_port", str(cfg.DEFAULT_PORT))))
        if not (1 <= port <= 65535):
            port = cfg.DEFAULT_PORT
    except Exception:
        log_unexpected_error('app.configured_network.L2496')
        port = cfg.DEFAULT_PORT
    return host, port

def configured_tls():
    enabled = os.environ.get("TECHIN_TLS", get_setting("tls_enabled", "0")).strip().lower() in {"1","true","yes","on"}
    cert_path = os.environ.get("TECHIN_TLS_CERT", get_setting("tls_cert_path", "")).strip().strip('"')
    key_path = os.environ.get("TECHIN_TLS_KEY", get_setting("tls_key_path", "")).strip().strip('"')
    return enabled, cert_path, key_path

def enable_direct_tls(server, cert_path, key_path):
    if not os.path.isfile(cert_path):
        raise FileNotFoundError(f"Certificat TLS introuvable : {cert_path}")
    if not os.path.isfile(key_path):
        raise FileNotFoundError(f"Clé privée TLS introuvable : {key_path}")
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    try:
        ctx.maximum_version = ssl.TLSVersion.TLSv1_3
    except Exception:
        pass
    ctx.load_cert_chain(certfile=cert_path, keyfile=key_path)
    server.socket = ctx.wrap_socket(server.socket, server_side=True)
    server.techin_https = True
