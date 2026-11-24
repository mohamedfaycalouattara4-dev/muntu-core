"""Tests d'intégrité du grand livre : chainage HMAC et Merkle."""
from django.test import TestCase
from apps.accounting.services.ledger_integrity import (
    compute_entry_hash, compute_entry_signature, verify_chain,
    compute_merkle_root, verify_day_balance,
)


class LedgerIntegrityTests(TestCase):
    """Tests du chainage HMAC et de la racine Merkle."""

    def test_entry_hash_deterministic(self):
        """Même entrée = même hash."""
        h1 = compute_entry_hash("T1", "501000", "DEBIT", 100000, "ref-001")
        h2 = compute_entry_hash("T1", "501000", "DEBIT", 100000, "ref-001")
        self.assertEqual(h1, h2)
        self.assertEqual(len(h1), 64)  # SHA-256 hex

    def test_entry_hash_changes_with_previous(self):
        """Changer le previous_hash change le résultat."""
        h1 = compute_entry_hash("T1", "501000", "DEBIT", 100000, "ref-001", "")
        h2 = compute_entry_hash("T1", "501000", "DEBIT", 100000, "ref-001", "different_prev")
        self.assertNotEqual(h1, h2)

    def test_entry_hash_changes_with_amount(self):
        """Changer le montant change le hash."""
        h1 = compute_entry_hash("T1", "501000", "DEBIT", 100000, "ref-001")
        h2 = compute_entry_hash("T1", "501000", "DEBIT", 200000, "ref-001")
        self.assertNotEqual(h1, h2)

    def test_entry_signature_with_key(self):
        """La signature HMAC avec clé est différente du hash simple."""
        h = compute_entry_hash("T1", "501000", "DEBIT", 100000, "ref-001")
        sig = compute_entry_signature(h, "T1", "secret-key-123")
        self.assertNotEqual(h, sig)
        self.assertEqual(len(sig), 64)

    def test_verify_chain_valid(self):
        """Chainage valide sur 3 écritures."""
        entries = [
            {"id": "e1", "tenant_id": "T1", "account_code": "501000", "direction": "DEBIT",
             "amount_xof": 100000, "reference": "ref-001"},
            {"id": "e2", "tenant_id": "T1", "account_code": "401000", "direction": "CREDIT",
             "amount_xof": 100000, "reference": "ref-002"},
            {"id": "e3", "tenant_id": "T1", "account_code": "701000", "direction": "CREDIT",
             "amount_xof": 5000, "reference": "ref-003"},
        ]
        # Calculer les hash chainés
        prev = ""
        for entry in entries:
            h = compute_entry_hash(
                entry["tenant_id"], entry["account_code"], entry["direction"],
                entry["amount_xof"], entry["reference"], prev,
            )
            entry["entry_hash"] = h
            prev = h

        results = verify_chain(entries)
        self.assertTrue(all(r["is_valid"] for r in results))

    def test_verify_chain_tampered(self):
        """Une entrée altérée est détectée."""
        entries = [
            {"id": "e1", "tenant_id": "T1", "account_code": "501000", "direction": "DEBIT",
             "amount_xof": 100000, "reference": "ref-001"},
            {"id": "e2", "tenant_id": "T1", "account_code": "401000", "direction": "CREDIT",
             "amount_xof": 100000, "reference": "ref-002"},
        ]
        # Calculer les hash
        h1 = compute_entry_hash("T1", "501000", "DEBIT", 100000, "ref-001", "")
        h2 = compute_entry_hash("T1", "401000", "CREDIT", 100000, "ref-002", h1)
        entries[0]["entry_hash"] = h1
        entries[1]["entry_hash"] = h2

        # Altérer la deuxième entrée
        entries[1]["amount_xof"] = 999999  # Altération

        results = verify_chain(entries)
        self.assertTrue(results[0]["is_valid"])  # La première est OK
        self.assertFalse(results[1]["is_valid"])  # La deuxième est invalide

    def test_merkle_root_single(self):
        """Un seul hash = la racine."""
        root = compute_merkle_root(["abc123"])
        self.assertEqual(root, "abc123")

    def test_merkle_root_two(self):
        """Deux hash = hash de leur concaténation."""
        import hashlib
        a = "aaa"
        b = "bbb"
        expected = hashlib.sha256((a + b).encode()).hexdigest()
        root = compute_merkle_root([a, b])
        self.assertEqual(root, expected)

    def test_merkle_root_four(self):
        """Quatre hash = arbre binaire."""
        import hashlib
        hashes = ["a", "b", "c", "d"]
        ab = hashlib.sha256((hashes[0] + hashes[1]).encode()).hexdigest()
        cd = hashlib.sha256((hashes[2] + hashes[3]).encode()).hexdigest()
        expected = hashlib.sha256((ab + cd).encode()).hexdigest()
        root = compute_merkle_root(hashes)
        self.assertEqual(root, expected)

    def test_merkle_root_odd(self):
        """Nombre impair : le dernier est dupliqué."""
        import hashlib
        hashes = ["a", "b", "c"]
        ab = hashlib.sha256((hashes[0] + hashes[1]).encode()).hexdigest()
        cc = hashlib.sha256((hashes[2] + hashes[2]).encode()).hexdigest()
        expected = hashlib.sha256((ab + cc).encode()).hexdigest()
        root = compute_merkle_root(hashes)
        self.assertEqual(root, expected)

    def test_verify_day_balance(self):
        """Journée équilibrée."""
        self.assertTrue(verify_day_balance(1000000, 1000000))
        self.assertFalse(verify_day_balance(1000000, 999999))
