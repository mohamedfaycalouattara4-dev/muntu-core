"""Tests des opérations de caisse."""
from django.test import TestCase
from apps.teller.models import (
    TellerSession, TellerSessionStatus, TellerOperationType,
)
from apps.tenancy.models import Institution, InstitutionStatus
from apps.teller.services.operations import process_teller_operation
from apps.core.tenant_context import set_tenant_id, clear_tenant_id


class TellerOperationTests(TestCase):
    """Tests des opérations de caisse."""

    def setUp(self):
        self.inst = Institution.objects.create(
            name="Test Bank", slug="test-teller-bank", country_code="BF",
            status=InstitutionStatus.ACTIVE,
        )
        self.session = TellerSession.objects.create(
            tenant_id=self.inst.id,
            branch_code="HQ",
            teller_id="TELLER-001",
            status=TellerSessionStatus.OPENING,
            opening_balance=0,
        )
        # Ouvrir la session
        self.session.open(dotation=1_000_000, opened_by="ADMIN-001")
        set_tenant_id(self.inst.id)

    def tearDown(self):
        clear_tenant_id()

    def test_deposit_operation(self):
        """Dépôt de caisse."""
        result = process_teller_operation(
            session_id=self.session.id,
            operation_type="DEPOSIT",
            amount=500_000,
            counterparty_member_id="MEM-001",
            performed_by="TELLER-001",
        )
        self.assertEqual(result["type"], "DEPOSIT")
        self.assertEqual(result["amount"], 500_000)
        self.assertEqual(result["current_balance"], 1_500_000)

    def test_withdrawal_operation(self):
        """Retrait de caisse."""
        process_teller_operation(
            session_id=self.session.id,
            operation_type="DEPOSIT",
            amount=500_000,
            counterparty_member_id="MEM-001",
            performed_by="TELLER-001",
        )
        result = process_teller_operation(
            session_id=self.session.id,
            operation_type="WITHDRAWAL",
            amount=200_000,
            counterparty_member_id="MEM-002",
            performed_by="TELLER-001",
        )
        self.assertEqual(result["type"], "WITHDRAWAL")
        self.assertEqual(result["current_balance"], 1_300_000)  # 1M + 500k - 200k

    def test_invalid_amount_raises(self):
        """Montant invalide → ValueError."""
        with self.assertRaises(ValueError):
            process_teller_operation(
                session_id=self.session.id,
                operation_type="DEPOSIT",
                amount=0,
                counterparty_member_id="",
                performed_by="TELLER-001",
            )

    def test_closed_session_raises(self):
        """Session scellée → PermissionError."""
        self.session.seal(counted=1_000_000, sealed_by="ADMIN", merkle_root="abc123")
        with self.assertRaises(PermissionError):
            process_teller_operation(
                session_id=self.session.id,
                operation_type="DEPOSIT",
                amount=100_000,
                counterparty_member_id="",
                performed_by="TELLER-001",
            )

    def test_operation_count_increments(self):
        """Le compteur d'opérations s'incrémente."""
        process_teller_operation(self.session.id, "DEPOSIT", 100_000, "", "T1")
        process_teller_operation(self.session.id, "DEPOSIT", 200_000, "", "T1")
        process_teller_operation(self.session.id, "WITHDRAWAL", 50_000, "", "T1")
        self.session.refresh_from_db()
        self.assertEqual(self.session.operation_count, 3)

    def test_session_totals(self):
        """Les totaux par type sont corrects."""
        process_teller_operation(self.session.id, "DEPOSIT", 300_000, "", "T1")
        process_teller_operation(self.session.id, "DEPOSIT", 200_000, "", "T1")
        process_teller_operation(self.session.id, "WITHDRAWAL", 100_000, "", "T1")
        self.session.refresh_from_db()
        self.assertEqual(self.session.total_deposits, 500_000)
        self.assertEqual(self.session.total_withdrawals, 100_000)
