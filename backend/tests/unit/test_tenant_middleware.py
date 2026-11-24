"""Tests unitaires pour le middleware TenantMiddleware (Phase 00)."""
from __future__ import annotations

import pytest
from django.http import HttpResponse
from django.test import RequestFactory

from apps.core.middleware.tenant_middleware import TenantMiddleware
from apps.core.tenant_context import clear_tenant_id, get_tenant_id


@pytest.fixture
def request_factory():
    """Fixture pour créer des requêtes HTTP de test."""
    return RequestFactory()


@pytest.fixture
def dummy_get_response():
    """Fixture pour une fonction get_response minimale."""
    def get_response(request):
        return HttpResponse("OK")
    return get_response


class TestTenantMiddleware:
    """Tests du middleware TenantMiddleware."""

    def test_middleware_extracts_tenant_id_from_header(self, request_factory, dummy_get_response):
        """Vérifie que le middleware extrait le tenant_id de l'en-tête X-Tenant-ID."""
        middleware = TenantMiddleware(dummy_get_response)

        request = request_factory.get("/", HTTP_X_TENANT_ID="institution-123")
        clear_tenant_id()

        response = middleware(request)

        # Après la requête, le contexte doit être réinitialisé
        assert get_tenant_id() is None
        assert response.status_code == 200

    def test_middleware_extracts_tenant_id_from_subdomain(self, request_factory, dummy_get_response):
        """Vérifie que le middleware extrait le tenant_id du sous-domaine."""
        middleware = TenantMiddleware(dummy_get_response)

        request = request_factory.get("/", HTTP_HOST="institution-456.muntu.local")
        clear_tenant_id()

        response = middleware(request)

        # Après la requête, le contexte doit être réinitialisé
        assert get_tenant_id() is None
        assert response.status_code == 200

    def test_middleware_clears_tenant_id_after_request(self, request_factory, dummy_get_response):
        """Vérifie que le middleware réinitialise le tenant_id après la requête."""
        middleware = TenantMiddleware(dummy_get_response)

        request = request_factory.get("/", HTTP_X_TENANT_ID="institution-789")
        clear_tenant_id()

        assert get_tenant_id() is None
        middleware(request)
        assert get_tenant_id() is None

    def test_middleware_handles_missing_tenant_id(self, request_factory, dummy_get_response):
        """Vérifie que le middleware gère gracieusement l'absence de tenant_id."""
        middleware = TenantMiddleware(dummy_get_response)

        request = request_factory.get("/")
        clear_tenant_id()

        response = middleware(request)

        assert get_tenant_id() is None
        assert response.status_code == 200

    def test_middleware_header_takes_precedence_over_subdomain(self, request_factory, dummy_get_response):
        """Vérifie que l'en-tête X-Tenant-ID a priorité sur le sous-domaine."""
        middleware = TenantMiddleware(dummy_get_response)

        request = request_factory.get(
            "/",
            HTTP_X_TENANT_ID="institution-header",
            HTTP_HOST="institution-subdomain.muntu.local"
        )
        clear_tenant_id()

        response = middleware(request)

        # Après la requête, le contexte doit être réinitialisé
        assert get_tenant_id() is None
        assert response.status_code == 200

    def test_middleware_handles_exception_in_get_response(self, request_factory, dummy_get_response):
        """Vérifie que le middleware réinitialise le contexte même si get_response lève une exception."""
        def failing_get_response(request):
            raise ValueError("Test exception")

        middleware = TenantMiddleware(failing_get_response)

        request = request_factory.get("/", HTTP_X_TENANT_ID="institution-999")
        clear_tenant_id()

        with pytest.raises(ValueError):
            middleware(request)

        # Le contexte doit être réinitialisé même après une exception
        assert get_tenant_id() is None
