"""High-Security Zone (ZHS / Cold World).

Toutes les opérations financières sensibles passent par `sign_command()` et
`verify_command()` — HMAC-SHA256 horodaté + nonce anti-rejeu.
L'Orchestrateur ZHS vit dans une instance Django distincte sans HTTP public.
"""
from __future__ import annotations

import hmac
from datetime import timedelta
import json
import os
import time
import uuid
from dataclasses import dataclass

from django.conf import settings

from .security import _signing_key, verify_hmac


@dataclass(frozen=True)
class ZhsCommand:
    command: str
    payload: dict
    nonce: str
    issued_at: int

    def canonical(self) -> str:
        return json.dumps({"c": self.command, "p": self.payload,
                           "n": self.nonce, "t": self.issued_at},
                          sort_keys=True, separators=(",", ":"))


def sign_command(command: str, payload: dict, *,
                 nonce: str | None = None, issued_at: int | None = None) -> tuple[ZhsCommand, str]:
    """Crée une commande ZHS signée. Retourne (commande, signature)."""
    nonce = nonce or uuid.uuid4().hex
    issued_at = issued_at or int(time.time())
    cmd = ZhsCommand(command=command, payload=payload,
                     nonce=nonce, issued_at=issued_at)
    signature = hmac.new(_signing_key("HSZ_SIGNING_KEY"),
                         cmd.canonical().encode("utf-8"),
                         "sha256").hexdigest()
    return cmd, signature


def verify_command(cmd: ZhsCommand, signature: str) -> bool:
    expected = hmac.new(_signing_key("HSZ_SIGNING_KEY"),
                        cmd.canonical().encode("utf-8"),
                        "sha256").hexdigest()
    if not hmac.compare_digest(expected, signature or ""):
        return False
    # Anti-rejeu (nonces 24h)
    now = int(time.time())
    if abs(now - cmd.issued_at) > 24 * 3600:
        return False
    from django.utils import timezone  # noqa: PLC0415

    from .models import UsedNonce  # noqa: PLC0415
    if UsedNonce.objects.filter(nonce=cmd.nonce, expires_at__gt=timezone.now()).exists():
        return False
    UsedNonce.objects.create(
        nonce=cmd.nonce,
        expires_at=timezone.now() + timedelta(hours=24),
    )
    return True
