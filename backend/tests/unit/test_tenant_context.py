"""Tests unitaires pour la gestion du contexte tenant_id (Phase 00)."""
from __future__ import annotations

import pytest

from apps.core.tenant_context import (
    TenantContext,
    clear_tenant_id,
    get_tenant_id,
    require_tenant_id,
    set_tenant_id,
)


class TestTenantContext:
    """Tests du gestionnaire de contexte tenant_id."""

    def test_set_and_get_tenant_id(self):
        """Vérifie que set_tenant_id et get_tenant_id fonctionnent correctement."""
        tenant_id = "institution-123"
        set_tenant_id(tenant_id)
        assert get_tenant_id() == tenant_id

    def test_get_tenant_id_returns_none_by_default(self):
        """Vérifie que get_tenant_id retourne None par défaut."""
        clear_tenant_id()
        assert get_tenant_id() is None

    def test_clear_tenant_id(self):
        """Vérifie que clear_tenant_id réinitialise le contexte."""
        set_tenant_id("institution-123")
        clear_tenant_id()
        assert get_tenant_id() is None

    def test_set_tenant_id_raises_on_invalid_input(self):
        """Vérifie que set_tenant_id lève une exception pour une entrée invalide."""
        with pytest.raises(ValueError):
            set_tenant_id("")

        with pytest.raises(ValueError):
            set_tenant_id(None)

        with pytest.raises(ValueError):
            set_tenant_id(123)  # Non-string

    def test_require_tenant_id_returns_tenant_id(self):
        """Vérifie que require_tenant_id retourne le tenant_id."""
        tenant_id = "institution-456"
        set_tenant_id(tenant_id)
        assert require_tenant_id() == tenant_id

    def test_require_tenant_id_raises_when_not_set(self):
        """Vérifie que require_tenant_id lève une exception si aucun tenant_id n'est défini."""
        clear_tenant_id()
        with pytest.raises(RuntimeError, match="Aucun tenant_id défini"):
            require_tenant_id()

    def test_tenant_context_manager(self):
        """Vérifie que TenantContext fonctionne comme context manager."""
        clear_tenant_id()
        assert get_tenant_id() is None

        with TenantContext("institution-789"):
            assert get_tenant_id() == "institution-789"

        assert get_tenant_id() is None

    def test_tenant_context_manager_nested(self):
        """Vérifie que TenantContext fonctionne correctement en contextes imbriqués."""
        clear_tenant_id()

        with TenantContext("institution-1"):
            assert get_tenant_id() == "institution-1"

            with TenantContext("institution-2"):
                assert get_tenant_id() == "institution-2"

            assert get_tenant_id() == "institution-1"

        assert get_tenant_id() is None

    def test_tenant_context_manager_exception_handling(self):
        """Vérifie que TenantContext réinitialise le contexte même en cas d'exception."""
        clear_tenant_id()

        try:
            with TenantContext("institution-999"):
                assert get_tenant_id() == "institution-999"
                raise ValueError("Test exception")
        except ValueError:
            pass

        assert get_tenant_id() is None
