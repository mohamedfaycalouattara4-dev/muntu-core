"""Métriques Prometheus KALYCE (registre process unique).

Exposées sur `GET /api/v1/metrics` (protégé par `METRICS_TOKEN` si défini).
Le registre par défaut de `prometheus_client` est utilisé afin de conserver
les métriques process (GC, mémoire) fournies nativement.
"""
from __future__ import annotations

from typing import Any

from prometheus_client import (
    CONTENT_TYPE_LATEST, REGISTRY, Counter, Gauge, Histogram, generate_latest,
)

__all__ = [
    "CONTENT_TYPE_LATEST", "render_latest",
    "HTTP_REQUESTS", "HTTP_LATENCY", "IDEMPOTENCY_EVENTS",
    "LEDGER_ENTRIES", "LEDGER_AMOUNT", "LEDGER_POSTINGS", "LEDGER_LAST_ENTRY_TS",
    "WEBHOOK_EVENTS", "OTP_VERIFICATIONS", "ORDER_TRANSITIONS",
]


def _metric(cls: Any, name: str, doc: str, labels: list[str], **kwargs: Any):
    """Idempotent : renvoie le collector existant si déjà enregistré.

    Nécessaire car Django peut réimporter le module (autoreload, workers,
    suites de tests) et `prometheus_client` refuse les doublons.
    """
    existing = REGISTRY._names_to_collectors.get(name) or \
        REGISTRY._names_to_collectors.get(f"{name}_total")
    if existing is not None:
        return existing
    try:
        return cls(name, doc, labels, **kwargs) if labels else cls(name, doc, **kwargs)
    except ValueError:  # pragma: no cover - course d'import
        return REGISTRY._names_to_collectors[name]


HTTP_REQUESTS = _metric(
    Counter, "kalyce_http_requests", "Requêtes HTTP traitées",
    ["method", "route", "status"])
HTTP_LATENCY = _metric(
    Histogram, "kalyce_http_request_duration_seconds", "Latence HTTP (s)",
    ["method", "route"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0))
IDEMPOTENCY_EVENTS = _metric(
    Counter, "kalyce_idempotency_events", "Événements du middleware d'idempotence",
    ["result"])
LEDGER_ENTRIES = _metric(
    Counter, "kalyce_ledger_entries", "Écritures comptables postées",
    ["account", "direction"])
LEDGER_AMOUNT = _metric(
    Counter, "kalyce_ledger_amount_xof", "Montants postés au ledger (XOF)",
    ["account", "direction"])
LEDGER_POSTINGS = _metric(
    Counter, "kalyce_ledger_postings", "Transactions ledger (double entrée)",
    ["result"])
LEDGER_LAST_ENTRY_TS = _metric(
    Gauge, "kalyce_ledger_last_entry_timestamp_seconds",
    "Horodatage de la dernière écriture ledger", [])
WEBHOOK_EVENTS = _metric(
    Counter, "kalyce_payment_webhook_events", "Webhooks agrégateurs reçus",
    ["aggregator", "result"])
OTP_VERIFICATIONS = _metric(
    Counter, "kalyce_otp_verifications", "Vérifications OTP de livraison",
    ["result"])
ORDER_TRANSITIONS = _metric(
    Counter, "kalyce_order_transitions", "Transitions FSM de commande",
    ["from_state", "to_state"])


def render_latest() -> bytes:
    return generate_latest(REGISTRY)
