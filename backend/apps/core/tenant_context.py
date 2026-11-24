"""MUNTU CORE · Gestion du contexte tenant_id global (Phase 00).

Mécanisme pour injecter et propager le tenant_id à travers toutes les couches
de l'application (requêtes HTTP, tâches asynchrones, accès base de données).

Utilise contextvars (thread-safe, async-safe) pour stocker le tenant_id courant.
"""
from __future__ import annotations

import contextvars
import logging
from typing import Optional

logger = logging.getLogger("muntu.tenant")

# Variable de contexte pour stocker le tenant_id courant
_tenant_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "tenant_id",
    default=None
)


def set_tenant_id(tenant_id: str) -> None:
    """Définit le tenant_id pour le contexte courant.

    Args:
        tenant_id: Identifiant unique de l'institution (ULID).

    Raises:
        ValueError: Si tenant_id est vide ou invalide.
    """
    if not tenant_id or not isinstance(tenant_id, str):
        raise ValueError(f"tenant_id invalide : {tenant_id}")
    _tenant_id_var.set(tenant_id)
    logger.debug(f"Tenant context set to: {tenant_id}")


def get_tenant_id() -> Optional[str]:
    """Récupère le tenant_id du contexte courant.

    Returns:
        L'identifiant du tenant courant, ou None si aucun n'est défini.
    """
    return _tenant_id_var.get()


def clear_tenant_id() -> None:
    """Réinitialise le tenant_id du contexte courant."""
    _tenant_id_var.set(None)
    logger.debug("Tenant context cleared")


def require_tenant_id() -> str:
    """Récupère le tenant_id et lève une exception s'il n'existe pas.

    Returns:
        L'identifiant du tenant courant.

    Raises:
        RuntimeError: Si aucun tenant_id n'est défini.
    """
    tenant_id = get_tenant_id()
    if not tenant_id:
        raise RuntimeError("Aucun tenant_id défini dans le contexte courant. "
                          "Assurez-vous que le middleware TenantMiddleware est actif.")
    return tenant_id


class TenantContext:
    """Context manager pour définir temporairement un tenant_id.

    Exemple :
        with TenantContext("institution-123"):
            # Code exécuté avec tenant_id = "institution-123"
            ...
        # tenant_id réinitialisé après la sortie du bloc
    """

    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id
        self.token: Optional[contextvars.Token] = None

    def __enter__(self) -> TenantContext:
        self.token = _tenant_id_var.set(self.tenant_id)
        logger.debug(f"Entering TenantContext: {self.tenant_id}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self.token:
            _tenant_id_var.reset(self.token)
            logger.debug(f"Exiting TenantContext: {self.tenant_id}")
