"""Contexte RLS par requête (P0-06).

Sans ces variables de session, toutes les politiques `USING (...)` évaluent
`NULL` et n'isolent rien. Le middleware pose le contexte au début de chaque
requête et le réinitialise systématiquement à la fin (les connexions sont
mutualisées : un contexte oublié fuiterait sur la requête suivante).
"""
from __future__ import annotations

import logging
from contextlib import contextmanager

from django.db import connection, transaction

logger = logging.getLogger("muntu.security")


def set_rls_context(*, user_id: str = "", roles=(), system: bool = False,
                    tenant_id: str = "", local: bool | None = None) -> None:
    """Pose le contexte d'autorisation avec support multi-tenant (Phase 00).

    `local=None` choisit automatiquement `SET LOCAL` dès qu'une transaction est
    ouverte (ATOMIC_REQUESTS, `transaction.atomic`) : le contexte meurt alors
    avec la transaction et ne peut pas fuir vers la requête suivante servie par
    la même connexion mutualisée — vulnérabilité classique avec PgBouncer.

    Args:
        user_id: Identifiant de l'utilisateur courant.
        roles: Tuple de rôles de l'utilisateur.
        system: Vrai si l'acteur est un système (tâche Celery, migration).
        tenant_id: Identifiant de l'institution (tenant) courante (Phase 00).
        local: Portée de la variable (LOCAL = transaction, session = requête).
    """
    from apps.core.db import set_local_context

    set_local_context(user_id=user_id, roles=roles, system=system,
                      tenant_id=tenant_id, local=local)


def clear_rls_context() -> None:
    """Réinitialise le contexte au niveau session (fin de requête).

    Toujours en portée session : c'est le filet qui garantit qu'aucune valeur
    ne survit à la requête, même si la transaction a été fermée avant.
    """
    if connection.vendor != "postgresql":
        return
    set_rls_context(user_id="", roles=(), system=False, tenant_id="", local=False)


@contextmanager
def system_context(*, tenant_id: str = ""):
    """Contexte privilégié explicite pour les tâches de fond et les migrations.

    Args:
        tenant_id: Identifiant du tenant (optionnel, pour les tâches cross-tenant).
    """
    set_rls_context(user_id="system", roles=("system",), system=True, tenant_id=tenant_id)
    try:
        yield
    finally:
        clear_rls_context()


class RowLevelSecurityMiddleware:
    """Propage l'identité applicative vers PostgreSQL à chaque requête.

    La requête est enveloppée dans une transaction explicite afin que le
    contexte soit posé en `SET LOCAL` : il meurt avec la transaction et ne peut
    donc jamais fuir vers la requête suivante servie par la même connexion.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def _apply(self, request):
        from apps.core.tenant_context import get_tenant_id

        user = getattr(request, "user", None)
        tenant_id = get_tenant_id() or ""

        if user is not None and getattr(user, "is_authenticated", False):
            set_rls_context(user_id=str(user.id), roles=tuple(user.roles or ()),
                          tenant_id=tenant_id)
        else:
            set_rls_context(user_id="", roles=(), system=False, tenant_id=tenant_id)

    def __call__(self, request):
        if connection.vendor != "postgresql":  # pragma: no cover - parité locale
            return self.get_response(request)
        try:
            with transaction.atomic():
                try:
                    self._apply(request)
                except Exception:  # noqa: BLE001 - jamais bloquant, toujours tracé
                    logger.exception("Impossible de poser le contexte RLS")
                return self.get_response(request)
        finally:
            # Filet de sécurité : la portée session est remise à zéro même si
            # une transaction a été fermée prématurément par le code appelant.
            try:
                clear_rls_context()
            except Exception:  # noqa: BLE001 - pragma: no cover
                logger.exception("Impossible de réinitialiser le contexte RLS")
