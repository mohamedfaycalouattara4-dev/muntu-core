"""Tests du middleware tenant — I2 isolation forte."""
from django.test import TestCase, RequestFactory, override_settings
from apps.tenancy.models import Institution, InstitutionStatus
from apps.core.middleware.tenant_middleware import TenantMiddleware
from apps.core.tenant_context import get_tenant_id, clear_tenant_id


class TenantMiddlewareTests(TestCase):
    """Tests du middleware d'extraction tenant."""

    def setUp(self):
        self.factory = RequestFactory()
        self.inst = Institution.objects.create(
            name="Test Tenant",
            slug="test-tenant-mw",
            country_code="BF",
            status=InstitutionStatus.ACTIVE,
        )
        self.middleware = TenantMiddleware(lambda request: _mock_response())

    def test_header_extraction(self):
        request = self.factory.get("/api/v1/members/", HTTP_X_TENANT_ID=self.inst.id)
        response = self.middleware(request)
        self.assertEqual(response.status_code, 200)

    def test_missing_tenant_returns_400(self):
        request = self.factory.get("/api/v1/members/")
        response = self.middleware(request)
        self.assertEqual(response.status_code, 400)

    def test_inactive_tenant_returns_403(self):
        inst = Institution.objects.create(
            name="Suspended",
            slug="suspended-tenant",
            country_code="BF",
            status=InstitutionStatus.SUSPENDED,
        )
        request = self.factory.get("/api/v1/members/", HTTP_X_TENANT_ID=inst.id)
        response = self.middleware(request)
        self.assertEqual(response.status_code, 403)

    def test_unknown_tenant_returns_404(self):
        request = self.factory.get("/api/v1/members/", HTTP_X_TENANT_ID="unknown-tenant-id")
        response = self.middleware(request)
        self.assertEqual(response.status_code, 404)

    def test_exempt_paths(self):
        request = self.factory.get("/health/")
        response = self.middleware(request)
        self.assertEqual(response.status_code, 200)

    def test_context_cleared_after_request(self):
        request = self.factory.get("/api/v1/members/", HTTP_X_TENANT_ID=self.inst.id)
        self.middleware(request)
        # Après la requête, le contexte est nettoyé
        self.assertIsNone(get_tenant_id())


def _mock_response():
    """Réponse fictive pour le middleware."""
    from django.http import JsonResponse
    return JsonResponse({"ok": True})
