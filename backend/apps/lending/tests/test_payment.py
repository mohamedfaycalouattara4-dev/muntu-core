"""Tests du règlement de prêt — imputation stricte."""
from django.test import TestCase
from apps.lending.services.payment import (
    process_payment, compute_late_fee, compute_outstanding,
)


class PaymentAllocationTests(TestCase):
    """Tests de l'imputation stricte : frais → intérêt → principal."""

    def test_full_payment_allocation(self):
        """Paiement complet : frais + intérêt + principal."""
        result = process_payment(
            loan_id="L1", installment_id="I1",
            amount=100_000, payment_method="CASH", performed_by="U1",
            late_fee_amount=5_000, interest_amount=15_000, principal_amount=80_000,
        )
        self.assertEqual(result["late_fee_applied"], 5_000)
        self.assertEqual(result["interest_applied"], 15_000)
        self.assertEqual(result["principal_applied"], 80_000)
        self.assertEqual(result["unallocated"], 0)
        self.assertEqual(result["status"], "FULLY_ALLOCATED")

    def test_partial_payment_principal_only(self):
        """Paiement insuffisant pour couvrir tout → principal réduit."""
        result = process_payment(
            loan_id="L1", installment_id="I1",
            amount=50_000, payment_method="CASH", performed_by="U1",
            late_fee_amount=5_000, interest_amount=15_000, principal_amount=80_000,
        )
        self.assertEqual(result["late_fee_applied"], 5_000)
        self.assertEqual(result["interest_applied"], 15_000)
        self.assertEqual(result["principal_applied"], 30_000)  # 50k - 5k - 15k
        self.assertEqual(result["status"], "FULLY_ALLOCATED")

    def test_partial_payment_interest_principal_only(self):
        """Paiement couvre frais + partie intérêt."""
        result = process_payment(
            loan_id="L1", installment_id="I1",
            amount=15_000, payment_method="TRANSFER", performed_by="U1",
            late_fee_amount=5_000, interest_amount=15_000, principal_amount=80_000,
        )
        self.assertEqual(result["late_fee_applied"], 5_000)
        self.assertEqual(result["interest_applied"], 10_000)
        self.assertEqual(result["principal_applied"], 0)
        self.assertEqual(result["unallocated"], 0)

    def test_no_dues_all_principal(self):
        """Pas de frais ni d'intérêt → tout va au principal."""
        result = process_payment(
            loan_id="L1", installment_id="I1",
            amount=100_000, payment_method="CASH", performed_by="U1",
            late_fee_amount=0, interest_amount=0, principal_amount=100_000,
        )
        self.assertEqual(result["late_fee_applied"], 0)
        self.assertEqual(result["interest_applied"], 0)
        self.assertEqual(result["principal_applied"], 100_000)

    def test_invalid_amount_raises(self):
        """Montant <= 0 lève ValueError."""
        with self.assertRaises(ValueError):
            process_payment("L1", "I1", 0, "CASH", "U1")
        with self.assertRaises(ValueError):
            process_payment("L1", "I1", -1000, "CASH", "U1")

    def test_allocation_order_guaranteed(self):
        """L'ordre d'allocation est toujours respecté."""
        result = process_payment(
            loan_id="L1", installment_id="I1",
            amount=7_000, payment_method="CASH", performed_by="U1",
            late_fee_amount=5_000, interest_amount=10_000, principal_amount=85_000,
        )
        # 7000: d'abord 5000 frais, puis 2000 intérêt, 0 principal
        self.assertEqual(result["late_fee_applied"], 5_000)
        self.assertEqual(result["interest_applied"], 2_000)
        self.assertEqual(result["principal_applied"], 0)


class LateFeeTests(TestCase):
    """Tests du calcul des frais de retard."""

    def test_within_grace_period(self):
        """Retard dans la période de tolérance → pas de frais."""
        self.assertEqual(compute_late_fee(100_000, 2, 3, 0.01), 0)

    def test_basic_late_fee(self):
        """10 jours de retard, 1% par mois."""
        fee = compute_late_fee(100_000, 40, 3, 0.01)
        # 37 jours effectifs / 30 = 1.23 mois × 1% × 100 000 = 1233
        self.assertEqual(fee, 1233)

    def test_exact_grace_period(self):
        """Exactement grace_period → pas de frais."""
        self.assertEqual(compute_late_fee(100_000, 3, 3, 0.01), 0)


class OutstandingTests(TestCase):
    """Tests du calcul du restant dû."""

    def test_no_payments(self):
        result = compute_outstanding(1_000_000, 0, 100_000, 0)
        self.assertEqual(result["outstanding_principal"], 1_000_000)
        self.assertEqual(result["outstanding_interest"], 100_000)

    def test_partial_payment(self):
        result = compute_outstanding(1_000_000, 400_000, 100_000, 30_000)
        self.assertEqual(result["outstanding_principal"], 600_000)
        self.assertEqual(result["outstanding_interest"], 70_000)

    def test_fully_repaid(self):
        result = compute_outstanding(1_000_000, 1_000_000, 100_000, 100_000)
        self.assertEqual(result["outstanding_principal"], 0)
        self.assertEqual(result["outstanding_interest"], 0)

    def test_overpayment_not_negative(self):
        """Le restant ne peut pas être négatif."""
        result = compute_outstanding(1_000_000, 1_500_000, 100_000, 150_000)
        self.assertEqual(result["outstanding_principal"], 0)
        self.assertEqual(result["outstanding_interest"], 0)
