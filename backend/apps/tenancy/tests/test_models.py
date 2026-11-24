"""Tests des modèles tenancy — I2 isolation forte."""
from django.test import TestCase
from apps.tenancy.models import Institution, Branch, ModuleToggle, InstitutionStatus, CurrencyCode


class InstitutionModelTests(TestCase):
    """Tests du modèle Institution."""

    def test_create_institution(self):
        inst = Institution.objects.create(
            name="Caisse Populaire de Ouaga",
            slug="cp-ouaga",
            country_code="BF",
            currency=CurrencyCode.XOF,
        )
        self.assertEqual(inst.status, InstitutionStatus.PENDING)
        self.assertFalse(inst.is_active())
        self.assertEqual(len(inst.id), 26)  # ULID

    def test_activate_institution(self):
        inst = Institution.objects.create(
            name="Test Bank",
            slug="test-bank",
            country_code="SN",
        )
        inst.activate()
        self.assertEqual(inst.status, InstitutionStatus.ACTIVE)
        self.assertTrue(inst.is_active())
        self.assertIsNotNone(inst.onboarded_at)

    def test_suspend_institution(self):
        inst = Institution.objects.create(
            name="Test Bank",
            slug="test-bank-suspend",
            country_code="CI",
            status=InstitutionStatus.ACTIVE,
        )
        inst.suspend("Non-paiement cotisation")
        self.assertEqual(inst.status, InstitutionStatus.SUSPENDED)
        self.assertFalse(inst.is_active())
        self.assertEqual(inst.suspended_reason, "Non-paiement cotisation")

    def test_archive_institution(self):
        inst = Institution.objects.create(
            name="Archived Bank",
            slug="archived-bank",
            country_code="ML",
        )
        inst.archive()
        self.assertEqual(inst.status, InstitutionStatus.ARCHIVED)

    def test_slug_unique(self):
        Institution.objects.create(name="A", slug="unique-slug", country_code="BF")
        with self.assertRaises(Exception):
            Institution.objects.create(name="B", slug="unique-slug", country_code="SN")

    def test_str_representation(self):
        inst = Institution.objects.create(
            name="Test Institution",
            slug="test-inst",
            country_code="BF",
        )
        self.assertIn("Test Institution", str(inst))


class BranchModelTests(TestCase):
    """Tests du modèle Branch."""

    def setUp(self):
        self.inst = Institution.objects.create(
            name="Test Bank",
            slug="test-branch-bank",
            country_code="BF",
        )

    def test_create_branch(self):
        branch = Branch.objects.create(
            institution=self.inst,
            name="Agence Centrale",
            code="AG01",
            is_hq=True,
        )
        self.assertTrue(branch.is_hq)
        self.assertEqual(str(branch), "AG01 — Agence Centrale (test-branch-bank)")

    def test_unique_code_per_institution(self):
        Branch.objects.create(institution=self.inst, name="A", code="AG01")
        with self.assertRaises(Exception):
            Branch.objects.create(institution=self.inst, name="B", code="AG01")


class ModuleToggleModelTests(TestCase):
    """Tests du modèle ModuleToggle."""

    def setUp(self):
        self.inst = Institution.objects.create(
            name="Test Bank",
            slug="test-module-bank",
            country_code="BF",
        )

    def test_create_and_enable_module(self):
        toggle = ModuleToggle.objects.create(
            institution=self.inst,
            module_name="savings",
            is_enabled=False,
        )
        self.assertFalse(toggle.is_enabled)
        toggle.enable()
        self.assertTrue(toggle.is_enabled)
        self.assertIsNotNone(toggle.enabled_at)

    def test_disable_module(self):
        toggle = ModuleToggle.objects.create(
            institution=self.inst,
            module_name="lending",
            is_enabled=True,
        )
        toggle.disable()
        self.assertFalse(toggle.is_enabled)

    def test_unique_module_per_institution(self):
        ModuleToggle.objects.create(institution=self.inst, module_name="savings")
        with self.assertRaises(Exception):
            ModuleToggle.objects.create(institution=self.inst, module_name="savings")
