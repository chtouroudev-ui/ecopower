import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from error_log import log_unexpected_error
import asyncio
import json
import os
import re
import shutil
import stat
import threading
import sqlite3
import time
import queue
from pathlib import Path
from datetime import datetime
from collections import deque, defaultdict
import tkinter as tk
from tkinter import scrolledtext, filedialog

import urllib.request
import websockets

# =========================
# CONFIG
# =========================

DEBUG_URL = "http://127.0.0.1:9222/json"
HERMES_KEYWORD = "hermes_net_v5/Supervision"
TARGET_REQUEST = "changes.ashx"

LOG_DIR = Path(r"C:\Logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)

GENERAL_FILE = LOG_DIR / "hermes_general.txt"
RAW_FILE = LOG_DIR / "hermes_raw_changes.txt"
CALLS_FILE = LOG_DIR / "appels_blancs.txt"
CONNEXION_FILE = LOG_DIR / "deconnexions_reconnexions.txt"
STATS_FILE = LOG_DIR / "stats_agents.txt"
ERROR_FILE = LOG_DIR / "erreurs_capture.txt"
SUMMARY_FILE = LOG_DIR / "resume_diagnostic.txt"

# Mode stable: la capture ecrit dans SQLite en priorite.
# Les TXT sont desactives pour eviter les blocages Windows Permission denied.
DB_FILE = LOG_DIR / "hermes_supervision.db"
SQLITE_ENABLED = True
WRITE_TEXT_LOGS = False  # SQLite only: TXT désactivés pour éviter les perturbations capture
ENABLE_RAW_LOG = False   # RAW désactivé par défaut pour stabilité

WHITE_CALL_LIMIT_SECONDS = 15

# Watchdog: relance la capture si aucun log utile ne revient pendant X secondes
# 15s etait trop court : si Edge purge le buffer DevTools avant que
# Network.getResponseBody soit appele (cf NETWORK_BUFFER plus bas), on perd
# des reponses meme quand Hermes envoie bien changes.ashx chaque seconde.
# On laisse une marge confortable au watchdog, le vrai correctif etant le
# buffer DevTools agrandi + la detection d'erreur getResponseBody ci-dessous.
WATCHDOG_NO_LOG_SECONDS = 60
WATCHDOG_CHECK_EVERY_MS = 2000
RESTART_DELAY_MS = 2000

# Taille du buffer DevTools (CDP) pour conserver les corps de reponse reseau.
# Par defaut Edge/Chrome utilise une taille modeste qui peut etre depassee si
# Hermes genere beaucoup de requetes par seconde sur une longue session : les
# plus anciennes reponses sont alors evincees avant que getResponseBody soit
# appele, ce qui les fait disparaitre silencieusement (corps vide).
NETWORK_MAX_RESOURCE_BUFFER = 100 * 1024 * 1024   # par ressource
NETWORK_MAX_TOTAL_BUFFER = 200 * 1024 * 1024       # buffer global

# =========================
# MEMORY
# =========================

agents = {}
calls = {}
active_calls = {}
agent_history = {}
last_micro_state = {}
last_event_cache = set()

stats = defaultdict(lambda: {
    "deconnexions": 0,
    "reconnexions": 0,
    "deconnexions_en_appel": 0,
    "appels_blancs": 0,
    "transferts": 0,
    "micro_erreurs": 0,
    "temps_deconnecte_seconds": 0,
    "last_deconnexion_at": None
})

capture_thread = None
stop_event = threading.Event()
schedule_job = None
ui_pump_job = None

# Variables protegees par un lock pour eviter les conflits entre Tkinter et le thread capture
state_lock = threading.Lock()
last_useful_log_at = None
capture_started_at = None
restart_in_progress = False
file_lock = threading.Lock()
db_lock = threading.Lock()

# File d'attente thread-safe : le thread de capture pousse des lignes ici,
# Tkinter (thread principal) les consomme via process_ui_queue(). Cela evite
# tout appel direct a root.after()/output_box depuis le thread de capture,
# qui peut se bloquer si l'UI est occupee et donc geler la capture.
ui_queue = queue.Queue()
UI_QUEUE_DRAIN_MAX = 200  # securite anti-blocage si gros backlog


# =========================
# SQLITE STORAGE
# =========================

def init_db():
    if not SQLITE_ENABLED:
        return
    try:
        with sqlite3.connect(DB_FILE, timeout=30) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA busy_timeout=30000")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS log_lines (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts TEXT NOT NULL,
                    category TEXT NOT NULL,
                    line TEXT NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_log_lines_ts ON log_lines(ts)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_log_lines_category_ts ON log_lines(category, ts)")
            conn.commit()
    except Exception as e:
        log_unexpected_error('capture.Capture_NELYIO.init_db.L132')
        print(f"ERREUR_SQLITE_INIT | {e}")



# NELYIO: confirms Hermès responses, independent of agent state changes.
_nelyio_last_heartbeat = 0.0

def nelyio_heartbeat():
    global _nelyio_last_heartbeat
    current = time.monotonic()
    if current - _nelyio_last_heartbeat < 5:
        return
    _nelyio_last_heartbeat = current
    try:
        line = datetime.now().astimezone().isoformat(timespec="seconds") + " | NELYIO_HEARTBEAT"
        write_to_sqlite(GENERAL_FILE, line)
    except Exception as exc:
        log_unexpected_error('capture.Capture_NELYIO.nelyio_heartbeat.L149')
        print("NELYIO_HEARTBEAT_ERROR", exc)

def log_category_from_path(path):
    if path == GENERAL_FILE:
        return "general"
    if path == CALLS_FILE:
        return "appels_blancs"
    if path == CONNEXION_FILE:
        return "deconnexions"
    if path == STATS_FILE:
        return "stats"
    if path == ERROR_FILE:
        return "erreurs"
    if path == RAW_FILE:
        return "raw"
    if path == SUMMARY_FILE:
        return "resume"
    return "autre"


def write_to_sqlite(path, line):
    if not SQLITE_ENABLED:
        return
    category = log_category_from_path(path)
    ts = datetime.now().astimezone().isoformat(timespec="seconds")  # NELYIO: explicit timezone in SQLite; original text format unchanged
    for attempt in range(5):
        try:
            with db_lock:
                with sqlite3.connect(DB_FILE, timeout=30) as conn:
                    conn.execute("PRAGMA busy_timeout=30000")
                    conn.execute(
                        "INSERT INTO log_lines(ts, category, line) VALUES (?, ?, ?)",
                        (ts, category, line)
                    )
                    conn.commit()
            return
        except sqlite3.OperationalError as e:
            if "locked" in str(e).lower() and attempt < 4:
                time.sleep(0.1 * (attempt + 1))
                continue
            log_unexpected_error('capture.Capture_NELYIO.write_to_sqlite.L186')
            print(f"ERREUR_SQLITE_WRITE | {category} | {e}")
            return
        except Exception as e:
            log_unexpected_error('capture.Capture_NELYIO.write_to_sqlite.L192')
            print(f"ERREUR_SQLITE_WRITE | {category} | {e}")
            return


# =========================
# FILES / LOGGING
# =========================

def set_readonly(path):
    try:
        if path.exists():
            os.chmod(path, stat.S_IREAD)
    except Exception:
        pass


def set_writable(path):
    try:
        if path.exists():
            os.chmod(path, stat.S_IWRITE)
    except Exception:
        pass


def init_files():
    init_db()
    if not WRITE_TEXT_LOGS:
        return
    for path in [
        GENERAL_FILE,
        RAW_FILE,
        CALLS_FILE,
        CONNEXION_FILE,
        STATS_FILE,
        ERROR_FILE,
        SUMMARY_FILE,
    ]:
        if not path.exists():
            path.touch()


def write_to_file(path, line):
    # SQLite est le stockage principal. TXT reste optionnel pour compatibilité.
    write_to_sqlite(path, line)

    if not WRITE_TEXT_LOGS:
        return

    for attempt in range(5):
        try:
            with file_lock:
                with open(path, "a", encoding="utf-8", buffering=1) as f:
                    f.write(line + "\n")
            return
        except PermissionError:
            if attempt == 4: log_unexpected_error('capture.Capture_NELYIO.write_to_file.L247')
            time.sleep(0.1 * (attempt + 1))
        except Exception as e:
            log_unexpected_error('capture.Capture_NELYIO.write_to_file.L249')
            print(f"ERREUR_WRITE_FILE | {path} | {e}")
            return

    print(f"ERREUR_WRITE_FILE | {path} | Permission denied après 5 tentatives")


def log_line(path, message):
    line = f"{datetime.now():%Y-%m-%d %H:%M:%S} | {message}"
    write_to_file(path, line)
    return line


def write_ui(line):
    """
    Pousse la ligne dans une queue thread-safe au lieu de toucher Tkinter
    directement depuis le thread de capture. Non-bloquant : meme si l'UI
    est lente ou occupee, le thread de capture ne peut jamais se figer ici.
    """
    print(line)
    try:
        ui_queue.put_nowait(line)
    except Exception:
        pass


def process_ui_queue():
    """
    Tourne exclusivement sur le thread principal (Tkinter), planifie via
    root.after(). Draine la queue et met a jour l'affichage. Une limite par
    passage evite qu'un gros backlog ne bloque la boucle d'evenements.
    """
    global ui_pump_job
    try:
        drained = 0
        while drained < UI_QUEUE_DRAIN_MAX:
            try:
                item = ui_queue.get_nowait()
            except queue.Empty:
                break

            try:
                if isinstance(item, tuple) and len(item) == 2 and item[0] == "__LIVE_LABEL__":
                    live_label.config(text=item[1])
                else:
                    output_box.insert(tk.END, str(item) + "\n")
            except Exception:
                pass
            drained += 1

        if drained:
            try:
                total_lines = int(output_box.index('end-1c').split('.')[0])
                if total_lines > 800:
                    output_box.delete('1.0', f'{total_lines - 800}.0')
                output_box.see(tk.END)
            except Exception:
                pass
    finally:
        ui_pump_job = root.after(100, process_ui_queue)


def write_general(message):
    line = log_line(GENERAL_FILE, message)
    write_ui(line)


def write_error(message):
    line = log_line(ERROR_FILE, message)
    write_ui(line)


def write_call(message):
    log_line(CALLS_FILE, message)
    write_general(message)


def write_connexion(message):
    log_line(CONNEXION_FILE, message)
    write_general(message)


def write_stats(message):
    log_line(STATS_FILE, message)
    write_general(message)


def write_raw(body):
    if not ENABLE_RAW_LOG:
        return
    try:
        set_writable(RAW_FILE)
        with open(RAW_FILE, "a", encoding="utf-8") as f:
            f.write("\n\n===== RAW ")
            f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S}")
            f.write(" =====\n")
            f.write(body)
            f.write("\n")
        set_readonly(RAW_FILE)
    except Exception as e:
        write_error(f"ERREUR_RAW | {e}")


# =========================
# HELPERS
# =========================

def clean(value):
    if value is None:
        return ""

    value = str(value)
    value = re.sub(r"<.*?>", "", value)
    value = value.replace("&nbsp;", " ")
    value = value.replace("&amp;", "&")
    value = value.replace("\\'", "'")
    value = value.replace('\\"', '"')
    return value.strip()


def is_connected(state):
    return clean(state).lower() != "déconnecté"


def is_call_state(state):
    value = clean(state).lower()
    return "en ligne" in value or "appel" in value


def is_transfer_state(state):
    return "transfert" in clean(state).lower()


def is_micro_error(value):
    value = clean(value).lower()

    if not value:
        return False

    ok_words = ["ok", "aucun", "normal"]
    if any(ok in value for ok in ok_words):
        return False

    error_words = [
        "erreur",
        "error",
        "ko",
        "déconnecté",
        "deconnecte",
        "absent",
        "non détecté",
        "non detecte",
        "micro",
        "casque",
        "headset"
    ]

    return any(word in value for word in error_words)


def call_bucket(duration):
    if duration <= 10:
        return "<=10s"
    if duration <= 20:
        return "<=20s"
    return "<=15s"


def ensure_history(agent_id):
    if agent_id not in agent_history:
        agent_history[agent_id] = deque(maxlen=3)


def add_history(agent_id, state):
    ensure_history(agent_id)
    agent_history[agent_id].append(clean(state))


def get_history(agent_id):
    ensure_history(agent_id)
    values = list(agent_history[agent_id])

    while len(values) < 3:
        values.insert(0, "")

    return values[-3], values[-2], values[-1]


def split_js_args(args_text):
    """
    Split JS function arguments without breaking values inside quotes.
    Example:
      231,1027,-1,100,"En ligne (appel entrant)",1,537,"CLIENT","+33123"
    """
    args = []
    current = []
    in_quote = False
    escape = False

    for ch in args_text:
        if escape:
            current.append(ch)
            escape = False
            continue

        if ch == "\\":
            current.append(ch)
            escape = True
            continue

        if ch == '"':
            in_quote = not in_quote
            current.append(ch)
            continue

        if ch == "," and not in_quote:
            args.append("".join(current).strip())
            current = []
            continue

        current.append(ch)

    if current:
        args.append("".join(current).strip())

    cleaned = []
    for value in args:
        value = value.strip()
        if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
            value = value[1:-1]
        cleaned.append(clean(value))

    return cleaned


def extract_tstate_events(body):
    """
    Returns list of dicts extracted from UpAgtTState(...) calls.

    Known format from your RAW:
    UpAgtTState(
      231,
      1027,                       # index 1 agent_id
      -1,
      100,
      "En ligne (appel entrant)",  # index 4 state
      1,1,"","",1,
      537,                        # index 10 queue_id
      "CIM RADIONIORT",            # index 11 client / campagne
      "+33549326604",              # index 12 phone
      ...
    )
    """
    events = []

    for args_text in re.findall(r"UpAgtTState\((.*?)\);", body, flags=re.DOTALL):
        parts = split_js_args(args_text)

        if len(parts) < 5:
            continue

        agent_id = parts[1]
        state = parts[4]

        queue_id = parts[10] if len(parts) > 10 else ""
        client = parts[11] if len(parts) > 11 else ""
        phone = parts[12] if len(parts) > 12 else ""

        events.append({
            "agent_id": agent_id,
            "state": state,
            "queue_id": queue_id,
            "client": client,
            "phone": phone,
            "raw_args": parts,
        })

    return events


def remember_active_call(agent_id, state, queue_id="", client="", phone=""):
    active_calls[agent_id] = {
        "start": datetime.now(),
        "state": state,
        "queue_id": queue_id,
        "client": client,
        "phone": phone,
    }


def forget_active_call(agent_id):
    active_calls.pop(agent_id, None)


def get_active_call(agent_id):
    return active_calls.get(agent_id)


def event_key(kind, agent_id, extra=""):
    current_minute = datetime.now().strftime("%Y-%m-%d %H:%M")
    return f"{current_minute}|{kind}|{agent_id}|{extra}"


def write_dedup_connexion(kind, agent_id, message, extra=""):
    key = event_key(kind, agent_id, extra)
    if key in last_event_cache:
        return

    last_event_cache.add(key)

    if len(last_event_cache) > 5000:
        last_event_cache.clear()

    write_connexion(message)


# =========================
# PARSING
# =========================

def parse_micro_errors(body):
    patterns = [
        r'UpAgtMicro\(\d+,(\d+),.*?,"([^"]*)"',
        r'UpAgtHeadset\(\d+,(\d+),.*?,"([^"]*)"',
        r'UpAgtCasque\(\d+,(\d+),.*?,"([^"]*)"',
        r'UpAgtTHeadset\(\d+,(\d+),.*?,"([^"]*)"',
    ]

    for pattern in patterns:
        for agent_id, value in re.findall(pattern, body):
            value = clean(value)
            old_value = last_micro_state.get(agent_id)

            if old_value != value:
                last_micro_state[agent_id] = value

                if is_micro_error(value):
                    stats[agent_id]["micro_erreurs"] += 1
                    write_stats(f"MICRO_ERREUR | Agent {agent_id} | valeur={value}")


def process_response(body):
    parse_micro_errors(body)

    tstate_events = extract_tstate_events(body)

    for event in tstate_events:
        agent_id = event["agent_id"]
        new_state = event["state"]
        queue_id = event["queue_id"]
        client = event["client"]
        phone = event["phone"]
        now_dt = datetime.now()

        old_state = agents.get(agent_id)

        if old_state is None:
            agents[agent_id] = new_state
            add_history(agent_id, new_state)

            write_general(
                f"ETAT_INITIAL | Agent {agent_id} | {new_state} | "
                f"queue={queue_id} | client={client} | numero={phone}"
            )

            if is_transfer_state(new_state):
                stats[agent_id]["transferts"] += 1
                write_stats(f"TRANSFERT | Agent {agent_id} | état={new_state}")

            if is_call_state(new_state):
                calls[agent_id] = {
                    "start": now_dt,
                    "before": get_history(agent_id)
                }
                remember_active_call(agent_id, new_state, queue_id, client, phone)

            continue

        if old_state == new_state:
            # Same state, but client/phone may be updated while still in call.
            if is_call_state(new_state):
                remember_active_call(agent_id, new_state, queue_id, client, phone)
            continue

        old_connected = is_connected(old_state)
        new_connected = is_connected(new_state)

        old_in_call = is_call_state(old_state)
        new_in_call = is_call_state(new_state)

        write_general(
            f"ETAT | Agent {agent_id} | {old_state} -> {new_state} | "
            f"queue={queue_id} | client={client} | numero={phone}"
        )

        if is_transfer_state(new_state):
            stats[agent_id]["transferts"] += 1
            write_stats(f"TRANSFERT | Agent {agent_id} | {old_state} -> {new_state}")

        # Ces variables évitent qu'un même événement soit compté deux fois
        # comme APPEL_BLANC et DECONNEXION_EN_APPEL.
        deconnexion_already_logged = False
        skip_critical_disconnect = False

        # Appel commence
        if not old_in_call and new_in_call:
            calls[agent_id] = {
                "start": now_dt,
                "before": get_history(agent_id)
            }
            remember_active_call(agent_id, new_state, queue_id, client, phone)

        # Appel continue: update metadata client/phone
        elif old_in_call and new_in_call:
            remember_active_call(agent_id, new_state, queue_id, client, phone)

        # Appel termine
        elif old_in_call and not new_in_call:
            call_info = calls.pop(agent_id, None)
            call_meta = get_active_call(agent_id)
            forget_active_call(agent_id)

            if call_info:
                duration = int((now_dt - call_info["start"]).total_seconds())

                before_1, before_2, before_3 = call_info["before"]
                disconnected_after = "OUI" if not new_connected else "NON"

                meta_client = call_meta.get("client", "") if call_meta else client
                meta_phone = call_meta.get("phone", "") if call_meta else phone
                meta_queue = call_meta.get("queue_id", "") if call_meta else queue_id

                # Règle métier:
                # - <= 15s : appel blanc, même si l'état suivant est Déconnecté.
                # - > 15s + Déconnecté : déconnexion critique en appel.
                # - > 15s + non déconnecté : appel terminé normalement.
                if duration <= WHITE_CALL_LIMIT_SECONDS:
                    stats[agent_id]["appels_blancs"] += 1
                    skip_critical_disconnect = True

                    write_call(
                        f"APPEL_BLANC | Agent {agent_id} | "
                        f"fin={now_dt:%Y-%m-%d %H:%M:%S} | "
                        f"durée={duration}s | "
                        f"tranche={call_bucket(duration)} | "
                        f"queue={meta_queue} | "
                        f"client={meta_client} | "
                        f"numero={meta_phone} | "
                        f"avant_1={before_1} | "
                        f"avant_2={before_2} | "
                        f"avant_3={before_3} | "
                        f"état_appel={old_state} | "
                        f"état_après={new_state} | "
                        f"déconnecté_après_appel={disconnected_after}"
                    )

                elif not new_connected:
                    stats[agent_id]["deconnexions"] += 1
                    stats[agent_id]["deconnexions_en_appel"] += 1
                    stats[agent_id]["last_deconnexion_at"] = now_dt
                    deconnexion_already_logged = True

                    write_dedup_connexion(
                        "DECONNEXION_EN_APPEL",
                        agent_id,
                        f"DECONNEXION_EN_APPEL | Agent {agent_id} | "
                        f"dernier état={old_state} | "
                        f"durée_appel={duration}s | "
                        f"queue={meta_queue} | "
                        f"client={meta_client} | "
                        f"numero={meta_phone}",
                        extra=meta_phone
                    )

        # Déconnexion hors règle appel blanc / critique déjà traitée
        if old_connected and not new_connected and not deconnexion_already_logged:
            # Si c'est une coupure juste après un appel blanc <=15s, on ne la classe
            # pas comme déconnexion critique pour éviter le double comptage.
            if skip_critical_disconnect:
                pass
            else:
                stats[agent_id]["deconnexions"] += 1
                stats[agent_id]["last_deconnexion_at"] = now_dt

                call_meta = get_active_call(agent_id)

                if old_in_call or call_meta:
                    stats[agent_id]["deconnexions_en_appel"] += 1

                    meta_client = call_meta.get("client", "") if call_meta else client
                    meta_phone = call_meta.get("phone", "") if call_meta else phone
                    meta_queue = call_meta.get("queue_id", "") if call_meta else queue_id

                    write_dedup_connexion(
                        "DECONNEXION_EN_APPEL",
                        agent_id,
                        f"DECONNEXION_EN_APPEL | Agent {agent_id} | "
                        f"dernier état={old_state} | "
                        f"queue={meta_queue} | "
                        f"client={meta_client} | "
                        f"numero={meta_phone}",
                        extra=meta_phone
                    )
                else:
                    write_dedup_connexion(
                        "DECONNEXION",
                        agent_id,
                        f"DECONNEXION | Agent {agent_id} | dernier état={old_state}"
                    )

                forget_active_call(agent_id)

        # Reconnexion
        elif not old_connected and new_connected:
            stats[agent_id]["reconnexions"] += 1

            last_dt = stats[agent_id].get("last_deconnexion_at")
            if last_dt:
                offline_seconds = int((now_dt - last_dt).total_seconds())
                stats[agent_id]["temps_deconnecte_seconds"] += offline_seconds
                stats[agent_id]["last_deconnexion_at"] = None

            write_dedup_connexion(
                "RECONNEXION",
                agent_id,
                f"RECONNEXION | Agent {agent_id} | nouvel état={new_state}"
            )

        agents[agent_id] = new_state
        add_history(agent_id, new_state)

    update_live_labels()


# =========================
# WATCHDOG STATE
# =========================

def mark_capture_started():
    global capture_started_at, last_useful_log_at
    with state_lock:
        capture_started_at = datetime.now()
        last_useful_log_at = None


def mark_useful_log_received():
    global last_useful_log_at
    with state_lock:
        last_useful_log_at = datetime.now()


def get_seconds_without_useful_log():
    with state_lock:
        now_dt = datetime.now()
        if last_useful_log_at is not None:
            return int((now_dt - last_useful_log_at).total_seconds())
        if capture_started_at is not None:
            return int((now_dt - capture_started_at).total_seconds())
        return 0


def reset_restart_flag():
    global restart_in_progress
    with state_lock:
        restart_in_progress = False


def set_restart_flag_if_free():
    global restart_in_progress
    with state_lock:
        if restart_in_progress:
            return False
        restart_in_progress = True
        return True

# =========================
# DEVTOOLS CAPTURE
# =========================

def find_hermes_tab():
    try:
        request = urllib.request.Request(DEBUG_URL, headers={"Accept": "application/json"})
        with urllib.request.urlopen(request, timeout=5) as response:
            tabs = json.loads(response.read().decode("utf-8"))
        if not isinstance(tabs, list):
            raise ValueError("Reponse DevTools inattendue")
    except Exception as e:
        raise Exception(f"Impossible de joindre Edge DevTools sur {DEBUG_URL} | {e}")

    for tab in tabs:
        url = tab.get("url", "")
        if HERMES_KEYWORD.lower() in url.lower():
            return tab["webSocketDebuggerUrl"]

    raise Exception("Onglet Hermes introuvable. Ouvre Hermes dans Edge debug.")


async def capture_loop():
    ws_url = find_hermes_tab()
    write_general("INFO | Connecté à Hermes via DevTools")

    async with websockets.connect(ws_url, ping_interval=20, ping_timeout=10, close_timeout=5, max_queue=512) as ws:
        next_id = 1
        pending = {}
        tracked_request_ids = {}  # request_id -> heure de responseReceived, en attente de loadingFinished

        async def send(method, params=None):
            nonlocal next_id

            current = next_id
            await ws.send(json.dumps({
                "id": current,
                "method": method,
                "params": params or {},
            }))
            next_id += 1
            return current

        await send("Network.enable", {
            "maxResourceBufferSize": NETWORK_MAX_RESOURCE_BUFFER,
            "maxTotalBufferSize": NETWORK_MAX_TOTAL_BUFFER,
        })

        missed_body_count = 0
        last_missed_body_warning = datetime.now()

        while not stop_event.is_set():
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=1)
            except asyncio.TimeoutError:
                now_dt = datetime.now()
                for cmd_id, created_at in list(pending.items()):
                    if (now_dt - created_at).total_seconds() > 10:
                        pending.pop(cmd_id, None)
                # Nettoyage des requetes suivies dont loadingFinished/Failed
                # n'est jamais arrive (cas rare, evite une fuite memoire).
                for request_id, created_at in list(tracked_request_ids.items()):
                    if (now_dt - created_at).total_seconds() > 15:
                        tracked_request_ids.pop(request_id, None)
                continue

            try:
                message = json.loads(raw)
                method = message.get("method")

                if method == "Network.responseReceived":
                    params = message.get("params", {})
                    url = params.get("response", {}).get("url", "")

                    if TARGET_REQUEST in url:
                        request_id = params.get("requestId")
                        if request_id:
                            # On ne demande pas encore le corps ici : a ce stade
                            # seuls les headers sont garantis disponibles. On
                            # attend Network.loadingFinished (corps complet pret)
                            # pour eviter un getResponseBody premature qui peut
                            # echouer meme si la reponse n'a pas ete evincee.
                            tracked_request_ids[request_id] = datetime.now()

                elif method == "Network.loadingFinished":
                    request_id = message.get("params", {}).get("requestId")
                    if request_id and request_id in tracked_request_ids:
                        tracked_request_ids.pop(request_id, None)
                        cmd_id = await send(
                            "Network.getResponseBody",
                            {"requestId": request_id}
                        )
                        pending[cmd_id] = datetime.now()

                elif method == "Network.loadingFailed":
                    request_id = message.get("params", {}).get("requestId")
                    tracked_request_ids.pop(request_id, None)

                elif message.get("id") in pending:
                    pending.pop(message["id"], None)

                    if "error" in message:
                        # Le corps de la reponse a ete evince du buffer DevTools
                        # avant qu'on ait pu le recuperer (trop de requetes en
                        # parallele, ou buffer trop petit). On le compte et on
                        # avertit periodiquement plutot que de laisser passer
                        # en silence : ca permet de voir si ca se reproduit
                        # meme avec le buffer agrandi.
                        missed_body_count += 1
                        now_dt = datetime.now()
                        if (now_dt - last_missed_body_warning).total_seconds() >= 30:
                            write_error(
                                f"AVERTISSEMENT_BUFFER_DEVTOOLS | "
                                f"{missed_body_count} corps de reponse perdus "
                                f"(evinces du buffer CDP) depuis le dernier avertissement | "
                                f"dernier_erreur={message.get('error', {}).get('message', '')}"
                            )
                            last_missed_body_warning = now_dt
                            missed_body_count = 0
                        continue

                    body = message.get("result", {}).get("body", "")
                    nelyio_heartbeat()

                    if body:
                        write_raw(body)

                    if "UpAgt" in body:
                        mark_useful_log_received()
                        process_response(body)

            except Exception as e:
                write_error(f"ERREUR_CAPTURE | {e}")


def run_capture():
    # Reconnexion autonome : si Edge/Hermès coupe le WebSocket, on retente sans action manuelle.
    while not stop_event.is_set():
        try:
            asyncio.run(capture_loop())
        except Exception as e:
            write_error(f"ERREUR_SCRIPT | {e}")
            if stop_event.is_set():
                break
            stop_event.wait(3)
        else:
            break
    write_general("INFO | Capture arrêtée")


def is_capture_active():
    return capture_thread is not None and capture_thread.is_alive()


def start_capture():
    global capture_thread

    if is_capture_active():
        write_general("INFO | Capture déjà démarrée")
        return

    stop_event.clear()
    mark_capture_started()
    capture_thread = threading.Thread(target=run_capture, daemon=True)
    capture_thread.start()
    write_general("INFO | Start capture")


def stop_capture():
    stop_event.set()
    write_general("INFO | Stop demandé")


# =========================
# SCHEDULE
# =========================
# Le planning horaire est entierement delegue a Timer.py : ce script ne
# decide plus lui-meme s'il doit etre actif selon l'heure. Voir
# schedule_capture() plus haut.


def restart_capture(reason):
    if not set_restart_flag_if_free():
        return

    write_error(f"WATCHDOG | Redemarrage capture | raison={reason}")
    stop_capture()

    def delayed_start():
        try:
            if not is_capture_active():
                start_capture()
            else:
                write_general("WATCHDOG | Ancienne capture encore active, redemarrage reporte")
        except Exception as e:
            write_error(f"ERREUR_WATCHDOG_RESTART | {e}")
        finally:
            reset_restart_flag()

    root.after(RESTART_DELAY_MS, delayed_start)


def schedule_capture():
    """
    Demarre la capture immediatement et garde uniquement le role de watchdog
    anti-blocage (relance si aucun log utile pendant WATCHDOG_NO_LOG_SECONDS).

    Avant, ce script avait son propre planning interne (champs Start/Stop)
    en plus de celui gere par Timer.py (le superviseur qui lance/tue ce
    process). Les deux horaires devaient rester synchronises manuellement :
    si l'un changeait sans l'autre, des minutes de capture pouvaient etre
    perdues en silence, sans aucune alerte. Comme Timer.py est deja la seule
    source de verite sur QUAND ce process tourne, CapV4 n'a plus besoin de
    redecider lui-meme s'il doit etre actif : tant qu'il est lance, il capture.
    """
    global schedule_job

    def watchdog_only():
        global schedule_job

        try:
            if not is_capture_active():
                write_general("INFO | Capture absente, demarrage")
                start_capture()
            else:
                silence = get_seconds_without_useful_log()
                if silence >= WATCHDOG_NO_LOG_SECONDS:
                    restart_capture(f"aucun log utile depuis {silence}s")

        except Exception as e:
            write_error(f"ERREUR_WATCHDOG | {e}")

        schedule_job = root.after(WATCHDOG_CHECK_EVERY_MS, watchdog_only)

    if schedule_job:
        root.after_cancel(schedule_job)

    write_general(
        f"INFO | Capture demarree immediatement (planning gere par Timer.py) | "
        f"watchdog: relance si aucun log utile pendant {WATCHDOG_NO_LOG_SECONDS}s"
    )
    start_capture()
    schedule_job = root.after(WATCHDOG_CHECK_EVERY_MS, watchdog_only)


def cancel_schedule():
    global schedule_job

    if schedule_job:
        root.after_cancel(schedule_job)
        schedule_job = None
        write_general("INFO | Watchdog desactive")


# =========================
# REPORT / EXPORT
# =========================

def export_file(source_file, title, default_name):
    export_path = filedialog.asksaveasfilename(
        title=title,
        defaultextension=".txt",
        initialfile=default_name,
        filetypes=[
            ("Fichier texte", "*.txt"),
            ("Tous les fichiers", "*.*")
        ]
    )

    if not export_path:
        write_general("INFO | Export annulé")
        return

    try:
        shutil.copy2(source_file, export_path)
        write_general(f"INFO | Export créé avec succès | {export_path}")
    except Exception as e:
        write_error(f"ERREUR | Impossible d'exporter : {e}")


def export_general():
    export_file(GENERAL_FILE, "Exporter log général", f"export_hermes_general_{datetime.now():%Y-%m-%d_%H-%M-%S}.txt")


def export_raw():
    export_file(RAW_FILE, "Exporter RAW changes.ashx", f"export_hermes_raw_{datetime.now():%Y-%m-%d_%H-%M-%S}.txt")


def export_calls():
    export_file(CALLS_FILE, "Exporter appels blancs", f"export_appels_blancs_{datetime.now():%Y-%m-%d_%H-%M-%S}.txt")


def export_connexions():
    export_file(CONNEXION_FILE, "Exporter déconnexions", f"export_deconnexions_reconnexions_{datetime.now():%Y-%m-%d_%H-%M-%S}.txt")


def export_stats():
    export_file(STATS_FILE, "Exporter stats diagnostic", f"export_stats_agents_{datetime.now():%Y-%m-%d_%H-%M-%S}.txt")


def export_errors():
    export_file(ERROR_FILE, "Exporter erreurs capture", f"export_erreurs_capture_{datetime.now():%Y-%m-%d_%H-%M-%S}.txt")


def generate_summary():
    try:
        set_writable(SUMMARY_FILE)

        with open(SUMMARY_FILE, "w", encoding="utf-8") as f:
            f.write("===== RESUME DIAGNOSTIC HERMES =====\n")
            f.write(f"Genere le : {datetime.now():%Y-%m-%d %H:%M:%S}\n\n")

            f.write("Agent | Deco | Reco | Deco en appel | Appels blancs | Micro erreurs | Transferts | Temps deconnecte\n")
            f.write("-" * 110 + "\n")

            for agent_id in sorted(stats.keys(), key=lambda x: int(x) if str(x).isdigit() else str(x)):
                s = stats[agent_id]
                seconds = s["temps_deconnecte_seconds"]
                minutes = seconds // 60
                rest = seconds % 60

                f.write(
                    f"{agent_id} | "
                    f"{s['deconnexions']} | "
                    f"{s['reconnexions']} | "
                    f"{s['deconnexions_en_appel']} | "
                    f"{s['appels_blancs']} | "
                    f"{s['micro_erreurs']} | "
                    f"{s['transferts']} | "
                    f"{minutes}m {rest}s\n"
                )

        set_readonly(SUMMARY_FILE)
        write_general(f"INFO | Résumé généré | {SUMMARY_FILE}")

    except Exception as e:
        write_error(f"ERREUR_RESUME | {e}")


# =========================
# UI
# =========================

def update_live_labels():
    try:
        total = len(agents)
        connected = sum(1 for state in agents.values() if is_connected(state))
        disconnected = total - connected
        in_call = sum(1 for state in agents.values() if is_call_state(state))

        text = (
            f"Agents connus: {total} | Connectés: {connected} | "
            f"Déconnectés: {disconnected} | En appel: {in_call}"
        )
        try:
            ui_queue.put_nowait(("__LIVE_LABEL__", text))
        except Exception:
            pass
    except Exception:
        pass


def on_close():
    global schedule_job, ui_pump_job

    if schedule_job:
        root.after_cancel(schedule_job)
    if ui_pump_job:
        root.after_cancel(ui_pump_job)

    stop_capture()
    root.after(800, root.destroy)


init_files()

root = tk.Tk()
root.title("Hermes Capture Diagnostic V4 Watchdog")
root.geometry("1250x760")

tk.Label(
    root,
    text="Hermes Capture Diagnostic - RAW / Appels / Déconnexions / Micro / Transfert / Watchdog",
    font=("Arial", 14, "bold")
).pack(pady=10)

button_frame = tk.Frame(root)
button_frame.pack(pady=5)

tk.Button(button_frame, text="START MANUEL", width=18, command=start_capture).grid(row=0, column=0, padx=10)
tk.Button(button_frame, text="STOP MANUEL", width=18, command=stop_capture).grid(row=0, column=1, padx=10)

schedule_frame = tk.LabelFrame(root, text="Watchdog (planning gere par Timer.py)")
schedule_frame.pack(padx=10, pady=10, fill="x")

tk.Label(
    schedule_frame,
    text=(
        "Cette fenetre n'a plus de planning horaire propre. Timer.py decide "
        "QUAND ce process tourne ; ici, la capture demarre des le lancement "
        f"et le watchdog la relance si aucun log utile pendant {WATCHDOG_NO_LOG_SECONDS}s."
    ),
    wraplength=1100,
    justify="left",
).pack(padx=10, pady=8, anchor="w")

tk.Button(schedule_frame, text="ACTIVER WATCHDOG", width=20, command=schedule_capture).pack(side="left", padx=10, pady=5)
tk.Button(schedule_frame, text="DÉSACTIVER WATCHDOG", width=20, command=cancel_schedule).pack(side="left", padx=10, pady=5)

live_label = tk.Label(
    root,
    text="Agents connus: 0 | Connectés: 0 | Déconnectés: 0 | En appel: 0",
    font=("Arial", 11, "bold"),
    fg="blue"
)
live_label.pack(pady=5)

tk.Label(
    root,
    text=(
        "Mode SQLite only : TXT désactivés pendant capture | "
        "appels_blancs=<=15s avec client/numéro | deconnexions=deco/reco + numéro si coupure en appel | "
        "stats=micro/transfert | erreurs=problèmes capture"
    ),
    fg="red"
).pack(pady=5)

export_frame = tk.LabelFrame(root, text="Export / Rapport")
export_frame.pack(padx=10, pady=10, fill="x")

tk.Button(export_frame, text="EXPORT GENERAL", width=20, command=export_general).grid(row=0, column=0, padx=6, pady=8)
tk.Button(export_frame, text="EXPORT RAW", width=20, command=export_raw).grid(row=0, column=1, padx=6, pady=8)
tk.Button(export_frame, text="EXPORT APPELS BLANCS", width=22, command=export_calls).grid(row=0, column=2, padx=6, pady=8)
tk.Button(export_frame, text="EXPORT DECONNEXIONS", width=22, command=export_connexions).grid(row=0, column=3, padx=6, pady=8)
tk.Button(export_frame, text="EXPORT STATS", width=20, command=export_stats).grid(row=0, column=4, padx=6, pady=8)
tk.Button(export_frame, text="EXPORT ERREURS", width=20, command=export_errors).grid(row=0, column=5, padx=6, pady=8)
tk.Button(export_frame, text="GENERER RESUME", width=20, command=generate_summary).grid(row=0, column=6, padx=6, pady=8)

output_box = scrolledtext.ScrolledText(root, width=150, height=27)
output_box.pack(padx=10, pady=10)

root.after(1000, schedule_capture)
root.after(100, process_ui_queue)

root.protocol("WM_DELETE_WINDOW", on_close)
root.mainloop()
