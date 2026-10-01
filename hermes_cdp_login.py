"""Credential-safe Hermes login automation over localhost CDP.

No page JavaScript is executed. The worker only uses CDP DOM/Input/Page commands,
never reads cookies, storage, passwords from the page, or raw HTTP bodies.
"""
from __future__ import annotations

import inspect
import json
import time
from urllib.parse import urlsplit, urlunsplit
from urllib.request import build_opener, ProxyHandler, Request

from hermes_credentials import (
    clear_login_guard,
    load_credentials,
    login_guard_status,
    record_login_failure,
)

LOGIN_HOST = "fr06-cloud.vocalcom.com"
SUPERVISION_HOST = "fr06-supervision.vocalcom.com"
DIRECT_SUPERVISION_URL = (
    "https://fr06-supervision.vocalcom.com/hermes360/Supervision/Login.aspx?"
    "Id_Admin=1&Culture_inf=fr-FR&Oid_Company=hzKSeX0K&Oid_Network=&"
    "Oid_Network_Agent=WAN&Station=&Phone=&COLOR=LIGHT&Tz=Romance%20Standard%20Time"
)


class LoginError(RuntimeError):
    pass


def _targets(port: int) -> list[dict]:
    opener = build_opener(ProxyHandler({}))
    req = Request(f"http://127.0.0.1:{int(port)}/json/list", headers={"Accept": "application/json"})
    try:
        with opener.open(req, timeout=3) as response:
            raw = response.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024:
            raise LoginError("Liste CDP trop volumineuse.")
        items = json.loads(raw)
    except LoginError:
        raise
    except Exception as exc:
        raise LoginError("Le port CDP local ne repond pas.") from exc
    result = []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict) or item.get("type") != "page":
            continue
        page = urlsplit(str(item.get("url") or ""))
        if page.scheme not in {"http", "https"} or page.hostname not in {LOGIN_HOST, SUPERVISION_HOST}:
            continue
        ws = urlsplit(str(item.get("webSocketDebuggerUrl") or ""))
        if ws.scheme != "ws" or ws.hostname not in {"127.0.0.1", "localhost", "::1"} or ws.port != int(port):
            continue
        result.append({
            "id": str(item.get("id") or "")[:160],
            "host": page.hostname,
            "url": urlunsplit((page.scheme, page.netloc, page.path, page.query, "")),
            "websocket": urlunsplit(("ws", f"127.0.0.1:{int(port)}", ws.path, "", "")),
        })
    return result


def _find_target(port: int, host: str) -> dict | None:
    for item in _targets(port):
        if item["host"] == host:
            return item
    return None


def _wait_target(port: int, hosts: set[str], timeout: float) -> dict | None:
    end = time.time() + float(timeout)
    while time.time() < end:
        try:
            for item in _targets(port):
                if item["host"] in hosts:
                    return item
        except LoginError:
            pass
        time.sleep(0.5)
    return None


class Cdp:
    def __init__(self, websocket_url: str):
        self.websocket_url = websocket_url
        self.socket = None
        self.next_id = 0

    def __enter__(self):
        try:
            from websockets.sync.client import connect
        except ImportError as exc:
            raise LoginError("Module websockets absent pour l'auto-login Hermes.") from exc
        options = dict(open_timeout=3, close_timeout=1, max_size=2 * 1024 * 1024, compression=None)
        if "proxy" in inspect.signature(connect).parameters:
            options["proxy"] = None
        try:
            self.socket = connect(self.websocket_url, **options)
        except Exception as exc:
            raise LoginError("Connexion CDP a la page Hermes impossible.") from exc
        return self

    def __exit__(self, *_):
        if self.socket:
            try:
                self.socket.close()
            except Exception:
                pass
            self.socket = None

    def call(self, method: str, params: dict | None = None, timeout: float = 5.0) -> dict:
        self.next_id += 1
        ident = self.next_id
        self.socket.send(json.dumps({"id": ident, "method": method, "params": params or {}}))
        end = time.time() + timeout
        while time.time() < end:
            try:
                raw = self.socket.recv(timeout=max(0.1, min(1.0, end - time.time())))
            except TimeoutError:
                continue
            except Exception as exc:
                raise LoginError(f"CDP interrompu pendant {method}.") from exc
            try:
                message = json.loads(raw)
            except (TypeError, ValueError):
                continue
            if message.get("id") != ident:
                continue
            if message.get("error"):
                raise LoginError(f"Commande CDP refusee: {method}.")
            return message.get("result") or {}
        raise LoginError(f"Delai CDP depasse: {method}.")


def _visible_node(cdp: Cdp, root_id: int, selectors: list[str]) -> int:
    for selector in selectors:
        try:
            node_id = int(cdp.call("DOM.querySelector", {"nodeId": root_id, "selector": selector}).get("nodeId") or 0)
            if not node_id:
                continue
            cdp.call("DOM.getBoxModel", {"nodeId": node_id})
            return node_id
        except LoginError:
            continue
    return 0


def _replace_text(cdp: Cdp, node_id: int, text: str) -> None:
    cdp.call("DOM.focus", {"nodeId": node_id})
    cdp.call("Input.dispatchKeyEvent", {"type": "keyDown", "key": "a", "code": "KeyA", "windowsVirtualKeyCode": 65, "modifiers": 2})
    cdp.call("Input.dispatchKeyEvent", {"type": "keyUp", "key": "a", "code": "KeyA", "windowsVirtualKeyCode": 65, "modifiers": 2})
    cdp.call("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Backspace", "code": "Backspace", "windowsVirtualKeyCode": 8})
    cdp.call("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Backspace", "code": "Backspace", "windowsVirtualKeyCode": 8})
    cdp.call("Input.insertText", {"text": text})


def _click_node(cdp: Cdp, node_id: int) -> None:
    model = cdp.call("DOM.getBoxModel", {"nodeId": node_id}).get("model") or {}
    quad = model.get("content") or model.get("border") or []
    if len(quad) < 8:
        raise LoginError("Bouton Hermes non cliquable.")
    xs = quad[0::2]
    ys = quad[1::2]
    x = sum(xs) / len(xs)
    y = sum(ys) / len(ys)
    cdp.call("Input.dispatchMouseEvent", {"type": "mousePressed", "x": x, "y": y, "button": "left", "clickCount": 1})
    cdp.call("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": x, "y": y, "button": "left", "clickCount": 1})


def _login_form(target: dict, username: str, password: str) -> None:
    with Cdp(target["websocket"]) as cdp:
        cdp.call("DOM.enable")
        root = int((cdp.call("DOM.getDocument", {"depth": 2, "pierce": True}).get("root") or {}).get("nodeId") or 0)
        if not root:
            raise LoginError("DOM Hermes indisponible.")
        user_selectors = [
            'input[name="username"]', 'input[name="login"]', 'input[name="user"]',
            'input[id*="username" i]', 'input[id*="login" i]', 'input[autocomplete="username"]',
            'input[type="text"]',
        ]
        password_selectors = [
            'input[name="password"]', 'input[id*="password" i]',
            'input[autocomplete="current-password"]', 'input[type="password"]',
        ]
        submit_selectors = [
            'button[type="submit"]', 'input[type="submit"]',
            'button[id*="login" i]', 'button[class*="login" i]',
        ]
        user_node = _visible_node(cdp, root, user_selectors)
        password_node = _visible_node(cdp, root, password_selectors)
        if not user_node:
            raise LoginError("Champ utilisateur Hermes introuvable.")
        if not password_node:
            raise LoginError("Champ mot de passe Hermes introuvable.")
        _replace_text(cdp, user_node, username)
        _replace_text(cdp, password_node, password)
        submit_node = _visible_node(cdp, root, submit_selectors)
        if submit_node:
            _click_node(cdp, submit_node)
        else:
            cdp.call("DOM.focus", {"nodeId": password_node})
            cdp.call("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13})
            cdp.call("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13})


def _navigate(target: dict, url: str) -> None:
    with Cdp(target["websocket"]) as cdp:
        cdp.call("Page.enable")
        cdp.call("Page.navigate", {"url": url})


def auto_login(port: int = 9222, *, wait_seconds: float = 45.0) -> dict:
    guard = login_guard_status()
    if guard["blocked"]:
        return {"ok": False, "state": "cooldown", "message": "Auto-login Hermes temporairement suspendu apres un echec."}
    credentials = load_credentials()
    if not credentials.get("auto_login"):
        return {"ok": False, "state": "disabled", "message": "Auto-login Hermes desactive."}
    username = credentials["username"]
    password = credentials["password"]
    try:
        # Existing authenticated supervision always wins; no credential is used.
        supervision = _find_target(port, SUPERVISION_HOST)
        login = _find_target(port, LOGIN_HOST)
        if supervision:
            clear_login_guard()
            return {"ok": True, "state": "supervision_ready", "message": "Session Hermes deja disponible."}

        target = login or _wait_target(port, {LOGIN_HOST, SUPERVISION_HOST}, min(wait_seconds, 20.0))
        if target and target["host"] == SUPERVISION_HOST:
            clear_login_guard()
            return {"ok": True, "state": "supervision_ready", "message": "Supervision Hermes disponible."}
        if not target:
            raise LoginError("Page de connexion Hermes introuvable apres ouverture d'Edge.")
        if "/dashboard" in target.get("url", "").lower():
            _navigate(target, DIRECT_SUPERVISION_URL)
            supervision = _wait_target(port, {SUPERVISION_HOST}, 30.0)
            if supervision:
                clear_login_guard()
                return {"ok": True, "state": "supervision_ready", "message": "Session Hermes existante reutilisee."}
            raise LoginError("Dashboard Hermes disponible mais Supervision ne s'est pas ouverte.")

        _login_form(target, username, password)
        deadline = time.time() + float(wait_seconds)
        navigated = False
        while time.time() < deadline:
            supervision = _find_target(port, SUPERVISION_HOST)
            if supervision:
                clear_login_guard()
                return {"ok": True, "state": "supervision_ready", "message": "Connexion Hermes automatique reussie."}
            cloud = _find_target(port, LOGIN_HOST)
            if cloud and "/dashboard" in cloud.get("url", "").lower() and not navigated:
                _navigate(cloud, DIRECT_SUPERVISION_URL)
                navigated = True
            time.sleep(0.5)

        raise LoginError("Hermes n'a pas confirme la connexion automatique.")
    except Exception as exc:
        reason = str(exc)[:300]
        record_login_failure(reason)
        return {"ok": False, "state": "login_failed", "message": reason}
    finally:
        # Drop the only Python references as soon as the CDP sequence is over.
        username = None
        password = None
        credentials = None
