"""Contexte d'autorisation PostgreSQL pour le code hors requête HTTP.

Toute tâche Celery qui touche une table protégée par RLS doit s'exécuter dans
un `db_actor(...)` explicite : sans contexte, les politiques évaluent NULL et
la tâche ne voit rien (ou, pire, on serait tenté de désactiver la RLS).

`SET LOCAL` est impératif : la valeur meurt avec la transaction et ne peut donc
pas fuir vers la requête suivante servie par la même connexion mutualisée
(PgBouncer en mode transaction).
"""
from __future__ import annotations

from contextlib import contextmanager

from django.db import connection, transaction

__all__ = ["db_actor", "db_system_actor", "set_local_context", "current_db_context"]


def set_local_context(*, user_id: str = "", roles=(), system: bool = False,
                      tenant_id: str = "", local: bool | None = None) -> None:
    """Pose les variables de contexte lues par les politiques RLS (Phase 00).

    Nouvelles variables (Phase 00) :
        - muntu.tenant_id : Identifiant de l'institution (tenant) courante
    """
    if connection.vendor != "postgresql":
        return
    scope_local = connection.in_atomic_block if local is None else local
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT set_config('muntu.current_user_id', %s, %s),"
            "       set_config('muntu.role', %s, %s),"
            "       set_config('muntu.system', %s, %s),"
            "       set_config('muntu.tenant_id', %s, %s)",
            [str(user_id or ""), scope_local,
             ",".join(sorted({str(r) for r in (roles or ())})), scope_local,
             "on" if system else "off", scope_local,
             str(tenant_id or ""), scope_local],
        )


def current_db_context() -> dict[str, str]:
    if connection.vendor != "postgresql":  # pragma: no cover
        return {}
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT coalesce(current_setting('muntu.current_user_id', true), ''),"
            "       coalesce(current_setting('muntu.role', true), ''),"
            "       coalesce(current_setting('muntu.system', true), 'off'),"
            "       coalesce(current_setting('muntu.tenant_id', true), '')")
        user_id, roles, system, tenant_id = cursor.fetchone()
    return {"user_id": user_id, "roles": roles, "system": system, "tenant_id": tenant_id}


@contextmanager
def db_actor(user_id: str, role: str | tuple[str, ...] | list[str], *,
             system: bool = False, tenant_id: str = ""):
    """Ouvre une transaction et y pose l'identité applicative (obligatoire en tâche).

    Utilisation :
        with db_actor(order.buyer_id, "buyer", tenant_id="institution-123"):
            ...

    Args:
        user_id: Identifiant de l'utilisateur.
        role: Rôle(s) de l'utilisateur.
        system: Vrai si l'acteur est un système.
        tenant_id: Identifiant du tenant (Phase 00).
    """
    roles = (role,) if isinstance(role, str) else tuple(role)
    with transaction.atomic():
        set_local_context(user_id=user_id, roles=roles, system=system,
                         tenant_id=tenant_id, local=True)
        yield
        # `SET LOCAL` : le contexte est automatiquement oublié à la sortie de la
        # transaction, y compris en cas d'exception. Aucun reset manuel requis.


@contextmanager
def db_system_actor(reason: str = "celery", *, tenant_id: str = ""):
    """Contexte système explicite et tracé pour les tâches de plateforme.

    Args:
        reason: Motif de l'exécution système (ex: "celery", "migration").
        tenant_id: Identifiant du tenant (Phase 00, optionnel).
    """
    with db_actor("system", ("service", "system"), system=True, tenant_id=tenant_id):
        yield reason
