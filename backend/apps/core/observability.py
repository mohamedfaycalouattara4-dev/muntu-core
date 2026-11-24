"""Contexte de corrélation des logs (request_id / reference / actor).

Chaque requête HTTP, tâche Celery ou opération de ledger porte un
identifiant de corrélation ULID. Ce contexte est propagé via `contextvars`
(compatible async/ASGI) et injecté automatiquement dans chaque log JSON par
`LogContextFilter`.
"""
from __future__ import annotations

import logging
from contextlib import contextmanager
from contextvars import ContextVar, Token
import secrets
import time
from typing import Any, Iterator

CROCKFORD32 = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def generate_ulid() -> str:
    """ULID 26 caractères — dupliqué ici pour rester importable très tôt.

    `apps.core.models` ne peut pas être importé pendant la configuration du
    logging (le registre d'applications Django n'est pas encore prêt).
    """
    ts = int(time.time() * 1000) & ((1 << 48) - 1)
    time_part = "".join(CROCKFORD32[(ts >> shift) & 0x1F] for shift in range(45, -1, -5))
    return time_part + "".join(secrets.choice(CROCKFORD32) for _ in range(16))

_request_id: ContextVar[str] = ContextVar("kalyce_request_id", default="")
_reference: ContextVar[str] = ContextVar("kalyce_reference", default="")
_actor_id: ContextVar[str] = ContextVar("kalyce_actor_id", default="")

CORRELATION_HEADER = "X-Request-ID"


def new_correlation_id() -> str:
    """ULID 26 caractères — triable dans le temps, non devinable."""
    return generate_ulid()


def get_request_id() -> str:
    return _request_id.get()


def set_request_id(value: str) -> Token:
    return _request_id.set(value or "")


def get_reference() -> str:
    return _reference.get()


def get_actor_id() -> str:
    return _actor_id.get()


def current_context() -> dict[str, str]:
    ctx = {
        "request_id": _request_id.get(),
        "reference": _reference.get(),
        "actor_id": _actor_id.get(),
    }
    return {k: v for k, v in ctx.items() if v}


@contextmanager
def bind_context(*, request_id: str | None = None, reference: str | None = None,
                 actor_id: str | None = None) -> Iterator[dict[str, Any]]:
    """Lie temporairement un contexte de corrélation (ledger, tâches, vues)."""
    tokens: list[tuple[ContextVar[str], Token]] = []
    if request_id is not None:
        tokens.append((_request_id, _request_id.set(request_id)))
    if reference is not None:
        tokens.append((_reference, _reference.set(reference)))
    if actor_id is not None:
        tokens.append((_actor_id, _actor_id.set(actor_id)))
    try:
        yield current_context()
    finally:
        for var, token in reversed(tokens):
            var.reset(token)


class LogContextFilter(logging.Filter):
    """Injecte request_id / reference / actor_id dans chaque LogRecord."""

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: D102
        record.request_id = _request_id.get()
        record.reference = _reference.get()
        record.actor_id = _actor_id.get()
        return True
