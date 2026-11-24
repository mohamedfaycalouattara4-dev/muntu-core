"""Tests du scoring de risque crédit — fonctions pures, déterministes."""
from django.test import TestCase
from apps.lending.services.risk import compute_risk_score, compute_impairment_provision


class RiskScoreTests(TestCase):
    """Tests du scoring de risque."""

    def test_excellent_profile(self):
        """Client ancien, bon historique, garanties → classe A."""
        result = compute_risk_score(
            member_age_months=24,
            previous_loans=5,
            previous_defaults=0,
            loan_amount=1_000_000,
            estimated_monthly_income=500_000,
            has_guarantor=True,
            has_collateral=True,
            collateral_value=2_000_000,
        )
        self.assertEqual(result["risk_class"], "A")
        self.assertGreater(result["score"], 80)

    def test_poor_profile(self):
        """Nouveau client, defaults, pas de garanties → classe E."""
        result = compute_risk_score(
            member_age_months=1,
            previous_loans=2,
            previous_defaults=2,
            loan_amount=5_000_000,
            estimated_monthly_income=100_000,
            has_guarantor=False,
            has_collateral=False,
            collateral_value=0,
        )
        self.assertIn(result["risk_class"], ("D", "E"))
        self.assertLess(result["score"], 50)

    def test_new_client(self):
        """Premier prêt, client récent → classe B ou C."""
        result = compute_risk_score(
            member_age_months=6,
            previous_loans=0,
            previous_defaults=0,
            loan_amount=500_000,
            estimated_monthly_income=200_000,
            has_guarantor=True,
            has_collateral=False,
            collateral_value=0,
        )
        self.assertIn(result["risk_class"], ("B", "C"))

    def test_high_debt_ratio(self):
        """Ratio endettement > 12 → pénalité forte."""
        result = compute_risk_score(
            member_age_months=24,
            previous_loans=3,
            previous_defaults=0,
            loan_amount=2_000_000,
            estimated_monthly_income=100_000,  # ratio = 20
            has_guarantor=False,
            has_collateral=False,
            collateral_value=0,
        )
        self.assertLess(result["score"], 70)

    def test_good_collateral_coverage(self):
        """Couverture collatérale > 1.5 → bonus."""
        result_no_coll = compute_risk_score(
            24, 2, 0, 1_000_000, 500_000, False, False, 0,
        )
        result_with_coll = compute_risk_score(
            24, 2, 0, 1_000_000, 500_000, False, True, 1_500_000,
        )
        self.assertGreater(result_with_coll["score"], result_no_coll["score"])

    def test_score_bounded(self):
        """Le score est toujours entre 0 et 100."""
        result = compute_risk_score(1, 10, 10, 100_000_000, 100, False, False, 0)
        self.assertGreaterEqual(result["score"], 0)
        self.assertLessEqual(result["score"], 100)


class ImpairmentProvisionTests(TestCase):
    """Tests de la provision pour dépréciation."""

    def test_class_a_no_provision(self):
        """Classe A = pas de provision."""
        self.assertEqual(compute_impairment_provision(1_000_000, 0, "A"), 0)

    def test_class_c_20_percent(self):
        """Classe C = 20% de provision."""
        self.assertEqual(compute_impairment_provision(1_000_000, 15, "C"), 200_000)

    def test_class_d_50_percent(self):
        """Classe D = 50% de provision."""
        self.assertEqual(compute_impairment_provision(1_000_000, 45, "D"), 500_000)

    def test_class_e_100_percent(self):
        """Classe E = 100% de provision."""
        self.assertEqual(compute_impairment_provision(1_000_000, 120, "E"), 1_000_000)

    def test_escalation_by_days(self):
        """Si jours de retard dépassent le seuil, la provision monte."""
        # Classe A mais 100 jours de retard → 100%
        self.assertEqual(compute_impairment_provision(1_000_000, 100, "A"), 1_000_000)
        # Classe B mais 50 jours de retard → 50%
        self.assertEqual(compute_impairment_provision(1_000_000, 50, "B"), 500_000)
