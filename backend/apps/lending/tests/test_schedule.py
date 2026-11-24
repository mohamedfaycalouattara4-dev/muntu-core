"""Tests du calcul d'échéancier — fonctions pures, déterministes.

Jeu de tests validé à la main :
- Prêt 10 000 000 XOF, taux 15% annuel, 12 mois, mensuel, flat
- Prêt 5 000 000 XOF, taux 12% annuel, 6 mois, mensuel, declining
- Prêt 3 000 000 XOF, taux 18% annuel, 3 mois, mensuel, french
"""
from decimal import Decimal
from django.test import TestCase
from apps.lending.services.schedule import (
    compute_schedule, compute_flat_schedule, compute_declining_schedule,
    compute_french_schedule,
)


class FlatScheduleTests(TestCase):
    """Échéancier flat — intérêt constant chaque période."""

    def test_basic_flat_12_months(self):
        """10 000 000 XOF, 15% annuel, 12 mois, mensuel."""
        schedule = compute_flat_schedule(
            principal=10_000_000,
            annual_rate=Decimal("0.15"),
            term_months=12,
            frequency_months=1,
        )
        self.assertEqual(len(schedule), 12)
        total_principal = sum(s.principal for s in schedule)
        self.assertEqual(total_principal, 10_000_000)
        # Chaque échéance doit avoir un intérêt > 0
        for line in schedule:
            self.assertGreater(line.interest, 0)
            self.assertGreater(line.principal, 0)

    def test_flat_6_months_5_percent(self):
        """5 000 000 XOF, 5% annuel, 6 mois."""
        schedule = compute_flat_schedule(
            principal=5_000_000,
            annual_rate=Decimal("0.05"),
            term_months=6,
            frequency_months=1,
        )
        self.assertEqual(len(schedule), 6)
        total = sum(s.principal + s.interest for s in schedule)
        # Le total doit être proche de principal + intérêt total
        total_interest = 5_000_000 * 0.05 * 6 / 12  # = 125 000
        expected_total = 5_000_000 + 125_000
        self.assertAlmostEqual(total, expected_total, delta=100)

    def test_flat_single_period(self):
        """1 000 000 XOF, 10%, 3 mois, unique échéance."""
        schedule = compute_flat_schedule(
            principal=1_000_000,
            annual_rate=Decimal("0.10"),
            term_months=3,
            frequency_months=3,
        )
        self.assertEqual(len(schedule), 1)
        self.assertEqual(schedule[0].principal, 1_000_000)
        # Intérêt = 1 000 000 × 0.10 × 3/12 = 25 000
        self.assertEqual(schedule[0].interest, 25_000)

    def test_invalid_params_raises(self):
        with self.assertRaises(ValueError):
            compute_flat_schedule(0, Decimal("0.10"), 12, 1)
        with self.assertRaises(ValueError):
            compute_flat_schedule(100_000, Decimal("0.10"), 0, 1)


class DecliningScheduleTests(TestCase):
    """Échéancier dégressif — intérêt sur solde restant."""

    def test_basic_declining_6_months(self):
        """5 000 000 XOF, 12% annuel, 6 mois."""
        schedule = compute_declining_schedule(
            principal=5_000_000,
            annual_rate=Decimal("0.12"),
            term_months=6,
            frequency_months=1,
        )
        self.assertEqual(len(schedule), 6)
        total_principal = sum(s.principal for s in schedule)
        self.assertEqual(total_principal, 5_000_000)
        # Intérêts décroissants
        for i in range(1, len(schedule)):
            self.assertLessEqual(schedule[i].interest, schedule[i - 1].interest)

    def test_declining_interest_decreasing(self):
        """Vérifie que l'intérêt diminue strictement."""
        schedule = compute_declining_schedule(
            principal=10_000_000,
            annual_rate=Decimal("0.18"),
            term_months=12,
            frequency_months=1,
        )
        for i in range(1, len(schedule)):
            self.assertLess(schedule[i].interest, schedule[i - 1].interest)


class FrenchScheduleTests(TestCase):
    """Échéancier à annuité constante (méthode française)."""

    def test_basic_french_12_months(self):
        """3 000 000 XOF, 18% annuel, 3 mois."""
        schedule = compute_french_schedule(
            principal=3_000_000,
            annual_rate=Decimal("0.18"),
            term_months=3,
            frequency_months=1,
        )
        self.assertEqual(len(schedule), 3)
        total_principal = sum(s.principal for s in schedule)
        self.assertEqual(total_principal, 3_000_000)

    def test_french_zero_rate(self):
        """Taux nul — simple division."""
        schedule = compute_french_schedule(
            principal=1_000_000,
            annual_rate=Decimal("0"),
            term_months=4,
            frequency_months=1,
        )
        self.assertEqual(len(schedule), 4)
        self.assertEqual(schedule[0].interest, 0)
        self.assertEqual(sum(s.principal for s in schedule), 1_000_000)


class ScheduleIntegrationTests(TestCase):
    """Tests d'intégration — fonction d'entrée unique."""

    def test_dispatch_flat(self):
        schedule = compute_schedule(1_000_000, Decimal("0.10"), 6, 1, "FLAT")
        self.assertEqual(len(schedule), 6)

    def test_dispatch_declining(self):
        schedule = compute_schedule(1_000_000, Decimal("0.10"), 6, 1, "DECLINING")
        self.assertEqual(len(schedule), 6)

    def test_dispatch_french(self):
        schedule = compute_schedule(1_000_000, Decimal("0.10"), 6, 1, "FRENCH")
        self.assertEqual(len(schedule), 6)

    def test_invalid_method_raises(self):
        with self.assertRaises(ValueError):
            compute_schedule(1_000_000, Decimal("0.10"), 6, 1, "INVALID")

    def test_invariant_principal_sum(self):
        """Invariant fondamental : somme des principaux = montant du prêt."""
        for method in ["FLAT", "DECLINING", "FRENCH"]:
            schedule = compute_schedule(7_500_000, Decimal("0.15"), 10, 1, method)
            self.assertEqual(sum(s.principal for s in schedule), 7_500_000)
