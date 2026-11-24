"""KALYCE · Common abstract models & ULID helpers. Shared base models."""
from __future__ import annotations

import secrets
import time

from django.db import models


from apps.core.observability import CROCKFORD32, generate_ulid  # noqa: F401

__all__ = ["CROCKFORD32", "generate_ulid", "generate_order_number",
           "TimeStampedModel", "SoftDeleteModel", "SoftDeleteQuerySet",
           "SoftDeleteManager", "UsedNonce", "IdempotencyRecord", "OutboxEvent"]


def generate_order_number() -> str:
    """Numéro de commande lisible et non devinable : ``KLY-AAMMJJ-XXXXXXXX``."""
    stamp = time.strftime("%y%m%d", time.gmtime())
    suffix = "".join(secrets.choice(CROCKFORD32) for _ in range(8))
    return f"KLY-{stamp}-{suffix}"


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class SoftDeleteQuerySet(models.QuerySet):
    def alive(self):
        return self.filter(deleted_at__isnull=True)

    def dead(self):
        return self.filter(deleted_at__isnull=False)


class SoftDeleteManager(models.Manager.from_queryset(SoftDeleteQuerySet)):
    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)


class SoftDeleteModel(models.Model):
    """Soft delete (utilisé par LiveSession, Product).

    On évite un physical delete pour préserver la chaîne d'audit.
    """

    objects = SoftDeleteManager()
    all_objects = models.Manager()
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        abstract = True

    def soft_delete(self) -> None:
        from django.utils import timezone
        self.deleted_at = timezone.now()
        self.save(update_fields=["deleted_at", "updated_at"])


# Operational models live in this module too (no circular issue)
class UsedNonce(TimeStampedModel):
    nonce = models.CharField(max_length=64, primary_key=True)
    expires_at = models.DateTimeField(db_index=True)

    class Meta:
        indexes = [models.Index(fields=["expires_at"])]


class IdempotencyRecord(TimeStampedModel):
    """Cache secondaire Postgres pour idempotency-keys (si Redis indisponible)."""

    key_hash = models.CharField(max_length=64, primary_key=True)
    route_path = models.CharField(max_length=200)
    response_body = models.JSONField()
    response_status = models.PositiveSmallIntegerField()
    expires_at = models.DateTimeField(db_index=True)

    class Meta:
        indexes = [models.Index(fields=["expires_at"])]


class OutboxEvent(TimeStampedModel):
    """Pattern outbox : événements écrits dans la transaction métier.

    La tâche Beat `dispatch_outbox` les publie ensuite vers les canaux
    (notifications, temps réel, webhooks). Écrire l'intention avec le fait est
    ce qui empêche une notification d'exister sans transition, ou l'inverse.
    """

    STATUS_CHOICES = [("pending", "pending"), ("dispatched", "dispatched"), ("failed", "failed")]

    aggregate = models.CharField(max_length=50, db_index=True)
    #: Identifiant de l'agrégat : garantit l'ordre de publication par entité.
    aggregate_id = models.CharField(max_length=64, blank=True, db_index=True)
    tenant_id = models.CharField(
        max_length=26,
        db_index=True,
        help_text="Identifiant du tenant (institution) — Phase 00."
    )
    event_type = models.CharField(max_length=80, db_index=True)
    payload = models.JSONField()
    #: Clé d'idempotence de publication ("" = pas de déduplication).
    dedup_key = models.CharField(max_length=120, blank=True, default="")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending", db_index=True)
    #: Date à partir de laquelle l'événement est éligible (backoff des reprises).
    available_at = models.DateTimeField(null=True, blank=True, db_index=True)
    dispatched_at = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    last_error = models.TextField(blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["status", "available_at"]),
            models.Index(fields=["aggregate", "aggregate_id", "created_at"]),
        ]
        constraints = [
            models.UniqueConstraint(fields=["dedup_key"], name="uniq_outbox_dedup_key",
                                    condition=models.Q(dedup_key__gt="")),
        ]



class FinancialApproval(TimeStampedModel):
    """Trace persistante d'une contresignature d'opération financière (P0-02).

    Une approbation n'est valable que pour **une** opération : `operation_hash`
    est le SHA-256 de l'empreinte canonique (type + référence + montant +
    décision). Rejouer une assertion sur une autre opération produit un hash
    différent, donc aucune approbation exploitable.

    Les contraintes d'unicité rendent le double comptage impossible au niveau
    base de données, indépendamment du code applicatif.
    """

    OPERATION_DISPUTE_DECIDE = "dispute.decide"
    OPERATION_PLATFORM_FREEZE = "platform.freeze"
    OPERATION_PLATFORM_UNFREEZE = "platform.unfreeze"
    OPERATION_FREEZE_LIFT = "freeze.lift"

    id = models.CharField(max_length=26, primary_key=True, default=generate_ulid, editable=False)
    operation_type = models.CharField(max_length=50, db_index=True)
    operation_ref = models.CharField(max_length=100, blank=True, db_index=True)
    operation_hash = models.CharField(max_length=64, db_index=True)
    operation_payload = models.TextField(blank=True)
    tenant_id = models.CharField(
        max_length=26,
        db_index=True,
        help_text="Identifiant du tenant (institution) — Phase 00."
    )
    approver_id = models.CharField(max_length=26, db_index=True)
    credential_id = models.CharField(max_length=255)
    sign_count = models.BigIntegerField(default=0)
    challenge = models.CharField(max_length=255, blank=True)
    consumed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["operation_hash", "approver_id"],
                                    name="uniq_approval_per_operation_approver"),
            models.UniqueConstraint(fields=["operation_hash", "credential_id"],
                                    name="uniq_approval_per_operation_credential"),
        ]
        indexes = [models.Index(fields=["operation_hash", "created_at"])]

    def __str__(self) -> str:  # pragma: no cover - confort de debug
        return f"{self.operation_type}:{self.operation_ref} ← {self.approver_id}"
