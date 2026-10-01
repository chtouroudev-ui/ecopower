from error_log import log_unexpected_error
import app_config as cfg
import functools
import ipaddress
import re
import db_compat as sqlite3
import threading

SITE_VALUES = cfg.SITE_VALUES
CLASSIFICATION_LOCK = threading.RLock()
SITE_POLICY_CACHE = {"DC1": "SUR SITE", "DC2": "TELETRAVAIL", "*": "INCONNU"}
SITE_RULE_CACHE = []

def normalize_user_key(value):
    value = str(value or "").strip()
    if not value:
        return ""
    if "\\" in value:
        value = value.rsplit("\\", 1)[-1]
    if "/" in value:
        value = value.rsplit("/", 1)[-1]
    if "@" in value:
        value = value.split("@", 1)[0]
    return value.strip().upper()

@functools.lru_cache(maxsize=512)
def parse_ip_selector(text):
    """Parse an IP selector: exact IP, CIDR, or explicit start-end range."""
    raw = str(text or "").strip().replace("–", "-").replace("—", "-")
    if not raw:
        raise ValueError("Plage IP vide")

    # Explicit range: 192.168.100.20-192.168.100.80 or 192.168.100.20..192.168.100.80
    if ".." in raw:
        parts = raw.split("..", 1)
    elif "-" in raw:
        parts = raw.split("-", 1)
    else:
        parts = None

    if parts is not None:
        start_text, end_text = (x.strip() for x in parts)
        if not start_text or not end_text:
            raise ValueError("Intervalle IP incomplet")
        start = ipaddress.ip_address(start_text)
        # Raccourci IPv4 pratique : 192.168.100.20-80
        if start.version == 4 and re.fullmatch(r"\d{1,3}", end_text):
            last_octet = int(end_text)
            if not 0 <= last_octet <= 255:
                raise ValueError("Dernier octet de fin invalide")
            prefix = start_text.rsplit(".", 1)[0]
            end_text = f"{prefix}.{last_octet}"
        end = ipaddress.ip_address(end_text)
        if start.version != end.version:
            raise ValueError("Les deux adresses doivent être de la même version IP")
        if int(start) > int(end):
            raise ValueError("L'adresse de début doit être inférieure ou égale à l'adresse de fin")
        return {
            "kind": "range",
            "version": start.version,
            "start": int(start),
            "end": int(end),
            "normalized": f"{start}-{end}",
        }

    # CIDR or exact IP. Exact IP is normalized to /32 or /128 for rule storage.
    if "/" in raw:
        net = ipaddress.ip_network(raw, strict=False)
    else:
        ip_obj = ipaddress.ip_address(raw)
        net = ipaddress.ip_network(f"{ip_obj}/{ip_obj.max_prefixlen}", strict=False)
    return {
        "kind": "network",
        "version": net.version,
        "network": net,
        "normalized": str(net),
    }

def selector_contains(selector, ip_obj):
    if selector is None or ip_obj is None:
        return False
    if selector["version"] != ip_obj.version:
        return False
    if selector["kind"] == "range":
        value = int(ip_obj)
        return selector["start"] <= value <= selector["end"]
    return ip_obj in selector["network"]

def ip_matches_selector(ip_value, selector_text):
    try:
        ip_obj = ipaddress.ip_address(str(ip_value or "").strip())
        selector = parse_ip_selector(str(selector_text or "").strip())
        return 1 if selector_contains(selector, ip_obj) else 0
    except Exception:
        return 0

def classify_site_details(collector, ip_value, gateway_value=""):
    collector = str(collector or "").strip().upper() or "*"
    ip_text = str(ip_value or "").strip()
    gateway_text = str(gateway_value or "").strip()
    try:
        ip_obj = ipaddress.ip_address(ip_text) if ip_text else None
    except ValueError:
        ip_obj = None
    try:
        gateway_obj = ipaddress.ip_address(gateway_text) if gateway_text else None
    except ValueError:
        gateway_obj = None
    with CLASSIFICATION_LOCK:
        rules = list(SITE_RULE_CACHE)
        policies = dict(SITE_POLICY_CACHE)
    if ip_obj is not None:
        for rule in rules:
            if rule["collector"] not in {collector, "*"}:
                continue
            try:
                if not selector_contains(rule["network_selector"], ip_obj):
                    continue
                gateway_selector = rule.get("gateway_network_selector")
                if gateway_selector is not None:
                    if gateway_obj is None or not selector_contains(gateway_selector, gateway_obj):
                        continue
                reason_parts = [rule["label"] or rule["network"]]
                if rule.get("gateway_network"):
                    reason_parts.append(f"GW {rule['gateway_network']}")
                return {
                    "site": rule["result_site"],
                    "reason": " · ".join(reason_parts),
                    "rule_id": rule["id"],
                    "matched": True,
                }
            except Exception:
                log_unexpected_error('app.classify_site_details.L208')
                continue
    site = policies.get(collector, policies.get("*", "INCONNU"))
    return {
        "site": site if site in SITE_VALUES else "INCONNU",
        "reason": f"Défaut {collector}" if collector != "*" else "Collecteur inconnu",
        "rule_id": None,
        "matched": False,
    }

def classify_site_value(collector, ip_value, gateway_value=""):
    return classify_site_details(collector, ip_value, gateway_value)["site"]

def classify_site_reason(collector, ip_value, gateway_value=""):
    return classify_site_details(collector, ip_value, gateway_value)["reason"]

def refresh_classification_cache():
    global SITE_POLICY_CACHE, SITE_RULE_CACHE
    policies = {"DC1": "SUR SITE", "DC2": "TELETRAVAIL", "*": "INCONNU"}
    rules = []
    try:
        con = sqlite3.connect(cfg.APP_DB, timeout=10)
        con.row_factory = sqlite3.Row
        if con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='site_policies'").fetchone():
            for row in con.execute("SELECT collector,default_site FROM site_policies"):
                if row["default_site"] in SITE_VALUES:
                    policies[str(row["collector"]).strip().upper()] = row["default_site"]
        if con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='site_rules'").fetchone():
            for row in con.execute("SELECT id,collector,network,gateway_network,result_site,label,priority FROM site_rules WHERE enabled=1 ORDER BY priority DESC,id ASC"):
                try:
                    network_selector = parse_ip_selector(str(row["network"]).strip())
                except ValueError:
                    log_unexpected_error('app.refresh_classification_cache.L242')
                    continue
                if row["result_site"] not in SITE_VALUES:
                    continue
                gateway_network = str(row["gateway_network"] or "").strip()
                gateway_selector = None
                if gateway_network:
                    try:
                        gateway_selector = parse_ip_selector(gateway_network)
                        gateway_network = gateway_selector["normalized"]
                    except ValueError:
                        log_unexpected_error('app.refresh_classification_cache.L252')
                        continue
                rules.append({
                    "id": row["id"],
                    "collector": str(row["collector"] or "*").strip().upper() or "*",
                    "network": network_selector["normalized"],
                    "network_selector": network_selector,
                    "gateway_network": gateway_network,
                    "gateway_network_selector": gateway_selector,
                    "result_site": row["result_site"],
                    "label": str(row["label"] or ""),
                    "priority": int(row["priority"] or 0),
                })
        con.close()
    except Exception:
        log_unexpected_error('app.refresh_classification_cache.L266')
        pass
    with CLASSIFICATION_LOCK:
        SITE_POLICY_CACHE = policies
        SITE_RULE_CACHE = rules
