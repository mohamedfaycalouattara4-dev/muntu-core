"""Muntu Core — Réclamations membres avec quorum d'arbitrage."""
from __future__ import annotations
from django.db import models
from django.utils import timezone


def generate_ulid() -> str:
    import uuid
    ts = int(timezone.now().timestamp() * 1000)
    rnd = uuid.uuid4().hex[:16]
    return f"{ts:013x}{rnd}"


class ClaimCategory(models.TextChoices):
    ACCOUNT = "ACCOUNT", "Problème de compte"
    TRANSACTION = "TRANSACTION", "Transaction contestée"
    LOAN = "LOAN", "Litige de prêt"
    FEE = "FEE", "Frais contestés"
    SERVICE = "SERVICE", "Qualité de service"
    FRAUD = "FRAUD", "Fraude suspectée"
    OTHER = "OTHER", "Autre"


class ClaimStatus(models.TextChoices):
    OPEN = "OPEN", "Ouverte"
    UNDER_REVIEW = "UNDER_REVIEW", "En examen"
    ARBITRATION = "ARBITRATION", "En arbitrage (quorum)"
    RESOLVED = "RESOLVED", "Résolue"
    ESCALATED = "ESCALATED", "Escaladée"
    CLOSED = "CLOSED", "Clôturée"


class Claim(models.Model):
    """Réclamation d'un membre — avec quorum d'arbitrage."""
    id = models.CharField(max_length=26, primary_key=True, default=generate_ulid, editable=False)
    tenant_id = models.CharField(max_length=26, db_index=True)
    reference = models.CharField(max_length=50, unique=True, db_index=True)
    member_id = models.CharField(max_length=26, db_index=True)
    category = models.CharField(max_length=20, choices=ClaimCategory.choices)
    description = models.TextField()
    amount_xof = models.BigIntegerField(default=0)
    status = models.CharField(max_length=20, choices=ClaimStatus.choices, default=ClaimStatus.OPEN, db_index=True)
    priority = models.CharField(
        max_length=10, choices=[("LOW", "Faible"), ("MEDIUM", "Moyenne"), ("HIGH", "Élevée"), ("URGENT", "Urgente")],
        default="MEDIUM",
    )
    assigned_to = models.CharField(max_length=26, blank=True)
    requires_quorum = models.BooleanField(default=False)
    quorum_votes_yes = models.IntegerField(default=0)
    quorum_votes_no = models.IntegerField(default=0)
    quorum_required = models.IntegerField(default=2)
    resolution = models.TextField(blank=True)
    resolved_by = models.CharField(max_length=26, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["tenant_id", "status"])]

    def __str__(self):
        return f"Réclamation {self.reference} [{self.status}]"


class ClaimResolution(models.Model):
    """Vote d'arbitrage d'un membre du comité."""
    id = models.CharField(max_length=26, primary_key=True, default=generate_ulid, editable=False)
    claim = models.ForeignKey(Claim, on_delete=models.CASCADE, related_name="resolutions")
    voter_id = models.CharField(max_length=26, db_index=True)
    vote = models.CharField(max_length=10, choices=[("YES", "Pour"), ("NO", "Contre"), ("ABSTAIN", "Abstention")])
    reasoning = models.TextField(blank=True)
    voted_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = [["claim", "voter_id"]]
