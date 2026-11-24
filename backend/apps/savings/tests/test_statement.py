"""Tests du relevé d'épargne."""
from django.test import TestCase
from apps.savings.models import (
    SavingsProduct, SavingsAccount, SavingsAccountStatus,
    SavingsProductType, InterestFrequency, InterestAccrual,
)
from apps.tenancy.models import Institution, InstitutionStatus
from apps.savings.services.statement import compute_statement
from apps.core.tenant_context import set_tenant_id, clear_tenant_id


class StatementTests(TestCase):
    """Tests du calcul de relevé d'épargne."""

    def setUp(self):
        self.inst = Institution.objects.create(
            name="Test Bank", slug="test-stmt-bank", country_code="BF",
            status=InstitutionStatus.ACTIVE,
        )
        self.product = SavingsProduct.objects.create(
            tenant_id=self.inst.id,
            name="Épargne A",
            product_type=SavingsProductType.CURRENT,
            annual_interest_rate=0.035,
            interest_frequency=InterestFrequency.MONTHLY,
        )
        self.account = SavingsAccount.objects.create(
            tenant_id=self.inst.id,
            member_id="MEM001",
            product=self.product,
            account_number="SA-0001",
            status=SavingsAccountStatus.ACTIVE,
        )
        set_tenant_id(self.inst.id)

    def tearDown(self):
        clear_tenant_id()

    def test_statement_no_accruals(self):
        """Relevé sans aucun accrual → zéro intérêts."""
        result = compute_statement(self.account.id)
        self.assertEqual(result["total_interest_accrued"], 0)
        self.assertEqual(result["total_interest_pending"], 0)
        self.assertEqual(result["account_number"], "SA-0001")

    def test_statement_with_accruals(self):
        """Relevé avec des accruals."""
        from decimal import Decimal
        for i in range(5):
            InterestAccrual.objects.create(
                tenant_id=self.inst.id,
                account=self.account,
                accrual_date=f"2024-01-{i+1:02d}",
                opening_balance=1_000_000,
                daily_rate=Decimal("0.0000972"),
                interest_amount=97,
                cumulative_interest=97 * (i + 1),
                is_credited=(i < 3),
            )

        result = compute_statement(self.account.id)
        self.assertEqual(result["total_interest_accrued"], 485)  # 97 × 5
        self.assertEqual(result["total_interest_credited"], 291)  # 97 × 3
        self.assertEqual(result["total_interest_pending"], 194)  # 97 × 2

    def test_statement_with_period_filter(self):
        """Filtrage par période."""
        from decimal import Decimal
        for i in range(10):
            InterestAccrual.objects.create(
                tenant_id=self.inst.id,
                account=self.account,
                accrual_date=f"2024-01-{i+1:02d}",
                opening_balance=1_000_000,
                daily_rate=Decimal("0.0000972"),
                interest_amount=97,
                cumulative_interest=97 * (i + 1),
                is_credited=True,
            )

        result = compute_statement(self.account.id, period_start="2024-01-05", period_end="2024-01-08")
        self.assertEqual(result["total_interest_accrued"], 388)  # 97 × 4
