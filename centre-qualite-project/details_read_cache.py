"""Projections de lecture bornees, jamais une source de verite.

Les valeurs sont des octets immuables. L'appelant fournit la revision lue DANS
son instantane SQLite, les filtres exacts et les regles rechargees. Le TTL limite
la retention ; il n'autorise jamais une reponse perimee pendant 60 secondes.
Aucun thread, aucune connexion, aucun fichier ouvert a l'import.
"""
from collections import OrderedDict
from datetime import date, datetime
import hashlib
import json
import threading
import time


def _json_value(value):
    if isinstance(value, (date, datetime)):
        return {'__date__': value.isoformat()}
    if isinstance(value, (set, frozenset)):
        return {'__set__': sorted(value, key=lambda v: (type(v).__name__, str(v)))}
    raise TypeError('Type non pris en charge pour une cle de projection.')


def fingerprint(value):
    """Cle deterministe incluant les structures internes des moteurs existants."""
    data = json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), default=_json_value, allow_nan=False)
    return hashlib.sha256(data.encode('utf-8')).hexdigest()


class ProjectionCache:
    """LRU de processus ; verrou court, pas de SQL ni calcul sous verrou.

    Un echec ou un depassement de plafond signifie recalcul exact. Des calculs
    simultanes identiques peuvent se dupliquer : aucun verrou global ne bloque
    les autres lecteurs pendant un parcours de plusieurs secondes.
    """
    def __init__(self, max_entries=24, max_bytes=32*1024*1024,
                 max_item_bytes=16*1024*1024, ttl_seconds=60, clock=time.monotonic):
        if any(type(v) is not int or v < 1 for v in (max_entries, max_bytes, max_item_bytes)):
            raise ValueError('Plafonds du cache invalides.')
        if not isinstance(ttl_seconds, (int, float)) or ttl_seconds <= 0:
            raise ValueError('Retention du cache invalide.')
        self.max_entries = max_entries
        self.max_bytes = max_bytes
        self.max_item_bytes = min(max_item_bytes, max_bytes)
        self.ttl_seconds = ttl_seconds
        self.clock = clock
        self.lock = threading.RLock()
        self.entries = OrderedDict()
        self.bytes_used = 0
        self.counters = {'hit': 0, 'miss': 0, 'put': 0, 'evicted': 0, 'oversize': 0}

    def _remove(self, key):
        _, _, size = self.entries.pop(key)
        self.bytes_used -= size

    def _expire(self, now):
        for key, (until, _, _) in list(self.entries.items()):
            if until <= now:
                self._remove(key)
                self.counters['evicted'] += 1

    def get(self, key):
        if key is None:
            return None
        with self.lock:
            self._expire(self.clock())
            entry = self.entries.get(key)
            if entry is None:
                self.counters['miss'] += 1
                return None
            self.entries.move_to_end(key)
            self.counters['hit'] += 1
            return entry[1]

    def put(self, key, *blobs):
        if key is None:
            return False
        if not blobs or any(type(blob) is not bytes for blob in blobs):
            raise TypeError('Le cache accepte uniquement des octets immuables.')
        size = sum(map(len, blobs)) + len(str(key).encode('utf-8'))
        with self.lock:
            now = self.clock()
            self._expire(now)
            if size > self.max_item_bytes:
                self.counters['oversize'] += 1
                return False
            if key in self.entries:
                self._remove(key)
            while self.entries and (len(self.entries) >= self.max_entries or
                                    self.bytes_used + size > self.max_bytes):
                self._remove(next(iter(self.entries)))
                self.counters['evicted'] += 1
            self.entries[key] = (now + self.ttl_seconds, tuple(blobs), size)
            self.bytes_used += size
            self.counters['put'] += 1
            return True

    def clear(self):
        with self.lock:
            self.entries.clear()
            self.bytes_used = 0
            for key in self.counters:
                self.counters[key] = 0

    def stats(self):
        with self.lock:
            self._expire(self.clock())
            return dict(self.counters, entries=len(self.entries), bytes=self.bytes_used,
                        max_bytes=self.max_bytes, ttl_seconds=self.ttl_seconds)
