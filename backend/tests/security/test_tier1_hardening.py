"""Tests de non-régression et de robustesse pour les améliorations Tier-1 de Muntu-Core.
Valide l'idempotence stricte et le chaînage cryptographique du Ledger.
"""
import pytest
from apps.core.services.resilience import enforce_idempotency, store_idempotency_result, IdempotencyViolationError
from apps.payments.services.crypto_ledger import compute_entry_hash, verify_ledger_integrity

def test_idempotency_protection():
    """Vérifie que la même clé avec le même payload renvoie le résultat mémorisé,
    et bloque toute tentative de rejeu avec un payload altéré.
    """
    key = "idem-test-12345"
    payload = {"account_id": "acc_01", "amount": 10000}
    result = {"status": "SUCCESS", "tx_id": "tx_999"}

    # 1. Premier appel : pas de cache
    assert enforce_idempotency(key, payload) is None

    # Stockage du résultat
    store_idempotency_result(key, payload, result)

    # 2. Deuxième appel identique : renvoie le résultat
    cached = enforce_idempotency(key, payload)
    assert cached == result

    # 3. Appel avec payload modifié : lève une exception de sécurité
    fraudulent_payload = {"account_id": "acc_01", "amount": 99999}
    with pytest.raises(IdempotencyViolationError):
        enforce_idempotency(key, fraudulent_payload)


def test_crypto_ledger_chaining():
    """Vérifie que le chaînage cryptographique HMAC-SHA512 détecte toute altération d'écriture."""
    prev_hash = "0" * 128
    entries = []

    for i in range(3):
        entry = {
            "id": f"entry_{i}",
            "account_id": "acc_01",
            "amount": 5000 + i * 100,
            "direction": "DEBIT" if i % 2 == 0 else "CREDIT",
            "timestamp": f"2026-08-12T12:0{i}:00Z"
        }
        sig = compute_entry_hash(prev_hash, entry)
        entry["signature_hash"] = sig
        entries.append(entry)
        prev_hash = sig

    # Intégrité initiale valide
    is_valid, bad_idx = verify_ledger_integrity(entries)
    assert is_valid is True
    assert bad_idx == -1

    # Fraude : altération du montant de la deuxième écriture
    entries[1]["amount"] = 999999
    is_valid, bad_idx = verify_ledger_integrity(entries)
    assert is_valid is False
    assert bad_idx == 1
