"""Politiques d'autorisation centralisées (P0-01).

Règle d'architecture non négociable : **aucune vue n'écrit de condition
d'autorisation métier**. Toute décision passe par une fonction pure de ce
module, qui renvoie un objet `Decision` explicite (autorisé / motif).

Pourquoi ici et pas des décorateurs dispersés : un auditeur doit pouvoir lire
*un seul fichier* pour connaître l'intégralité des règles d'accès aux
opérations financières. Des vérifications ad hoc dans les vues sont
impossibles à auditer exhaustivement et divergent au fil des refactorings.

Toutes les fonctions sont pures (aucun effet de bord, aucune écriture) et
testables sans HTTP.
"""
from __future__ import annotations

from dataclasses import dataclass


class Role:
    """Rôles fonctionnels (miroir de `apps.accounts.models.UserRole`)."""

    BUYER = "buyer"
    SELLER = "seller"
    COURIER = "courier"
    OPERATOR = "operator"
    FINANCE = "finance"
    COMPLIANCE = "compliance"
    ARBITRE = "arbitrator"          # nom métier FR = ARBITRE, valeur stockée = arbitrator
    ARBITRATOR = "arbitrator"
    ADMIN = "admin"
    AUDITOR = "auditor"


#: Rôles habilités à trancher un litige (P0-01).
ARBITRATION_ROLES = (Role.ARBITRE,)
#: Rôles habilités à contresigner une opération financière (quorum, P0-02).
FINANCIAL_APPROVER_ROLES = (Role.FINANCE, Role.COMPLIANCE, Role.ADMIN)
#: Rôles habilités à geler / dégeler (P0-04).
FREEZE_ROLES = (Role.COMPLIANCE, Role.ADMIN)
#: États d'un litige pendant lesquels l'instruction est encore ouverte.
INSTRUCTION_STATES = ("OPENED", "UNDER_REVIEW")


@dataclass(frozen=True)
class Decision:
    """Résultat d'une politique : autorisé ou refusé, avec un motif stable."""

    allowed: bool
    reason: str = ""

    def __bool__(self) -> bool:  # `if can_decide_dispute(...)`
        return self.allowed


ALLOW = Decision(True)


def _roles(user) -> set[str]:
    return {str(r) for r in (getattr(user, "roles", None) or [])}


def has_role(user, *roles: str) -> bool:
    return bool(_roles(user) & set(roles))


def _authenticated(user) -> Decision | None:
    if not user or not getattr(user, "is_authenticated", False):
        return Decision(False, "anonymous")
    if getattr(user, "is_suspended", False):
        return Decision(False, "account_suspended")
    if not getattr(user, "is_active", True):
        return Decision(False, "account_inactive")
    return None


# ---------------------------------------------------------------------------
# Litiges
# ---------------------------------------------------------------------------
def can_open_dispute(user, target=None) -> Decision:
    """Autorise l'ouverture d'un litige (Phase 01 - Découplage)."""
    denial = _authenticated(user)
    if denial:
        return denial
    # En Phase 01, on simplifie l'autorisation en attendant le nouveau domaine métier SFD
    return ALLOW


def can_add_evidence(user, dispute, target=None) -> Decision:
    """Autorise l'ajout de preuves (Phase 01 - Découplage)."""
    denial = _authenticated(user)
    if denial:
        return denial
    if dispute is None:
        return Decision(False, "dispute_not_found")
    if has_role(user, Role.ARBITRE, Role.COMPLIANCE, Role.ADMIN, Role.OPERATOR):
        return ALLOW
    if _involves(dispute, target, str(user.id)):
        return ALLOW
    return Decision(False, "not_a_party")


def _involves(dispute, target, user_id: str) -> bool:
    """Vrai si `user_id` est partie prenante du litige (Phase 01 - Découplage)."""
    if hasattr(dispute, "involves"):
        return bool(dispute.involves(user_id))
    parties = {str(getattr(dispute, "initiator_id", "") or ""),
               str(getattr(dispute, "arbiter_id", "") or "")}
    # Le couplage avec Order est supprimé ici.
    parties.discard("")
    return user_id in parties


def can_decide_dispute(user, dispute, target=None) -> Decision:
    """Autorise la décision d'un litige (Phase 01 - Découplage)."""
    denial = _authenticated(user)
    if denial:
        return denial
    if not has_role(user, *ARBITRATION_ROLES):
        return Decision(False, f"role_required:{Role.ARBITRE}")
    if dispute is None:
        return Decision(False, "dispute_not_found")
    if _involves(dispute, target, str(user.id)):
        return Decision(False, "conflict_of_interest")
    state = str(getattr(dispute, "state", ""))
    if state not in INSTRUCTION_STATES:
        return Decision(False, f"bad_state:{state}")
    return ALLOW


# ---------------------------------------------------------------------------
# Opérations financières
# ---------------------------------------------------------------------------
def can_approve_financial_operation(user) -> Decision:
    """Habilitation à contresigner un quorum financier (P0-02)."""
    denial = _authenticated(user)
    if denial:
        return denial
    if not has_role(user, *FINANCIAL_APPROVER_ROLES, Role.ARBITRE):
        return Decision(False, "role_required:finance|compliance|admin|arbitrator")
    return ALLOW


def can_execute_financial_action(user) -> Decision:
    """Libération / remboursement manuel de fonds séquestrés."""
    denial = _authenticated(user)
    if denial:
        return denial
    if not has_role(user, Role.FINANCE, Role.ADMIN, Role.ARBITRE):
        return Decision(False, "role_required:finance|admin|arbitrator")
    return ALLOW


# ---------------------------------------------------------------------------
# Gels (P0-04)
# ---------------------------------------------------------------------------
def can_freeze_scope(user, scope: str) -> Decision:
    denial = _authenticated(user)
    if denial:
        return denial
    if scope == "GLOBAL":
        if not has_role(user, Role.ADMIN):
            return Decision(False, "role_required:admin")
        return ALLOW
    if not has_role(user, *FREEZE_ROLES):
        return Decision(False, "role_required:compliance|admin")
    return ALLOW


def can_lift_freeze(user, freeze) -> Decision:
    """Levée sous double contrôle : l'auteur du gel ne peut pas le lever seul."""
    denial = can_freeze_scope(user, str(getattr(freeze, "scope", "USER")))
    if not denial.allowed:
        return denial
    if freeze is None:
        return Decision(False, "freeze_not_found")
    if not getattr(freeze, "is_active", True):
        return Decision(False, "freeze_already_lifted")
    if str(getattr(freeze, "created_by", "")) == str(user.id):
        return Decision(False, "four_eyes_required")
    return ALLOW
