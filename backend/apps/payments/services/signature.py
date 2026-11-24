"""Signature HMAC-SHA256 des webhooks entrants — V2 §13.3."""
from __future__ import annotations

import hashlib
import hmac

from apps.core.security import _signing_key


def compute_raw_signature(raw_body: bytes, header_signature: str | None) -> str:
    return hmac.new(_signing_key("HSZ_SIGNING_KEY"), raw_body, hashlib.sha256).hexdigest()


def verify_aggregator_signature(raw_body: bytes, header_signature: str | None) -> bool:
    """Constant-time compare pour éviter timing attack."""
    if not header_signature:
        return False
    expected = compute_raw_signature(raw_body, header_signature)
    return hmac.compare_digest(expected, header_signature)
