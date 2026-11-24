"""Tests des opérations d'épargne (dépôt / retrait)."""
from django.test import TestCase
from apps.savings.models import (
    SavingsProduct, SavingsAccount, SavingsAccountStatus,
    SavingsProductType, InterestFrequency,
)
from apps.tenancy.models import Institution, InstitutionStatus
from apps.savings.services.operations import deposit, withdraw
from apps.core.tenant_context import set_tenant_id, clear_tenant_id


class DepositTests(TestCase):
    """Tests du dépôt d'épargne."""

    def setUp(self):
        self.inst = Institution.objects.create(
            name="Test Bank", slug="test-dep-bank", country_code="BF",
            status=InstitutionStatus.ACTIVE,
        )
        self.product = SavingsProduct.objects.create(
            tenant_id=self.inst.id,
            name="Épargne A",
            product_type=SavingsProductType.CURRENT,
        )
        self.account = SavingsAccount.objects.create(
            tenant_id=self.inst.id,
            member_id="MEM001",
            product=self.product,
            account_number="SA-DEP-001",
            status=SavingsAccountStatus.ACTIVE,
        )
        set_tenant_id(self.inst.id)

    def tearDown(self):
        clear_tenant_id()

    def test_basic_deposit(self):
        """Dépôt simple."""
        result = deposit(self.account.id, 500_000, "U1")
        self.assertEqual(result["operation"], "DEPOSIT")
        self.assertEqual(result["amount"], 500_000)
        self.assertEqual(result["status"], "COMPLETED")
        self.assertIn("SA-DEP-001", result["account_number"])

    def test_deposit_invalid_amount(self):
        """Montant invalide → ValueError."""
        with self.assertRaises(ValueError):
            deposit(self.account.id, 0, "U1")
        with self.assertRaises(ValueError):
            deposit(self.account.id, -1000, "U1")

    def test_deposit_inactive_account(self):
        """Compte inactif → PermissionError."""
        self.account.status = SavingsAccountStatus.BLOCKED
        self.account.save()
        with self.assertRaises(PermissionError):
            deposit(self.account.id, 100_000, "U1")

    def test_deposit_ledger_reference(self):
        """Chaque dépôt génère une référence grand livre."""
        result = deposit(self.account.id, 250_000, "U1")
        self.assertIn("SVD-", result["ledger_reference"])


class WithdrawalTests(TestCase):
    """Tests du retrait d'épargne."""

    def setUp(self):
        self.inst = Institution.objects.create(
            name="Test Bank", slug="test-wd-bank", country_code="BF",
            status=InstitutionStatus.ACTIVE,
        )
        self.product = SavingsProduct.objects.create(
            tenant_id=self.inst.id,
            name="Épargne B",
            product_type=SavingsProductType.CURRENT,
            min_withdrawal=5_000,
            daily_withdrawal_limit=500_000,
        )
        self.account = SavingsAccount.objects.create(
            tenant_id=self.inst.id,
            member_id="MEM002",
            product=self.product,
            account_number="SA-WD-001",
            status=SavingsAccountStatus.ACTIVE,
        )
        set_tenant_id(self.inst.id)

    def tearDown(self):
        clear_tenant_id()

    def test_basic_withdrawal(self):
        """Retrait simple."""
        result = withdraw(self.account.id, 100_000, "U1")
        self.assertEqual(result["operation"], "WITHDRAWAL")
        self.assertEqual(result["amount"], 100_000)
        self.assertEqual(result["status"], "COMPLETED")

    def test_withdrawal_below_minimum(self):
        """Retrait sous le minimum → ValueError."""
        with self.assertRaises(ValueError):
            withdraw(self.account.id, 1_000, "U1")  # min = 5 000

    def test_withdrawal_invalid_amount(self):
        """Montant invalide → ValueError."""
        with self.assertRaises(ValueError):
            withdraw(self.account.id, 0, "U1")

    def test_withdrawal_inactive_account(self):
        """Compte inactif → PermissionError."""
        self.account.status = SavingsAccountStatus.CLOSED
        self.account.save()
        with self.assertRaises(PermissionError):
            withdraw(self.account.id, 100_000, "U1")

    def test_withdrawal_no_minimum(self):
        """Retrait sans minimum de retrait configuré."""
        self.product.min_withdrawal = 0
        self.product.save()
        result = withdraw(self.account.id, 1, "U1")
        self.assertEqual(result["status"], "COMPLETED")
