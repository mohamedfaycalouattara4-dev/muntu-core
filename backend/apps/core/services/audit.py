"""Service audit : chaîne HMAC append-only, contexte d'audit."""
from __future__ import annotations

import contextlib
import hashlib
import json
import logging
from dataclasses import dataclass, field
from typing import Any

from django.db import models

from apps.core.security import sign_hmac

logger = logging.getLogger("muntu.audit")


@dataclass
class _AuditCtx:
    user: Any | None = None
    ip: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


_stack: list[_AuditCtx] = []


@contextlib.contextmanager
def audit_context(user=None, ip=None):
    _stack.append(_AuditCtx(user=user, ip=ip))
    try:
        yield
    finally:
        _stack.pop()


def current_context() -> _AuditCtx:
    return _stack[-1] if _stack else _AuditCtx()


def chain_payload(previous_hash: str, payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(f"{previous_hash}|{encoded}".encode("utf-8")).hexdigest()


def sign_audit_record(record_hash: str) -> str:
    return sign_hmac(record_hash, "AUDIT_SIGNING_KEY")


def emit(entity_type: str, entity_id: str, action: str, payload: dict[str, Any]) -> str:
    """Émet un événement d'audit. Retourne record_hash."""
    from apps.audit.models import AuditEvent  # avoid circular

    previous = AuditEvent.objects.order_by("-id").first()
    previous_hash = previous.current_hash if previous else "0" * 64
    full_payload = {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "action": action,
        "payload": payload,
        "actor_ip": current_context().ip,
        "actor_id": getattr(current_context().user, "id", None),
    }
    record_hash = chain_payload(previous_hash, full_payload)
    AuditEvent.objects.create(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        payload=full_payload,
        previous_hash=previous_hash,
        current_hash=record_hash,
        signature=sign_audit_record(record_hash),
    )
    return record_hash
