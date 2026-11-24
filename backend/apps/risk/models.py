"""Risk · signals + AML alerts (V2 §13.4)."""
from __future__ import annotations

from django.db import models

from apps.core.models import TimeStampedModel, generate_ulid


# --- Seuils réglementaires -------------------------------------------------
#: Seuil BCEAO (V2 §13.4) au-delà duquel une KYC renforcée est obligatoire.
KYC_BCEAO_THRESHOLD_XOF: int = 10_000_000

#: Bornes de sévérité du score de risque (V2 §13.4).
RISK_MEDIUM_THRESHOLD: int = 50
RISK_HIGH_THRESHOLD: int = 80


class RiskScoreLevel(models.TextChoices):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class AMLAlert(TimeStampedModel):
    id = models.CharField(max_length=26, primary_key=True, default=generate_ulid, editable=False)
    user_id = models.CharField(max_length=26, db_index=True)
    order_id = models.CharField(max_length=26, blank=True, db_index=True)
    severity = models.CharField(max_length=10, choices=RiskScoreLevel.choices, default="MEDIUM")
    score = models.IntegerField()
    rule_code = models.CharField(max_length=200)
    description = models.TextField()
    sar_filed = models.BooleanField(default=False)  # Suspicious Activity Report BCEAO
    status = models.CharField(max_length=20, default="open", db_index=True)


class RiskSignal(TimeStampedModel):
    """Behavioral fingerprint — bulk/rapid-fire/IPs/disputes."""
    name = models.CharField(max_length=60, primary_key=True)
    description = models.TextField()
    weight = models.IntegerField(default=10)
    level_medium_threshold = models.IntegerField(default=50)
    level_high_threshold = models.IntegerField(default=80)


class KycThreshold(TimeStampedModel):
    """Seuil BCEAO — au-delà, KYC renforcée."""
    name = models.CharField(max_length=50, primary_key=True)
    amount_xof = models.BigIntegerField()
    rule = models.TextField()


class FreezeScope(models.TextChoices):
    """Portée d'un gel — jamais implicite, jamais élargie automatiquement."""

    USER = "USER"
    ORDER = "ORDER"
    AGGREGATOR = "AGGREGATOR"
    GLOBAL = "GLOBAL"


class AccountFreeze(TimeStampedModel):
    """Gel persistant et ciblé (P0-04).

    Remplace l'ancien drapeau de cache global : un gel est une ligne en base,
    portée + cible explicites, traçable, et sa levée exige un double contrôle
    (`lifted_by` ≠ `created_by`, cf. `apps.core.policies.can_lift_freeze`).

    Un gel GLOBAL ne peut jamais être créé par une règle automatique : seule
    une action humaine sous quorum WebAuthn en produit un.
    """

    id = models.CharField(max_length=26, primary_key=True, default=generate_ulid, editable=False)
    scope = models.CharField(max_length=20, choices=FreezeScope.choices,
                             default=FreezeScope.USER, db_index=True)
    target_id = models.CharField(max_length=26, blank=True, db_index=True)
    reason = models.TextField()
    rule_code = models.CharField(max_length=200, blank=True)
    alert_id = models.CharField(max_length=26, blank=True, db_index=True)
    created_by = models.CharField(max_length=26, default="system", db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    lifted_at = models.DateTimeField(null=True, blank=True)
    lifted_by = models.CharField(max_length=26, blank=True)
    lift_approvals = models.JSONField(default=list, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["scope", "target_id"],
                                    condition=models.Q(is_active=True),
                                    name="uniq_active_freeze_per_target"),
        ]
        indexes = [models.Index(fields=["scope", "is_active"])]

    def __str__(self) -> str:  # pragma: no cover - confort de debug
        return f"{self.scope}:{self.target_id or '*'} actif={self.is_active}"
