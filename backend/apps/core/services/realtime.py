"""Diffusion temps réel (Channels) — tolérante à l'absence de couche.

Le temps réel est un confort : un stock qui n'arrive pas à l'écran doit
dégrader l'expérience, jamais faire échouer une transaction. Toutes les
fonctions de ce module sont donc *best effort* et silencieuses en cas
d'indisponibilité de la couche de canaux (tests, worker sans Redis).
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("muntu.realtime")


def group_name_session(session_id: str) -> str:
    return f"live.session.{session_id}"


def broadcast(group: str, message: dict[str, Any]) -> bool:
    """Envoie un message à un groupe. Retourne False si la diffusion n'a pas eu lieu."""
    try:
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer
    except Exception:  # noqa: BLE001 - channels non installé
        return False
    layer = get_channel_layer()
    if layer is None:
        return False
    try:
        async_to_sync(layer.group_send)(group, {"type": "broadcast.message", **message})
    except Exception as exc:  # noqa: BLE001 - Redis absent, canal saturé…
        logger.debug("Diffusion temps réel ignorée (%s): %s", group, exc)
        return False
    return True


def broadcast_stock(session_id: str, product_id: str, available: int) -> bool:
    return broadcast(group_name_session(session_id),
                     {"event": "stock.updated", "product_id": str(product_id),
                      "available": int(available)})


def broadcast_session_state(session_id: str, state: str) -> bool:
    return broadcast(group_name_session(session_id),
                     {"event": "session.state_changed", "state": state})
