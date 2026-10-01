"""Shared RC29 sorting contract.

Only allowlisted logical keys are accepted. Missing values always sort last in
both directions and a deterministic id key is always used as the final tie
breaker before pagination.
"""
from __future__ import annotations
from functools import cmp_to_key

MISSING_STRINGS={"","—","-","unknown","inconnu","non observé","non observe","non calculable","n/a","none","null"}


def request(qs, *, allowed, default_key, default_direction="desc"):
    def get(name, default=""):
        raw=(qs or {}).get(name,[default])
        if isinstance(raw,(list,tuple)):raw=raw[0] if raw else default
        return str(raw or "").strip().lower()
    key=get("sort",default_key) or default_key
    direction=get("direction",default_direction) or default_direction
    if key=="default":key=default_key;direction=default_direction
    if key not in set(allowed):raise ValueError("Clé de tri non autorisée.")
    if direction not in {"asc","desc"}:raise ValueError("Direction de tri non autorisée.")
    return key,direction


def _missing(value):
    if value is None:return True
    if isinstance(value,str):return value.strip().casefold() in MISSING_STRINGS
    return False


def sorted_rows(rows, *, key, direction, getter, id_getter):
    factor=1 if direction=="asc" else -1
    def cmp(a,b):
        av=getter(a,key);bv=getter(b,key)
        am=_missing(av);bm=_missing(bv)
        if am or bm:
            if am and bm:primary=0
            else:return 1 if am else -1
        else:
            if isinstance(av,(int,float)) and isinstance(bv,(int,float)):
                primary=(av>bv)-(av<bv)
            else:
                aa=str(av).casefold();bb=str(bv).casefold();primary=(aa>bb)-(aa<bb)
            primary*=factor
        if primary:return primary
        ai=str(id_getter(a) or "");bi=str(id_getter(b) or "")
        return (ai>bi)-(ai<bi)
    return sorted(list(rows or []),key=cmp_to_key(cmp))
