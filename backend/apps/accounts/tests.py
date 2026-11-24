"""Accounts · OTP durci (Argon2id, anti-énumération, verrouillage) + RBAC."""
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.services import otp as otp_service

from .models import User, UserRole


class OTPFlowTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        cache.clear()

    def _pending(self, phone):
        return cache.get(otp_service._pending_key(phone))

    def test_otp_request_stores_salted_argon2_hash(self):
        phone = "+22670000001"
        r1 = self.client.post(reverse("otp-request"), {"phone": phone}, format="json")
        self.assertEqual(r1.status_code, 200)
        stored = self._pending(phone)
        self.assertIsNotNone(stored)
        # Le code en clair n'est jamais stocké et le sel est unique par demande.
        self.assertEqual(len(stored["code"]), 64)
        self.assertEqual(len(stored["salt"]), 32)
        self.assertEqual(stored["tries"], 0)

    def test_otp_request_is_indistinguishable_for_unknown_numbers(self):
        """Anti-énumération : même corps, même statut, compte connu ou non."""
        known = self.client.post(reverse("otp-request"),
                                 {"phone": "+22670000010"}, format="json")
        User.objects.create_user(email="k@k.bf", phone="+22670000011",
                                 roles=[UserRole.BUYER], display_name="K")
        unknown = self.client.post(reverse("otp-request"),
                                   {"phone": "+22670000011"}, format="json")
        self.assertEqual(known.status_code, unknown.status_code)
        self.assertEqual(known.data, unknown.data)

    def test_otp_verify_success_and_failure(self):
        phone = "+22670000003"
        code = otp_service.request_otp(phone).code

        bad = self.client.post(reverse("otp-verify"),
                               {"phone": phone, "code": "000000"}, format="json")
        self.assertEqual(bad.status_code, 401)
        self.assertEqual(self._pending(phone)["tries"], 1)

        ok = self.client.post(reverse("otp-verify"),
                              {"phone": phone, "code": code}, format="json")
        self.assertEqual(ok.status_code, 200)
        self.assertIn("access", ok.data)
        self.assertIn("refresh", ok.data)
        # Consommation unique.
        self.assertIsNone(self._pending(phone))

    def test_otp_verify_unknown_code_is_generic(self):
        """Un code absent et un code faux répondent exactement pareil."""
        r = self.client.post(reverse("otp-verify"),
                             {"phone": "+22670000004", "code": "123456"}, format="json")
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.data["detail"], "Code invalide ou expiré.")

    def test_progressive_lockout_after_repeated_failures(self):
        phone = "+22670000005"
        otp_service.request_otp(phone)
        statuses = []
        for _ in range(5):
            statuses.append(self.client.post(
                reverse("otp-verify"), {"phone": phone, "code": "000000"},
                format="json").status_code)
        self.assertIn(429, statuses)
        blocked = self.client.post(reverse("otp-verify"),
                                   {"phone": phone, "code": "000000"}, format="json")
        self.assertEqual(blocked.status_code, 429)
        self.assertTrue(int(blocked["Retry-After"]) > 0)



class RBACTests(TestCase):
    def test_admin_role_block_buyer_endpoint(self):
        buyer = User.objects.create_user(
            email="b@k.bf", phone="+22670000002", roles=[UserRole.BUYER], display_name="B"
        )
        client = APIClient()
        client.force_authenticate(user=buyer)
        r = client.post(reverse("admin-freeze"))
        self.assertEqual(r.status_code, 403)
