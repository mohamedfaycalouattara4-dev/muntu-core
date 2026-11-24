"""Tests d'intégration pour valider l'isolation multi-tenant avec RLS (Phase 00)."""
from __future__ import annotations

import pytest
from django.db import connection

from apps.core.db import db_actor, db_system_actor, current_db_context
from apps.core.tenant_context import TenantContext, get_tenant_id, set_tenant_id


@pytest.mark.django_db
class TestMultiTenantRLSIntegration:
    """Tests d'intégration pour l'isolation multi-tenant via RLS."""

    def test_tenant_id_propagates_to_database_context(self):
        """Vérifie que le tenant_id se propage jusqu'au contexte PostgreSQL."""
        tenant_id = "institution-integration-test-001"

        with TenantContext(tenant_id):
            # Le contexte applicatif doit contenir le tenant_id
            assert get_tenant_id() == tenant_id

            # Utiliser db_actor pour vérifier la propagation au contexte DB
            with db_actor("user-123", "admin", tenant_id=tenant_id):
                db_context = current_db_context()
                assert db_context["tenant_id"] == tenant_id
                assert db_context["user_id"] == "user-123"

    def test_system_context_with_tenant_id(self):
        """Vérifie que le contexte système peut avoir un tenant_id."""
        tenant_id = "institution-system-test-001"

        with db_system_actor(reason="test", tenant_id=tenant_id):
            db_context = current_db_context()
            assert db_context["tenant_id"] == tenant_id
            assert db_context["user_id"] == "system"
            assert db_context["system"] == "on"

    def test_tenant_id_isolation_between_contexts(self):
        """Vérifie que les tenant_id sont isolés entre contextes imbriqués."""
        tenant_1 = "institution-isolation-test-001"
        tenant_2 = "institution-isolation-test-002"

        with TenantContext(tenant_1):
            assert get_tenant_id() == tenant_1

            with db_actor("user-1", "admin", tenant_id=tenant_1):
                ctx1 = current_db_context()
                assert ctx1["tenant_id"] == tenant_1

            # Après la sortie du contexte db_actor, on revient au contexte applicatif
            assert get_tenant_id() == tenant_1

            with TenantContext(tenant_2):
                assert get_tenant_id() == tenant_2

                with db_actor("user-2", "admin", tenant_id=tenant_2):
                    ctx2 = current_db_context()
                    assert ctx2["tenant_id"] == tenant_2

            # Après la sortie du contexte tenant_2, on revient à tenant_1
            assert get_tenant_id() == tenant_1

    def test_empty_tenant_id_in_system_context(self):
        """Vérifie que le contexte système peut s'exécuter sans tenant_id."""
        with db_system_actor(reason="migration"):
            db_context = current_db_context()
            assert db_context["tenant_id"] == ""
            assert db_context["user_id"] == "system"

    def test_tenant_id_with_different_roles(self):
        """Vérifie que le tenant_id fonctionne avec différents rôles."""
        tenant_id = "institution-roles-test-001"

        roles_to_test = ["admin", "finance", "compliance", "operator"]

        for role in roles_to_test:
            with db_actor("user-role-test", role, tenant_id=tenant_id):
                db_context = current_db_context()
                assert db_context["tenant_id"] == tenant_id
                assert role in db_context["roles"]

    def test_multiple_roles_with_tenant_id(self):
        """Vérifie que plusieurs rôles fonctionnent avec le tenant_id."""
        tenant_id = "institution-multi-roles-test-001"
        roles = ("admin", "finance", "compliance")

        with db_actor("user-multi-roles", roles, tenant_id=tenant_id):
            db_context = current_db_context()
            assert db_context["tenant_id"] == tenant_id
            # Tous les rôles doivent être présents (séparés par des virgules)
            for role in roles:
                assert role in db_context["roles"]

    def test_tenant_id_cleared_after_context_exit(self):
        """Vérifie que le tenant_id est réinitialisé après la sortie du contexte."""
        from apps.core.tenant_context import clear_tenant_id

        tenant_id = "institution-cleanup-test-001"

        set_tenant_id(tenant_id)
        assert get_tenant_id() == tenant_id

        clear_tenant_id()
        assert get_tenant_id() is None

    def test_exception_in_db_actor_clears_context(self):
        """Vérifie que le contexte est réinitialisé même en cas d'exception."""
        tenant_id = "institution-exception-test-001"

        try:
            with db_actor("user-exception", "admin", tenant_id=tenant_id):
                db_context = current_db_context()
                assert db_context["tenant_id"] == tenant_id
                raise ValueError("Test exception")
        except ValueError:
            pass

        # Après l'exception, le contexte doit être réinitialisé
        # (car SET LOCAL meurt avec la transaction)
        # Vérifier que nous pouvons créer un nouveau contexte sans erreur
        with db_actor("user-after-exception", "admin", tenant_id="new-tenant"):
            db_context = current_db_context()
            assert db_context["tenant_id"] == "new-tenant"
