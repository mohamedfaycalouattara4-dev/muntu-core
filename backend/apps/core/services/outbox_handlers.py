"""Consommateurs des événements outbox.

Les gestionnaires doivent être **idempotents** : la publication est
« au-moins-une-fois », donc un même événement peut être remis. Ils doivent
aussi être avares en effets de bord non rejouables (pas d'écriture financière
ici : le grand livre a sa propre voie transactionnelle).
"""
from __future__ import annotations

import hashlib

import logging

from apps.core.models import CROCKFORD32, OutboxEvent
from apps.core.services import realtime
from apps.core.services.outbox import register_handler

logger = logging.getLogger("muntu.outbox")


@register_handler("live_session.state_changed")
def _on_session_state_changed(event: OutboxEvent) -> None:
    payload = event.payload or {}
    realtime.broadcast_session_state(payload.get("session_id", ""),
                                     payload.get("to_state", ""))


@register_handler("stock.updated")
def _on_stock_updated(event: OutboxEvent) -> None:
    payload = event.payload or {}
    realtime.broadcast_stock(payload.get("session_id", ""),
                             payload.get("product_id", ""),
                             int(payload.get("available", 0)))


@register_handler("order.state_changed")
def _on_order_state_changed(event: OutboxEvent) -> None:
    """Notifie l'acheteur et le vendeur d'un changement d'état de commande.

    L'identifiant de la notification est **dérivé** de l'événement et du
    destinataire : republier l'événement retombe sur la même clé primaire, donc
    aucun doublon, sans colonne de déduplication supplémentaire.
    """
    payload = event.payload or {}
    try:
        from apps.notifications.models import Notification
    except Exception:  # noqa: BLE001 - application absente ou non migrée
        logger.debug("Notifications indisponibles, événement %s ignoré", event.id)
        return

    base = event.dedup_key or f"outbox:{event.id}"
    for recipient in filter(None, [payload.get("buyer_id"), payload.get("vendor_id")]):
        Notification.objects.get_or_create(
            id=deterministic_id(f"{base}:{recipient}"),
            defaults={"recipient_id": recipient, "channel": "push",
                      "template_key": "order.state_changed",
                      "payload": payload, "state": "pending"},
        )


def deterministic_id(seed: str) -> str:
    """ULID-compatible : 26 caractères Crockford dérivés d'un SHA-256."""
    digest = hashlib.sha256(seed.encode()).digest()
    value = int.from_bytes(digest[:16], "big")
    out = []
    for _ in range(26):
        value, rem = divmod(value, 32)
        out.append(CROCKFORD32[rem])
    return "".join(reversed(out))
