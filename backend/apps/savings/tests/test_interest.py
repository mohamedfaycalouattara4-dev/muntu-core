"""Tests du calcul d'intérêts créditeurs — fonctions pures, déterministes."""
from decimal import Decimal
from django.test import TestCase
from apps.savings.services.interest import (
    compute_daily_interest, compute_interest_for_period,
    compute_maturity_interest, compute_penalty,
    compute_daily_withdrawal_remaining,
)


class DailyInterestTests(TestCase):
    """Tests du calcul d'intérêt quotidien."""

    def test_basic_daily_interest(self):
        """1 000 000 XOF, 3.5% annuel, 360 jours."""
        result = compute_daily_interest(1_000_000, Decimal("0.035"), 360)
        # 1 000 000 × 0.035 / 360 = 97.222... → tronqué = 97
        self.assertEqual(result["interest_amount"], 97)
        self.assertGreater(result["daily_rate"], 0)

    def test_zero_balance(self):
        """Solde nul = pas d'intérêt."""
        result = compute_daily_interest(0, Decimal("0.035"))
        self.assertEqual(result["interest_amount"], 0)

    def test_zero_rate(self):
        """Taux nul = pas d'intérêt."""
        result = compute_daily_interest(1_000_000, Decimal("0"))
        self.assertEqual(result["interest_amount"], 0)

    def test_truncation_not_rounding(self):
        """L'intérêt est tronqué, pas arrondi."""
        # 1 XOF × 3.5% / 360 = 0.000097... → tronqué = 0
        result = compute_daily_interest(1, Decimal("0.035"), 360)
        self.assertEqual(result["interest_amount"], 0)

    def test_high_rate(self):
        """10 000 000 XOF, 15% annuel."""
        result = compute_daily_interest(10_000_000, Decimal("0.15"), 360)
        # 10 000 000 × 0.15 / 360 = 4166.666... → 4166
        self.assertEqual(result["interest_amount"], 4166)


class PeriodInterestTests(TestCase):
    """Tests du calcul d'intérêts sur période."""

    def test_simple_interest_30_days(self):
        """Intérêts simples sur 30 jours."""
        result = compute_interest_for_period(1_000_000, Decimal("0.035"), 30)
        expected = 97 * 30  # 97 XOF/jour × 30 jours
        self.assertEqual(result["total_interest"], expected)

    def test_compound_interest_3_days(self):
        """Intérêts composés sur 3 jours."""
        result = compute_interest_for_period(1_000_000, Decimal("0.035"), 3, compound=True)
        # Jour 1: 97 → solde 1 000 097
        # Jour 2: 97 (tronqué) → solde 1 000 194
        # Jour 3: 97 → total = 291
        self.assertGreater(result["total_interest"], 290)
        self.assertLessEqual(result["total_interest"], 295)

    def test_compound_exceeds_simple(self):
        """Les intérêts composés dépassent les intérêts simples."""
        simple = compute_interest_for_period(5_000_000, Decimal("0.10"), 30, compound=False)
        compound = compute_interest_for_period(5_000_000, Decimal("0.10"), 30, compound=True)
        self.assertGreater(compound["total_interest"], simple["total_interest"])


class MaturityInterestTests(TestCase):
    """Tests du calcul d'intérêts à l'échéance."""

    def test_basic_maturity(self):
        """5 000 000 XOF, 4% annuel, 360 jours."""
        result = compute_maturity_interest(5_000_000, Decimal("0.04"), 360)
        self.assertEqual(result, 200_000)

    def test_short_term(self):
        """10 000 000 XOF, 5% annuel, 90 jours."""
        result = compute_maturity_interest(10_000_000, Decimal("0.05"), 90)
        self.assertEqual(result, 125_000)


class PenaltyTests(TestCase):
    """Tests de la pénalité de rupture anticipée."""

    def test_basic_penalty(self):
        """1 000 000 XOF, 1% pénalité, 30 jours avant terme."""
        result = compute_penalty(1_000_000, Decimal("0.01"), 30)
        self.assertEqual(result, 10_000)

    def test_zero_penalty_rate(self):
        """Taux de pénalité nul = pas de pénalité."""
        result = compute_penalty(1_000_000, Decimal("0"), 30)
        self.assertEqual(result, 0)


class WithdrawalLimitTests(TestCase):
    """Tests de la limite journalière de retrait."""

    def test_within_limit(self):
        """Limite 500 000, retiré 200 000 → reste 300 000."""
        remaining = compute_daily_withdrawal_remaining(500_000, [200_000])
        self.assertEqual(remaining, 300_000)

    def test_exceeds_limit(self):
        """Limite 500 000, retiré 600 000 → reste 0."""
        remaining = compute_daily_withdrawal_remaining(500_000, [600_000])
        self.assertEqual(remaining, 0)

    def test_no_limit(self):
        """Limite 0 = illimité."""
        remaining = compute_daily_withdrawal_remaining(0, [1_000_000])
        self.assertEqual(remaining, 0)  # 0 signifie pas de limite

    def test_multiple_withdrawals(self):
        """Plusieurs retraits cumulés."""
        remaining = compute_daily_withdrawal_remaining(500_000, [100_000, 150_000, 50_000])
        self.assertEqual(remaining, 200_000)
