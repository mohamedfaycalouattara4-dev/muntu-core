"""Risk Engine · orchestrateur (V2 §13.4).

Scénarios typiques : Bulk buying, Rapid-fire, Circular flows, Structuring,
High-value cash out.
Seuils : score <50 LOW, 50-79 MEDIUM, ≥80 HIGH → auto-freeze + alerte SOC.
KYC BCEAO : >10 000 000 XOF.
"""
from __future__ import annotations

import logging

from django.conf import settings

from .models import (
    AMLAlert,
    KYC_BCEAO_THRESHOLD_XOF,
    RISK_HIGH_THRESHOLD,
    RISK_MEDIUM_THRESHOLD,
    RiskScoreLevel,
)

logger = logging.getLogger("muntu.risk")


def _raise_aml(*, user_id: str, order_id: str, score: int, rule: str, body: str) -> AMLAlert:
    if score >= RISK_HIGH_THRESHOLD:
        severity = RiskScoreLevel.HIGH
    elif score >= RISK_MEDIUM_THRESHOLD:
        severity = RiskScoreLevel.MEDIUM
    else:
        severity = RiskScoreLevel.LOW
    return AMLAlert.objects.create(
        user_id=user_id, order_id=order_id or "",
        severity=severity, score=score,
        rule_code=rule, description=body)


def score(*, user_id: str, order_id: str, amount_xof: int,
          rapid_fire: bool = False, bulk_buy: bool = False,
          shared_ip_count: int = 0, structuring_suspect: bool = False,
          high_value_cash_out: bool = False) -> AMLAlert | None:
    score = 0
    rules = []
    descriptions = []
    if bulk_buy:
        score += 50
        rules.append("BULK_BUY_50PCT")
        descriptions.append(">50 % du stock en une commande.")
    if rapid_fire:
        score += 30
        rules.append("RAPID_FIRE_<5S")
        descriptions.append("Commande <5s après ouverture session.")
    if shared_ip_count >= 3:
        score += 15
        rules.append("SHARED_IP_3+")
        descriptions.append("Plusieurs commandes depuis la même IP.")
    if structuring_suspect:
        score += 40
        rules.append("STRUCTURING")
        descriptions.append("Fractionnement suspect.")
    if high_value_cash_out:
        score += 45
        rules.append("HIGH_VALUE_CASH_OUT")
        descriptions.append("Retrait immédiat après réception.")
    if amount_xof >= KYC_BCEAO_THRESHOLD_XOF:
        score += 50
        rules.append("BCEAO_KYC_10M")
        descriptions.append("KYC renforcée BCEAO (≥ 10 000 000 XOF).")
    alert = None
    if score:
        body = "; ".join(descriptions)
        alert = _raise_aml(user_id=user_id, order_id=order_id or "",
                            score=score, rule="+".join(rules), body=body)
        logger.warning("AML alert user=%s order=%s score=%d rules=%s",
                       user_id, order_id, score, rules)
    return alert


#: Nombre d'utilisateurs distincts en alerte HIGH avant escalade SOC.
GLOBAL_ESCALATION_DISTINCT_USERS = int(
    getattr(settings, "RISK_GLOBAL_ESCALATION_USERS", 0) or 25)
GLOBAL_ESCALATION_WINDOW_MINUTES = 60
#: Le système ne gèle jamais au-delà de cette portée, quelle que soit l'alerte.
AUTOMATIC_FREEZE_SCOPES = ("USER",)


# ---------------------------------------------------------------------------
# Gels ciblés et persistés (P0-04)
# ---------------------------------------------------------------------------
class FreezeError(Exception):
    """Opération de gel refusée (portée interdite, double contrôle absent…)."""


def active_freeze(scope: str, target_id: str = ""):
    """Renvoie le gel actif pour une cible, ou None."""
    from .models import AccountFreeze

    return AccountFreeze.objects.filter(
        scope=scope, target_id=str(target_id or ""), is_active=True).first()


def is_user_frozen(user_id: str) -> bool:
    return active_freeze("USER", str(user_id)) is not None


def is_platform_frozen() -> bool:
    """Gel global : uniquement s'il a été décidé par un humain sous quorum."""
    return active_freeze("GLOBAL", "") is not None


def freeze_target(*, scope: str, target_id: str, reason: str, created_by: str,
                  rule_code: str = "", alert_id: str = "", automatic: bool = False):
    """Crée (ou réutilise) un gel actif, journalisé et traçable.

    `automatic=True` restreint la portée à `AUTOMATIC_FREEZE_SCOPES` : aucune
    règle de risque ne peut produire un gel de plateforme.
    """
    from django.db import IntegrityError, transaction

    from .models import AccountFreeze

    scope = str(scope).upper()
    if automatic and scope not in AUTOMATIC_FREEZE_SCOPES:
        raise FreezeError(
            f"Un gel automatique de portée {scope} est interdit : "
            "seul un gel ciblé USER peut être déclenché par une règle.")

    existing = active_freeze(scope, target_id)
    if existing:
        return existing
    try:
        with transaction.atomic():
            freeze = AccountFreeze.objects.create(
                scope=scope, target_id=str(target_id or ""), reason=reason,
                rule_code=rule_code, alert_id=alert_id or "",
                created_by=str(created_by or "system"))
    except IntegrityError:  # course concurrente : le gel existe déjà
        return active_freeze(scope, target_id)

    _audit("freeze", freeze, {"reason": reason, "rule": rule_code})
    logger.critical("GEL %s cible=%s par=%s motif=%s",
                    scope, target_id or "*", created_by, reason)
    return freeze


def lift_freeze(freeze, *, actor, approvals=()) -> None:
    """Lève un gel sous double contrôle (P0-04).

    La politique `can_lift_freeze` interdit à l'auteur du gel de le lever seul ;
    un gel de portée GLOBAL exige en plus un quorum d'approbations vérifiées.
    """
    from django.utils import timezone

    from apps.core.policies import can_lift_freeze

    verdict = can_lift_freeze(actor, freeze)
    if not verdict.allowed:
        raise FreezeError(f"Levée refusée : {verdict.reason}")
    approver_ids = sorted({str(a.user_id if hasattr(a, "user_id") else a) for a in approvals})
    if freeze.scope == "GLOBAL" and len(approver_ids) < 2:
        raise FreezeError("La levée d'un gel global exige un quorum de 2 approbateurs.")

    freeze.is_active = False
    freeze.lifted_at = timezone.now()
    freeze.lifted_by = str(actor.id)
    freeze.lift_approvals = approver_ids
    freeze.save(update_fields=["is_active", "lifted_at", "lifted_by",
                               "lift_approvals", "updated_at"])
    if freeze.scope == "USER" and freeze.target_id:
        _set_suspension(freeze.target_id, suspended=False, reason="")
    _audit("unfreeze", freeze, {"by": str(actor.id), "approvals": approver_ids})


def _audit(action: str, freeze, extra: dict) -> None:
    try:
        from apps.core.services.audit import emit

        emit("system", f"freeze:{freeze.scope}:{freeze.target_id or '*'}", action,
             {"freeze_id": str(freeze.id), **extra})
    except Exception:  # pragma: no cover - l'audit ne doit jamais bloquer un gel
        logger.exception("Audit du gel %s impossible", getattr(freeze, "id", "?"))


def auto_freeze_if_high(alert: AMLAlert | None) -> bool:
    """Gel CIBLÉ sur l'utilisateur concerné — jamais la plateforme entière.

    Corrige P0-04 : une seule alerte HIGH sur un seul compte gelait tout KALYCE
    (déni de service auto-infligé, déclenchable par n'importe quel attaquant).
    Désormais :

    * l'alerte HIGH crée un `AccountFreeze` de portée USER, persistant et
      traçable, et suspend ce seul compte ;
    * la levée exige un opérateur différent (double contrôle) ;
    * le gel global n'est jamais automatique : au-delà d'un seuil d'alertes HIGH
      sur des comptes distincts, on émet une escalade SOC critique, et seul un
      administrateur (WebAuthn + quorum) peut l'activer.
    """
    if not alert or alert.severity != RiskScoreLevel.HIGH:
        return False

    freeze_target(scope="USER", target_id=alert.user_id,
                  reason=f"AML HIGH {alert.rule_code} (alerte {alert.id})",
                  rule_code=alert.rule_code, alert_id=str(alert.id),
                  created_by="system", automatic=True)
    _set_suspension(alert.user_id, suspended=True,
                    reason=f"AML HIGH {alert.rule_code} (alerte {alert.id})")
    _escalate_if_systemic(alert)
    return True


def _set_suspension(user_id: str, *, suspended: bool, reason: str) -> None:
    from django.contrib.auth import get_user_model

    updated = get_user_model().objects.filter(pk=user_id).update(
        is_suspended=suspended, suspension_reason=reason)
    if not updated:
        logger.warning("Gel AML : utilisateur %s introuvable", user_id)


def _escalate_if_systemic(alert: AMLAlert) -> None:
    """Détecte une fraude systémique et alerte le SOC — sans geler la plateforme."""
    from datetime import timedelta

    from django.utils import timezone

    since = timezone.now() - timedelta(minutes=GLOBAL_ESCALATION_WINDOW_MINUTES)
    distinct_users = (AMLAlert.objects
                      .filter(severity=RiskScoreLevel.HIGH, created_at__gte=since)
                      .values_list("user_id", flat=True).distinct().count())
    if distinct_users >= GLOBAL_ESCALATION_DISTINCT_USERS:
        logger.critical(
            "ESCALADE SOC : %d comptes distincts en alerte AML HIGH en %d minutes. "
            "Décision de gel global réservée à un administrateur (WebAuthn + quorum).",
            distinct_users, GLOBAL_ESCALATION_WINDOW_MINUTES)
