"""Tests du grand livre Muntu Core — double-entry, chainage HMAC, invariant I1."""
from django.test import TestCase
from .models import LedgerEntry, LedgerAccount, LedgerDirection
from .services.ledger import (
    LedgerInvariantError, post_double_entry,
    post_savings_deposit, post_savings_withdrawal,
    post_loan_disbursement, post_loan_repayment,
    post_interest_accrual, Posting,
)


class LedgerDoubleEntryTests(TestCase):
    """Tests de l'invariant partie double."""

    def test_savings_deposit_balanced(self):
        """Dépôt épargne : DEBIT == CREDIT."""
        post_savings_deposit(
            reference="SAV-001-DEP-500000",
            amount_xof=500_000,
            tenant_id="TENANT-001",
        )
        qs = LedgerEntry.objects.filter(reference="SAV-001-DEP-500000")
        debit = sum(e.amount_xof for e in qs if e.direction == "DEBIT")
        credit = sum(e.amount_xof for e in qs if e.direction == "CREDIT")
        self.assertEqual(debit, credit)
        self.assertEqual(debit, 500_000)

    def test_loan_disbursement_balanced(self):
        """Décaissement prêt : DEBIT == CREDIT."""
        post_loan_disbursement(
            reference="LOAN-001-DISB-1000000",
            amount_xof=1_000_000,
            tenant_id="TENANT-001",
        )
        qs = LedgerEntry.objects.filter(reference="LOAN-001-DISB-1000000")
        debit = sum(e.amount_xof for e in qs if e.direction == "DEBIT")
        credit = sum(e.amount_xof for e in qs if e.direction == "CREDIT")
        self.assertEqual(debit, credit)
        self.assertEqual(debit, 1_000_000)

    def test_imbalanced_raises(self):
        """Écritures déséquilibrées → LedgerInvariantError."""
        with self.assertRaises(LedgerInvariantError):
            post_double_entry("bad-ref", [
                Posting(LedgerAccount.CASH, LedgerDirection.DEBIT, 1000),
                Posting(LedgerAccount.SAVINGS_DEPOSIT, LedgerDirection.CREDIT, 999),
            ], tenant_id="TENANT-001")

    def test_zero_amount_raises(self):
        """Montants nuls → LedgerInvariantError."""
        with self.assertRaises(LedgerInvariantError):
            post_double_entry("empty", [
                Posting(LedgerAccount.CASH, LedgerDirection.DEBIT, 0),
            ], tenant_id="TENANT-001")


class LedgerChainTests(TestCase):
    """Tests du chainage HMAC (intégrité I5)."""

    def test_chain_hash_links_previous(self):
        """Chaque entrée référence le hash de la précédente."""
        post_savings_deposit(reference="SAV-CHAIN-1", amount_xof=5000, tenant_id="T1")
        post_savings_withdrawal(reference="SAV-CHAIN-2", amount_xof=3000, tenant_id="T1")
        entries = list(LedgerEntry.objects.order_by("id"))
        # Chaque entrée (sauf la première) référence le hash de la précédente
        self.assertEqual(entries[1].previous_hash, entries[0].entry_hash)
        self.assertEqual(entries[2].previous_hash, entries[1].entry_hash)
        self.assertNotEqual(entries[0].entry_hash, entries[1].entry_hash)

    def test_tenant_id_on_every_entry(self):
        """Chaque entrée porte un tenant_id (I2)."""
        post_savings_deposit(reference="SAV-TENANT-1", amount_xof=10000, tenant_id="TENANT-A")
        post_loan_disbursement(reference="LOAN-TENANT-1", amount_xof=50000, tenant_id="TENANT-B")
        entries = LedgerEntry.objects.all()
        self.assertEqual(entries.filter(tenant_id="TENANT-A").count(), 2)
        self.assertEqual(entries.filter(tenant_id="TENANT-B").count(), 2)

    def test_loan_repayment_balanced(self):
        """Règlement prêt : caisse débitée = principal + intérêt + frais."""
        post_loan_repayment(
            reference="LOAN-REP-1",
            principal_xof=100_000,
            interest_xof=15_000,
            fee_xof=2_000,
            tenant_id="TENANT-001",
        )
        qs = LedgerEntry.objects.filter(reference="LOAN-REP-1")
        debit = sum(e.amount_xof for e in qs if e.direction == "DEBIT")
        credit = sum(e.amount_xof for e in qs if e.direction == "CREDIT")
        self.assertEqual(debit, 117_000)
        self.assertEqual(credit, 117_000)

    def test_interest_accrual_balanced(self):
        """Provision intérêts : charge débitée = revenus crédités."""
        post_interest_accrual(reference="INT-ACCR-1", amount_xof=970, tenant_id="TENANT-001")
        qs = LedgerEntry.objects.filter(reference="INT-ACCR-1")
        debit = sum(e.amount_xof for e in qs if e.direction == "DEBIT")
        credit = sum(e.amount_xof for e in qs if e.direction == "CREDIT")
        self.assertEqual(debit, 970)
        self.assertEqual(credit, 970)
