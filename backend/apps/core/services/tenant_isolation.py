"""Muntu Core — Vérification d'isolation tenant (I2).

Aucune donnée ne traverse les institutions.
Toutes les requêtes doivent filtrer par tenant_id.
"""
from __future__ import annotations
import logging
from apps.core.tenant_context import get_tenant_id

logger = logging.getLogger("muntu.core.isolation")


class TenantIsolationViolation(Exception):
    """Exception levée quand une requête tente d'accéder à des données d'un autre tenant."""
    pass


def require_tenant_scope(queryset, tenant_field: str = "tenant_id"):
    """Force le filtrage par tenant_id sur un queryset.

    Lève TenantIsolationViolation si aucun tenant_id n'est dans le contexte.
    """
    tenant_id = get_tenant_id()
    if not tenant_id:
        raise TenantIsolationViolation(
            "Aucun tenant_id dans le contexte. "
            "Toutes les requêtes métier doivent être scopées par tenant."
        )
    return queryset.filter(**{tenant_field: tenant_id})


def validate_no_cross_tenant_access(
    queryset,
    entity_id: str,
    tenant_field: str = "tenant_id",
):
    """Vérifie qu'une entité appartient bien au tenant courant.

    Lève TenantIsolationViolation si l'entité appartient à un autre tenant.
    """
    tenant_id = get_tenant_id()
    if not tenant_id:
        raise TenantIsolationViolation("Aucun tenant_id dans le contexte.")

    obj = queryset.filter(**{tenant_field: tenant_id}).first()
    if not obj:
        raise TenantIsolationViolation(
            f"Entité {entity_id} non trouvée dans le tenant {tenant_id} "
            "(accès inter-tenant détecté et bloqué)."
        )
    return obj
