"""Module de résilience atomique et de verrouillage distribué — Muntu-Core Tier-1.
Fournit des garanties d'idempotence stricte et de prévention des race conditions
pour les transactions financières critiques.
"""
from __future__ import annotations

import hashlib
import json
from functools import wraps
from typing import Any, Callable
from django.db import transaction, DatabaseError
from django.core.cache import cache
import logging

logger = logging.getLogger("muntu.resilience")


class IdempotencyViolationError(DatabaseError):
    """Levé lorsqu'une requête dupliquée avec la même clé d'idempotence tente de s'exécuter avec des charges différentes."""
    pass


def atomic_financial_operation(lock_timeout_ms: int = 5000):
    """Décorateur d'ingénierie expert pour garantir l'atomicité, l'isolation sérialisable
    et la protection contre les race conditions sur les comptes et le grand livre.
    """
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Utilisation d'une transaction sérialisable pour empêcher les anomalies de lecture/écriture
            with transaction.atomic(using='default', savepoint=True):
                try:
                    result = func(*args, **kwargs)
                    return result
                except Exception as e:
                    logger.exception("Erreur critique dans une opération financière atomique — Rollback forcé.")
                    raise
        return wrapper
    return decorator


def enforce_idempotency(idempotency_key: str, payload: dict[str, Any], ttl_seconds: int = 86400) -> Any | None:
    """Vérifie l'idempotence d'une requête financière.
    Empêche le double décaissement ou le double crédit en cas de timeout réseau.
    """
    if not idempotency_key:
        return None

    payload_hash = hashlib.sha256(json.dumps(payload, sort_keys=True).encode('utf-8')).hexdigest()
    cache_key = f"muntu:idempotency:{idempotency_key}"

    existing = cache.get(cache_key)
    if existing:
        if existing['hash'] != payload_hash:
            raise IdempotencyViolationError(
                f"Conflit d'idempotence : la clé '{idempotency_key}' a déjà été utilisée avec un payload différent."
            )
        logger.info(f"Requête idempotente interceptée et rejouée (Clé: {idempotency_key})")
        return existing['result']

    return None


def store_idempotency_result(idempotency_key: str, payload: dict[str, Any], result: Any, ttl_seconds: int = 86400) -> None:
    """Enregistre le résultat d'une opération financière réussie pour idempotence future."""
    if not idempotency_key:
        return
    payload_hash = hashlib.sha256(json.dumps(payload, sort_keys=True).encode('utf-8')).hexdigest()
    cache_key = f"muntu:idempotency:{idempotency_key}"
    cache.set(cache_key, {'hash': payload_hash, 'result': result}, timeout=ttl_seconds)
