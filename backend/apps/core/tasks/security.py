"""Tâches Beat — intégrité ledger, Merkle, rotation, SOC."""
from __future__ import annotations

import hashlib
import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger("muntu.security")


@shared_task(name="apps.core.tasks.verify_ledger_chain")
def verify_ledger_chain() -> int:
    """Recalcule le hash de chaîne ledger sur les 24 dernières heures.

    Renvoie le nombre d'incohérences détectées (0 si tout va bien).
    """
    from apps.payments.models import LedgerEntry  # noqa: PLC0415
    since = timezone.now() - timedelta(hours=24)
    qs = LedgerEntry.objects.filter(created_at__gte=since).order_by("id")
    previous = "0" * 64
    broken = 0
    for entry in qs:
        expected = hashlib.sha256(f"{previous}|{entry.entry_hash}".encode()).hexdigest()
        if expected != entry.previous_hash:
            broken += 1
        previous = entry.entry_hash
    if broken:
        logger.critical("Ledger chain integrity BROKEN: %d mismatches", broken)
    else:
        logger.info("Ledger chain verified OK on %d entries", qs.count())
    return broken


@shared_task(name="apps.core.tasks.anchor_daily_merkle_root")
def anchor_daily_merkle_root() -> str | None:
    """Calcule la racine Merkle quotidienne et l'enregistre.

    Une production réelle appellerait ici un TSA RFC 3161 ou un ancrage blockchain.
    """
    from apps.audit.models import AuditEvent  # noqa: PLC0415
    qs = AuditEvent.objects.filter(created_at__date=timezone.now().date()).order_by("id")
    layer = [e.current_hash for e in qs]
    if not layer:
        return None
    while len(layer) > 1:
        if len(layer) % 2:
            layer.append(layer[-1])
        layer = [hashlib.sha256(f"{layer[i]}{layer[i + 1]}".encode()).hexdigest()
                 for i in range(0, len(layer), 2)]
    root = layer[0]
    from apps.audit.models import MerkleAnchor  # noqa: PLC0415
    MerkleAnchor.objects.update_or_create(
        day=timezone.now().date(),
        defaults={"root": root, "entries_count": qs.count()},
    )
    logger.info("Merkle root anchored: %s (%d entries)", root, qs.count())
    return root


@shared_task(name="apps.core.tasks.cleanup_expired_nonces")
def cleanup_expired_nonces() -> int:
    from apps.core.models import UsedNonce  # noqa: PLC0415
    deleted, _ = UsedNonce.objects.filter(expires_at__lt=timezone.now()).delete()
    return deleted or 0


@shared_task(name="apps.core.tasks.rotate_signing_keys")
def rotate_signing_keys() -> bool:
    """Stub : en prod, interagit avec le KMS pour renouvellement 90 jours.

    Log un événement d'audit (rotation planifiée).
    """
    from apps.core.services.audit import emit  # noqa: PLC0415
    emit("system", "key-rotation", "check", {"interval_days": 90,
                                              "triggered_by": "celery-beat"})
    logger.info("Signing-key rotation check executed (90d cycle)")
    return True


@shared_task(name="apps.core.tasks.enqueue_soc_event")
def enqueue_soc_event(payload: str) -> None:
    """Stub SOC. En prod, POST vers `SOC_WEBHOOK_URL` via requests."""
    logger.warning("SOC event enqueued (would POST): %s", payload[:200])
