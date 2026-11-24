"""Muntu Core — Vérification d'intégrité du grand livre (chainage HMAC).

I1 : Aucune écriture hors grand livre.
Le chainage HMAC garantit que chaque écriture dépend cryptographiquement
de la précédente. Toute altération est détectable.
"""
from __future__ import annotations
import hashlib
import hmac
from typing import Optional


def compute_entry_hash(
    tenant_id: str,
    account_code: str,
    direction: str,
    amount_xof: int,
    reference: str,
    previous_hash: str = "",
    signing_key: str = "",
) -> str:
    """Calcule le hash HMAC d'une écriture (SHA-256).

    Le hash inclut :
    - Le hash de l'écriture précédente (chainage)
    - Les champs métier (tenant, compte, direction, montant, référence)
    """
    payload = f"{previous_hash}|{tenant_id}|{account_code}|{direction}|{amount_xof}|{reference}"
    if signing_key:
        return hmac.new(signing_key.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return hashlib.sha256(payload.encode()).hexdigest()


def compute_entry_signature(
    entry_hash: str,
    tenant_id: str,
    signing_key: str,
) -> str:
    """Calcule la signature HMAC de l'écriture complète.

    Utilise la clé de signature HSZ_SIGNING_KEY.
    """
    payload = f"{entry_hash}|{tenant_id}"
    return hmac.new(signing_key.encode(), payload.encode(), hashlib.sha256).hexdigest()


def verify_chain(
    entries: list[dict],
    signing_key: str = "",
) -> list[dict]:
    """Vérifie le chainage HMAC d'une séquence d'écritures.

    Args:
        entries: Liste de dictionnaires avec les champs de chaque écriture.
        signing_key: Clé HMAC utilisée pour la signature.

    Returns:
        Liste de résultats de vérification par écriture.
    """
    results = []
    previous_hash = ""

    for entry in entries:
        expected_hash = compute_entry_hash(
            tenant_id=entry.get("tenant_id", ""),
            account_code=entry.get("account_code", ""),
            direction=entry.get("direction", ""),
            amount_xof=entry.get("amount_xof", 0),
            reference=entry.get("reference", ""),
            previous_hash=previous_hash,
            signing_key=signing_key,
        )
        actual_hash = entry.get("entry_hash", "")
        is_valid = actual_hash == expected_hash

        results.append({
            "entry_id": entry.get("id", "unknown"),
            "expected_hash": expected_hash,
            "actual_hash": actual_hash,
            "is_valid": is_valid,
            "previous_hash": previous_hash,
        })

        if is_valid:
            previous_hash = actual_hash
        else:
            # Le chainage est cassé — arrêter la vérification
            break

    return results


def compute_merkle_root(hashes: list[str]) -> str:
    """Calcule la racine Merkle d'une liste de hash SHA-256.

    Utilisé pour le scellement des journées comptables (I5).
    """
    if not hashes:
        return hashlib.sha256(b"").hexdigest()

    if len(hashes) == 1:
        return hashes[0]

    # Si impair, dupliquer le dernier
    if len(hashes) % 2 == 1:
        hashes.append(hashes[-1])

    # Construire l'arbre niveau par niveau
    level = hashes
    while len(level) > 1:
        next_level = []
        for i in range(0, len(level), 2):
            combined = level[i] + level[i + 1]
            next_level.append(hashlib.sha256(combined.encode()).hexdigest())
        level = next_level

    return level[0]


def verify_day_balance(
    total_debit: int,
    total_credit: int,
) -> bool:
    """Vérifie qu'une journée comptable est équilibrée (partie double)."""
    return total_debit == total_credit
