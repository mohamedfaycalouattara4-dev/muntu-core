"""Audit · journal quinquennal.bétonné (V2 §10.5)."""
from django.db import models
from apps.core.models import TimeStampedModel, generate_ulid


class AuditEvent(TimeStampedModel):
    entity_type = models.CharField(max_length=100, db_index=True)
    entity_id = models.CharField(max_length=200, db_index=True)
    action = models.CharField(max_length=100)
    payload = models.JSONField(default=dict)
    actor_id = models.CharField(max_length=100, blank=True)
    actor_ip = models.CharField(max_length=64, blank=True)
    previous_hash = models.CharField(max_length=64, default="0" * 64, db_index=True)
    current_hash = models.CharField(max_length=64, unique=True)
    signature = models.TextField()

    class Meta:
        ordering = ["id"]
        indexes = [models.Index(fields=["entity_type", "entity_id"])]


class MerkleAnchor(TimeStampedModel):
    day = models.DateField(primary_key=True)
    root = models.CharField(max_length=64)
    entries_count = models.IntegerField(default=0)
    rfc3161_proof = models.TextField(blank=True)
