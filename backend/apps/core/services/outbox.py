"""Étape 5 · Outbox transactionnel : un seul écrit, plusieurs effets.

Le problème que ce module résout est la **double écriture**. Une transition
d'état qui, dans la même foulée, appelle un service externe (notification,
agrégateur de paiement, websocket) a deux façons de mentir :

* la transaction est validée mais l'appel échoue → l'effet promis n'arrive
  jamais ;
* l'appel réussit puis la transaction est annulée → un effet existe pour un
  fait qui n'a jamais eu lieu.

La parade est d'écrire l'intention **dans la même transaction que le fait**
(table `core_outboxevent`), puis de la publier depuis un processus séparé. On
échange une cohérence forte impossible contre une cohérence à terme honnête :
au-moins-une-fois côté publication, l'idempotence étant à la charge du
consommateur (`dedup_key`).

Ordre garanti : par agrégat (`aggregate` + `aggregate_id`), pas globalement.
Un événement en échec bloque volontairement ses cadets du même agrégat — sinon
un « colis livré » pourrait précéder son « colis expédié ».
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import timedelta
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.core.models import OutboxEvent

logger = logging.getLogger("muntu.outbox")

#: Nombre de tentatives avant mise au rebut (statut `failed` = file morte).
MAX_ATTEMPTS = 8
#: Backoff exponentiel plafonné (secondes) : 2, 4, 8 … 600.
BACKOFF_BASE_SECONDS = 2
BACKOFF_MAX_SECONDS = 600

_HANDLERS: dict[str, Callable[[OutboxEvent], None]] = {}


def register_handler(event_type: str):
    """Enregistre le consommateur d'un type d'événement."""

    def decorator(func: Callable[[OutboxEvent], None]):
        _HANDLERS[event_type] = func
        return func

    return decorator


def handlers() -> dict[str, Callable[[OutboxEvent], None]]:
    return dict(_HANDLERS)


def backoff_seconds(attempts: int) -> int:
    return min(BACKOFF_BASE_SECONDS ** max(1, attempts), BACKOFF_MAX_SECONDS)


def publish(*, aggregate: str, aggregate_id: str, event_type: str,
            payload: dict[str, Any], dedup_key: str = "") -> OutboxEvent | None:
    """Enregistre un événement à publier. **À appeler dans la transaction métier.**

    `dedup_key` rend l'écriture idempotente : republier la même intention (rejeu
    d'un webhook, tâche relancée) ne crée pas de doublon.
    """
    if dedup_key:
        existing = OutboxEvent.objects.filter(dedup_key=dedup_key).first()
        if existing is not None:
            return existing
    return OutboxEvent.objects.create(
        aggregate=aggregate, aggregate_id=str(aggregate_id), event_type=event_type,
        payload=payload, dedup_key=dedup_key or "",
        available_at=timezone.now(), status="pending")


def _blocked_aggregates() -> set[tuple[str, str]]:
    """Agrégats dont un événement est en échec définitif : on gèle leur suite."""
    return {
        (row["aggregate"], row["aggregate_id"])
        for row in OutboxEvent.objects.filter(status="failed")
        .values("aggregate", "aggregate_id").distinct()
    }


def dispatch_pending(limit: int = 100) -> dict[str, int]:
    """Publie les événements dus. Idempotent, sûr en concurrence.

    `SKIP LOCKED` est ici légitime — contrairement au stock : plusieurs workers
    doivent se répartir une file, et un événement déjà pris par un pair n'a pas
    besoin d'être attendu.
    """
    stats = {"dispatched": 0, "retried": 0, "failed": 0, "skipped": 0}
    blocked = _blocked_aggregates()
    now = timezone.now()
    candidate_ids = list(
        OutboxEvent.objects.filter(status="pending", available_at__lte=now)
        .order_by("created_at", "id").values_list("id", flat=True)[:limit]
    )
    seen_aggregates: set[tuple[str, str]] = set()
    for event_id in candidate_ids:
        with transaction.atomic():
            event = (OutboxEvent.objects.select_for_update(skip_locked=True)
                     .filter(pk=event_id, status="pending").first())
            if event is None:
                stats["skipped"] += 1
                continue
            key = (event.aggregate, event.aggregate_id)
            if key in blocked or key in seen_aggregates:
                # Ordre par agrégat : on ne double pas un événement plus ancien.
                stats["skipped"] += 1
                continue
            handler = _HANDLERS.get(event.event_type)
            if handler is None:
                # Aucun consommateur : ce n'est pas une erreur, l'événement reste
                # une trace exploitable (projections, rejeu ultérieur).
                event.status = "dispatched"
                event.dispatched_at = timezone.now()
                event.last_error = "no_handler"
                event.save(update_fields=["status", "dispatched_at", "last_error",
                                          "updated_at"])
                stats["dispatched"] += 1
                continue
            try:
                handler(event)
            except Exception as exc:  # noqa: BLE001 - la file doit survivre à tout
                event.attempts += 1
                event.last_error = f"{type(exc).__name__}: {exc}"[:2000]
                if event.attempts >= MAX_ATTEMPTS:
                    event.status = "failed"
                    blocked.add(key)
                    stats["failed"] += 1
                    logger.error("Outbox event %s abandonné après %d tentatives: %s",
                                 event.id, event.attempts, event.last_error)
                else:
                    event.available_at = timezone.now() + timedelta(
                        seconds=backoff_seconds(event.attempts))
                    seen_aggregates.add(key)
                    stats["retried"] += 1
                event.save(update_fields=["attempts", "last_error", "status",
                                          "available_at", "updated_at"])
            else:
                event.status = "dispatched"
                event.dispatched_at = timezone.now()
                event.attempts += 1
                event.save(update_fields=["status", "dispatched_at", "attempts",
                                          "updated_at"])
                stats["dispatched"] += 1
    return stats


def replay_failed(*, aggregate: str | None = None, limit: int = 100) -> int:
    """Remet en file des événements abandonnés (après correction d'un bug)."""
    qs = OutboxEvent.objects.filter(status="failed")
    if aggregate:
        qs = qs.filter(aggregate=aggregate)
    ids = list(qs.order_by("created_at").values_list("id", flat=True)[:limit])
    return OutboxEvent.objects.filter(id__in=ids).update(
        status="pending", attempts=0, last_error="", available_at=timezone.now())
