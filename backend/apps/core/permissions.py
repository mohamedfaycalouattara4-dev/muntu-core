"""RBAC + permissions fines pour les rôles du document V2.

buyer, seller, courier, operator (support), finance, compliance, admin, arbitrator.

Notes de sécurité (P0-01 / P0-03) :
* aucune vue financière ne doit se contenter de `IsAuthenticated` ;
* `HasVerifiedWebAuthn` exige une session WebAuthn **réellement vérifiée**
  (assertion FIDO2 contrôlée côté serveur), pas la simple présence d'un en-tête.
"""
from __future__ import annotations

import time

from django.core.cache import cache
from rest_framework.permissions import BasePermission

#: Durée pendant laquelle une vérification WebAuthn reste valable (secondes).
WEBAUTHN_SESSION_TTL = 600


def _roles(request) -> set[str]:
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return set()
    return set(user.roles or [])


class _RoleRequired(BasePermission):
    required_roles: tuple[str, ...] = ()

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        if not (user and user.is_authenticated) or getattr(user, "is_suspended", False):
            return False
        return bool(_roles(request) & set(self.required_roles))


class IsBuyer(_RoleRequired):
    required_roles = ("buyer",)


class IsSeller(_RoleRequired):
    required_roles = ("seller",)


class IsCourier(_RoleRequired):
    required_roles = ("courier",)


class IsOperator(_RoleRequired):
    required_roles = ("operator",)


class IsFinance(_RoleRequired):
    required_roles = ("finance",)


class IsCompliance(_RoleRequired):
    required_roles = ("compliance",)


class IsAdmin(_RoleRequired):
    required_roles = ("admin",)


class IsArbitrator(_RoleRequired):
    """Seuls ces rôles peuvent trancher un litige (P0-01)."""

    message = "Rôle arbitre requis (arbitrator, compliance ou admin)."
    required_roles = ("arbitrator", "compliance", "admin")


# ---------------------------------------------------------------------------
# Sessions WebAuthn vérifiées
# ---------------------------------------------------------------------------
#: Opération générique (ouverture de session sensible).
GENERIC_OPERATION = "*"
#: Durée d'une élévation financière : bien plus courte qu'une session sensible.
STEP_UP_TTL = 120
#: Montant (XOF) au-delà duquel une élévation dédiée est exigée.
STEP_UP_AMOUNT_THRESHOLD_XOF = 100_000


def _webauthn_session_key(user_id: str, operation: str = GENERIC_OPERATION) -> str:
    suffix = "" if operation == GENERIC_OPERATION else f":{operation}"
    return f"webauthn:verified:{user_id}{suffix}"


def mark_webauthn_verified(user_id: str, *, ttl: int = WEBAUTHN_SESSION_TTL,
                           operation: str = GENERIC_OPERATION) -> None:
    """Marque une vérification FIDO2 réussie, éventuellement liée à une opération.

    La portée par opération est ce qui distingue une simple session sensible
    d'un *step-up* : une vérification faite pour consulter un dossier ne doit
    pas autoriser, dans la foulée, un déblocage de fonds.
    """
    cache.set(_webauthn_session_key(str(user_id), operation), time.time(), timeout=ttl)


def has_recent_webauthn(user_id: str, *, max_age: int = WEBAUTHN_SESSION_TTL,
                        operation: str = GENERIC_OPERATION) -> bool:
    verified_at = cache.get(_webauthn_session_key(str(user_id), operation))
    return bool(verified_at) and (time.time() - float(verified_at)) <= max_age


def clear_webauthn_verification(user_id: str,
                                operation: str = GENERIC_OPERATION) -> None:
    cache.delete(_webauthn_session_key(str(user_id), operation))


def step_up_required(amount_xof: int) -> bool:
    """Une élévation dédiée est-elle exigée pour ce montant ?"""
    return int(amount_xof or 0) >= STEP_UP_AMOUNT_THRESHOLD_XOF


def has_financial_step_up(user_id: str, operation: str, *,
                          max_age: int = STEP_UP_TTL) -> bool:
    return has_recent_webauthn(user_id, max_age=max_age, operation=operation)


class StepUpRequired(Exception):
    """L'opération exige une réauthentification FIDO2 dédiée et récente."""

    def __init__(self, operation: str):
        super().__init__(
            f"Élévation d'authentification requise pour l'opération « {operation} ».")
        self.operation = operation


def enforce_financial_step_up(user, operation: str, amount_xof: int) -> None:
    """Garde-fou financier : au-delà du seuil, exige un step-up frais et ciblé.

    Appelé par les vues financières avant tout mouvement d'argent. Volontairement
    une fonction et non une permission : le seuil dépend du montant, qui n'est
    connu qu'après validation de la charge utile.
    """
    if not step_up_required(amount_xof):
        return
    if not getattr(user, "webauthn_credentials", None):
        raise StepUpRequired(operation)
    if not has_financial_step_up(str(user.id), operation):
        raise StepUpRequired(operation)


class HasVerifiedWebAuthn(BasePermission):
    """Exige une vérification FIDO2 récente, prouvée côté serveur.

    Corrige P0-03 : l'ancienne implémentation acceptait n'importe quel en-tête
    `X-Webauthn-Assertion` non vide.
    """

    message = "Authentification WebAuthn récente requise pour cette opération sensible."

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        if not (user and user.is_authenticated):
            return False
        if not getattr(user, "webauthn_credentials", None):
            self.message = "Aucune clé FIDO2 enregistrée pour ce compte."
            return False
        return has_recent_webauthn(user.id)


# Alias historique — conserve le nom utilisé par les vues existantes.
HasTwoFactorForSensitiveOps = HasVerifiedWebAuthn



class RequiresQuorum(BasePermission):
    """Le quorum est vérifié dans la vue (il dépend du montant et de l'opération).

    Cette permission ne fait que garantir que l'appelant est habilité à
    initier une opération soumise à quorum.
    """

    message = "Quorum financier requis (approbateurs distincts × WebAuthn vérifié)."
    required_roles = ("finance", "compliance", "admin", "arbitrator")

    def has_permission(self, request, view):
        return bool(_roles(request) & set(self.required_roles))
