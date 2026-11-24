"""Middleware DRF : Idempotency-Key universelle pour mutations financières.

Modèle de concurrence (corrige la race condition « lock-after-response ») :

1. Le verrou est posé **avant** l'exécution de la vue, via `cache.add()` —
   opération atomique (`SETNX` côté Redis, verrou interne côté LocMem) qui
   échoue si la clé existe déjà. Deux requêtes concurrentes ne peuvent donc
   jamais exécuter la vue en parallèle.
2. La requête gagnante traite la demande puis remplace le marqueur `pending`
   par le résultat définitif (`done`) avec le TTL métier.
3. Une requête perdante :
      * `done`     → rejoue la réponse mémorisée (200/201…, en-tête
                     `Idempotent-Replay: true`) ;
      * `pending`  → `409 Conflict` (traitement en cours, retenter plus tard) ;
      * empreinte différente → `422` (clé réutilisée avec un autre payload).
4. Toute réponse non-2xx ou toute exception libère le verrou : l'appelant
   peut retenter avec la même clé.

Le TTL du verrou (`IDEMPOTENCY_LOCK_TTL_SECONDS`, défaut 60 s) borne l'impact
d'un worker tué en plein traitement.
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import Callable

from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse

from ..metrics import IDEMPOTENCY_EVENTS

logger = logging.getLogger("muntu.core.idempotency")

_HEADER = "idempotency-key"
_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

STATE_PENDING = "pending"
STATE_DONE = "done"

DEFAULT_LOCK_TTL = 60
DEFAULT_RESULT_TTL = 86400


def _bucket_key(key: str, route: str) -> str:
    salted = f"{route}|{key}"
    return f"idem:{hashlib.sha256(salted.encode()).hexdigest()}"


def _fingerprint(request) -> str:
    """Empreinte du payload : détecte la réutilisation abusive d'une clé."""
    try:
        body = request.body or b""
    except Exception:  # pragma: no cover - corps déjà consommé / streaming
        body = b""
    return hashlib.sha256(
        f"{request.method}|{request.path}|".encode() + body).hexdigest()


def _lock_ttl() -> int:
    return int(getattr(settings, "IDEMPOTENCY_LOCK_TTL_SECONDS", DEFAULT_LOCK_TTL))


def _result_ttl() -> int:
    return int(getattr(settings, "IDEMPOTENCY_TTL_SECONDS", DEFAULT_RESULT_TTL))


def _count(result: str) -> None:
    try:
        IDEMPOTENCY_EVENTS.labels(result=result).inc()
    except Exception:  # pragma: no cover - la métrique ne doit jamais casser l'API
        logger.debug("metric idempotency non incrémentée", exc_info=True)


class IdempotencyMiddleware:
    def __init__(self, get_response: Callable):
        self.get_response = get_response

    def __call__(self, request):
        if request.method not in _METHODS:
            return self.get_response(request)
        key = request.headers.get(_HEADER) or request.headers.get(_HEADER.title())
        if not key:
            return self.get_response(request)

        bucket = _bucket_key(key, request.path)
        fingerprint = _fingerprint(request)
        marker = {
            "state": STATE_PENDING,
            "fingerprint": fingerprint,
            "ts": int(time.time()),
        }

        # --- Verrou atomique AVANT traitement (ferme la fenêtre de course) ---
        if cache.add(bucket, marker, timeout=_lock_ttl()):
            _count("acquired")
            return self._process_and_store(request, bucket, fingerprint)

        existing = cache.get(bucket)
        if existing is None:
            # Le verrou a expiré entre le `add` et le `get` : on retente une
            # acquisition, sinon on laisse simplement passer la requête.
            if cache.add(bucket, marker, timeout=_lock_ttl()):
                _count("acquired")
                return self._process_and_store(request, bucket, fingerprint)
            _count("race_passthrough")
            return self.get_response(request)

        if existing.get("fingerprint") not in (None, fingerprint):
            _count("fingerprint_mismatch")
            logger.warning("Idempotency-Key réutilisée avec un payload différent path=%s",
                           request.path)
            return JsonResponse(
                {"detail": "Idempotency-Key déjà utilisée avec un payload différent.",
                 "code": "idempotency_key_reuse"},
                status=422)

        if existing.get("state") == STATE_DONE:
            _count("replayed")
            response = JsonResponse(existing["body"], status=existing["status"],
                                    safe=not isinstance(existing["body"], list))
            response["Idempotent-Replay"] = "true"
            return response

        _count("conflict")
        logger.info("Requête idempotente déjà en cours path=%s", request.path)
        response = JsonResponse(
            {"detail": "Requête identique en cours de traitement.",
             "code": "idempotency_in_progress"},
            status=409)
        response["Retry-After"] = "1"
        return response

    # ------------------------------------------------------------------
    def _process_and_store(self, request, bucket: str, fingerprint: str):
        try:
            response = self.get_response(request)
        except Exception:
            cache.delete(bucket)  # libère le verrou : la clé reste rejouable
            _count("released_on_error")
            raise

        if not (200 <= response.status_code < 300):
            cache.delete(bucket)
            _count("released_on_failure")
            return response

        if getattr(response, "streaming", False):
            cache.delete(bucket)
            _count("released_streaming")
            return response

        try:
            body = json.loads(response.content.decode("utf-8"))
        except (ValueError, UnicodeDecodeError, AttributeError):
            cache.delete(bucket)
            _count("released_non_json")
            return response

        cache.set(bucket, {
            "state": STATE_DONE,
            "fingerprint": fingerprint,
            "body": body,
            "status": response.status_code,
            "ts": int(time.time()),
        }, timeout=_result_ttl())
        _count("stored")
        return response
