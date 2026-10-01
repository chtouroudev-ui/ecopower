"""Per-import ZIP cache.

The same SIMPLIFY2 archive is consumed by Support, Quality and Details during a
single import.  Keeping one ZipFile plus bounded decompressed/member parse cache
avoids reopening/decompressing the same large CSV several times.  The cache is
scoped to the current import worker via ContextVar and is released immediately
when the import finishes.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
import io
import zipfile

_CURRENT = ContextVar('nelyio_import_bundle', default=None)


class ImportBundle:
    def __init__(self, raw: bytes, filename: str):
        self.raw = raw
        self.filename = str(filename or '')
        self._zip = None
        self._infos = None
        self._bytes = {}
        self._memo = {}
        self.read_hits = 0
        self.read_misses = 0
        self.memo_hits = 0
        self.memo_misses = 0

    @property
    def is_zip(self):
        return self.filename.lower().endswith('.zip')

    def _ensure_zip(self):
        if self._zip is None:
            self._zip = zipfile.ZipFile(io.BytesIO(self.raw))
            self._infos = self._zip.infolist()
        return self._zip

    def infos(self):
        self._ensure_zip()
        return list(self._infos or ())

    def matching(self, suffix: str):
        suffix = str(suffix or '').lower()
        return [info for info in self.infos() if info.filename.lower().endswith(suffix)]

    def read(self, member):
        """Read a member once. Accepts ZipInfo or its exact filename."""
        name = member.filename if hasattr(member, 'filename') else str(member)
        if name not in self._bytes:
            self.read_misses += 1
            self._bytes[name] = self._ensure_zip().read(member)
        else:
            self.read_hits += 1
        return self._bytes[name]

    def memo(self, key, factory):
        if key not in self._memo:
            self.memo_misses += 1
            self._memo[key] = factory()
        else:
            self.memo_hits += 1
        return self._memo[key]

    def stats(self):
        return {
            'member_reads': self.read_misses,
            'member_cache_hits': self.read_hits,
            'parse_entries': len(self._memo),
            'parse_cache_hits': self.memo_hits,
        }

    def close(self):
        if self._zip is not None:
            self._zip.close()
        self._zip = None
        self._infos = None
        self._bytes.clear()
        self._memo.clear()


def current(raw=None, filename=None):
    bundle = _CURRENT.get()
    if bundle is None:
        return None
    if raw is not None and bundle.raw is not raw:
        return None
    if filename is not None and bundle.filename != str(filename or ''):
        return None
    return bundle


@contextmanager
def activate(raw: bytes, filename: str):
    bundle = ImportBundle(raw, filename)
    token = _CURRENT.set(bundle)
    try:
        yield bundle
    finally:
        _CURRENT.reset(token)
        bundle.close()


def begin(raw: bytes, filename: str):
    bundle = ImportBundle(raw, filename)
    token = _CURRENT.set(bundle)
    return token, bundle


def end(state):
    token, bundle = state
    try:
        _CURRENT.reset(token)
    finally:
        bundle.close()
