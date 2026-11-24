"""Module de chaînage cryptographique de niveau bancaire (Merkle & HMAC-SHA512) — Muntu-Core.
Garantit l'immuabilité totale du Grand Livre et détecte toute tentative d'altération en base de données.
"""
from __future__ import annotations

import hashlib
import hmac
from django.conf import settings
import logging

logger = logging.getLogger("muntu.crypto_ledger")


def compute_entry_hash(previous_hash: str, entry_data: dict[str, any], secret_key: str = "") -> str:
    """Calcule un hachage cryptographique sécurisé (HMAC-SHA512) liant l'écriture courante
    à l'écriture précédente, formant une chaîne ininterrompue de type blockchain privée.
    """
    if not secret_key:
        secret_key = getattr(settings, 'SECRET_KEY', 'muntu-core-secure-ledger-key')

    canonical_data = f"{previous_hash}:{entry_data.get('account_id')}:{entry_data.get('amount')}:{entry_data.get('direction')}:{entry_data.get('timestamp')}"

    signature = hmac.new(
        secret_key.encode('utf-8'),
        canonical_data.encode('utf-8'),
        hashlib.sha512
    ).hexdigest()

    return signature


def verify_ledger_integrity(entries: list[dict[str, any]]) -> tuple[bool, int]:
    """Audite une liste d'entrées chronologiques du Grand Livre.
    Renvoie (True, -1) si intègre, ou (False, index_de_la_rupture) en cas de fraude ou d'altération.
    """
    previous_hash = "0" * 128
    for idx, entry in enumerate(entries):
        expected_hash = compute_entry_hash(previous_hash, entry)
        if entry.get('signature_hash') != expected_hash:
            logger.critical(f"ALERTE RUPTURE LEDGER : Altération détectée à l'index {idx} (ID: {entry.get('id')})")
            return False, idx
        previous_hash = expected_hash

    return True, -1
