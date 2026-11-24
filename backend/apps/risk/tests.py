from django.test import TestCase

from .services import auto_freeze_if_high, score


class RiskScoringTests(TestCase):
    def test_low_amount_returns_none(self):
        alert = score(user_id="u1", order_id="o1", amount_xof=10_000)
        self.assertIsNone(alert)

    def test_bulk_buy_medium(self):
        alert = score(user_id="u1", order_id="o1", amount_xof=1_000_000, bulk_buy=True)
        self.assertIsNotNone(alert)
        self.assertEqual(alert.severity, "MEDIUM")

    def test_combinations_high_with_freeze(self):
        alert = score(
            user_id="u1", order_id="o1", amount_xof=10_000_001,
            bulk_buy=True, rapid_fire=True,
            structuring_suspect=True, high_value_cash_out=True)
        self.assertGreaterEqual(alert.score, 80)
        self.assertEqual(alert.severity, "HIGH")
        self.assertTrue(auto_freeze_if_high(alert))
