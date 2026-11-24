"""Tâche Beat : publication des événements outbox.

La publication est volontairement séparée de l'écriture métier. Cette tâche est
sans état : si un worker meurt en plein vol, l'événement reste `pending` et
repart au tour suivant (au-moins-une-fois).
"""
from __future__ import annotations

import logging

from celery import shared_task

from apps.core.services import outbox
from apps.core.services import outbox_handlers  # noqa: F401 - enregistre les handlers

logger = logging.getLogger("muntu.outbox")


@shared_task(name="apps.core.tasks.dispatch_outbox")
def dispatch_outbox(limit: int = 200) -> dict:
    stats = outbox.dispatch_pending(limit=limit)
    if stats["dispatched"] or stats["failed"]:
        logger.info("Outbox: %s", stats)
    return stats


@shared_task(name="apps.core.tasks.replay_failed_outbox")
def replay_failed_outbox(aggregate: str | None = None, limit: int = 100) -> int:
    """Reprise manuelle de la file morte, après correction d'un consommateur."""
    return outbox.replay_failed(aggregate=aggregate, limit=limit)
