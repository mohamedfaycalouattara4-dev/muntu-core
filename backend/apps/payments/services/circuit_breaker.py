"""Circuit Breaker (5 failures/60s = open, half-open après 300s).

État stocké en cache Django pour partage workers.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

from django.core.cache import cache

logger = logging.getLogger("muntu.payments")


class CircuitOpenError(Exception):
    pass


@dataclass
class _Bucket:
    failures: int = 0
    opened_at: float = 0.0
    state: str = "closed"  # closed / open / half_open


def _key(provider: str) -> str:
    return f"cb:{provider}"


def call(provider: str, fn, *args, **kwargs):
    bucket = cache.get(_key(provider)) or {"failures": 0, "opened_at": 0.0, "state": "closed"}
    now = time.time()
    if bucket["state"] == "open" and (now - bucket["opened_at"]) >= 300:
        bucket["state"] = "half_open"
        cache.set(_key(provider), bucket, timeout=600)
    if bucket["state"] == "open":
        raise CircuitOpenError(f"Provider {provider} indisponible")
    try:
        result = fn(*args, **kwargs)
    except Exception:
        bucket["failures"] += 1
        bucket["opened_at"] = now
        if bucket["failures"] >= 5:
            bucket["state"] = "open"
            logger.warning("Circuit breaker OPEN %s after 5 failures", provider)
        cache.set(_key(provider), bucket, timeout=600)
        raise
    if bucket["state"] == "half_open":
        bucket["state"] = "closed"
        bucket["failures"] = 0
        cache.set(_key(provider), bucket, timeout=600)
        logger.info("Circuit breaker CLOSED %s", provider)
    return result
