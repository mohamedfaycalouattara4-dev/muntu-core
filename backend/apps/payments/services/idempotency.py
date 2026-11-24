"""Génération/validation idempotency_key (cohérent V2 §10)."""
from __future__ import annotations

import hashlib
import os
import secrets

from apps.core.security import generate_xof_compatible_token


def derive_key(reference: str, salt: str) -> str:
    return hashlib.sha256(f"{reference}|{salt}|{secrets.token_hex(8)}".encode()).hexdigest()


def default_idempotency_key() -> str:
    return generate_xof_compatible_token()
