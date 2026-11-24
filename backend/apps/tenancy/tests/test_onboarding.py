"""Tests du service d'onboarding d'institution."""
from django.test import TestCase
from apps.tenancy.models import Institution, Branch, ModuleToggle
from apps.accounting.models import ChartAccount
from apps.tenancy.services.onboarding import onboard_institution


class OnboardingTests(TestCase):
    """Tests d'onboarding d'une nouvelle institution."""

    def test_full_onboarding(self):
        """Onboarding complet : institution + HQ + plan comptable + modules."""
        result = onboard_institution(
            name="Caisse Populaire de Ouaga",
            slug="cp-ouaga",
            country_code="BF",
        )
        self.assertIn("institution_id", result)
        self.assertEqual(result["slug"], "cp-ouaga")
        self.assertEqual(result["hq_branch_code"], "HQ")
        self.assertEqual(result["status"], "ACTIVE")
        self.assertGreater(result["modules_enabled"], 0)
        self.assertGreater(result["chart_accounts"], 0)

    def test_chart_accounts_created(self):
        """Le plan comptable SFD est créé."""
        result = onboard_institution("Test Bank", "test-bank-chart")
        accounts = ChartAccount.objects.filter(tenant_id=result["institution_id"])
        self.assertGreater(accounts.count(), 10)
        # Vérifier les classes
        codes = set(accounts.values_list("code", flat=True))
        self.assertIn("101000", codes)  # Capital
        self.assertIn("501000", codes)  # Caisse principale
        self.assertIn("701000", codes)  # Intérêts perçus

    def test_default_modules_enabled(self):
        """Les modules par défaut (savings, teller, accounting) sont activés."""
        result = onboard_institution("Test Bank", "test-bank-modules")
        enabled = ModuleToggle.objects.filter(
            institution_id=result["institution_id"], is_enabled=True
        ).values_list("module_name", flat=True)
        self.assertIn("savings", enabled)
        self.assertIn("teller", enabled)
        self.assertIn("accounting", enabled)

    def test_hq_branch_created(self):
        """L'agence HQ est créée."""
        result = onboard_institution("Test Bank", "test-bank-hq")
        inst = Institution.objects.get(id=result["institution_id"])
        hq = Branch.objects.filter(institution=inst, is_hq=True).first()
        self.assertIsNotNone(hq)
        self.assertEqual(hq.code, "HQ")

    def test_invalid_params_raises(self):
        """name et slug sont requis."""
        with self.assertRaises(ValueError):
            onboard_institution("", "")
        with self.assertRaises(ValueError):
            onboard_institution("Name", "")

    def test_duplicate_slug_raises(self):
        """Le slug doit être unique."""
        onboard_institution("Bank A", "unique-slug-test")
        with self.assertRaises(Exception):
            onboard_institution("Bank B", "unique-slug-test")
