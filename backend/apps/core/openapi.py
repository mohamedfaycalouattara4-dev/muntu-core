"""Hooks drf-spectacular : tags automatiques + section webhooks OAS 3.1."""
from __future__ import annotations

from typing import Any

from .webhook_examples import openapi_webhooks

TAG_BY_PREFIX = [
    ("/api/v1/auth/", "Authentification"),
    ("/api/v1/users/", "Comptes & KYC"),
    ("/api/v1/institutions/", "Institutions & multi-tenant"),
    ("/api/v1/members/", "Membres & adhésion"),
    ("/api/v1/savings/", "Épargne"),
    ("/api/v1/loans/", "Crédit"),
    ("/api/v1/teller/", "Caisse & guichet"),
    ("/api/v1/accounting/", "Comptabilité"),
    ("/api/v1/payments/", "Paiements & grand livre"),
    ("/api/v1/regulatory/", "États réglementaires"),
    ("/api/v1/claims/", "Réclamations"),
    ("/api/v1/documents/", "Documents & contrats"),
    ("/api/v1/risk/", "Risque & conformité"),
    ("/api/v1/audit/", "Audit"),
    ("/api/v1/health", "Exploitation"),
    ("/api/v1/metrics", "Exploitation"),
]

WEBHOOK_ENVELOPE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["event", "event_id", "occurred_at", "data"],
    "properties": {
        "event": {"type": "string", "example": "savings.deposit_completed"},
        "event_id": {"type": "string", "description": "ULID — clé d'idempotence."},
        "occurred_at": {"type": "string", "format": "date-time"},
        "reference": {"type": "string",
                      "description": "Corrélation ledger/logs, ex. `savings:SA-0001`."},
        "data": {"type": "object", "additionalProperties": True},
    },
}


def postprocess_schema(result, generator, request, public):  # noqa: ANN001, ARG001
    """Ajoute tags cohérents, webhooks et réponses d'erreur transverses."""
    for path, operations in result.get("paths", {}).items():
        tag = next((t for prefix, t in TAG_BY_PREFIX if path.startswith(prefix)), None)
        for method, operation in operations.items():
            if method not in {"get", "post", "put", "patch", "delete"}:
                continue
            if tag:
                operation["tags"] = [tag]
            if method in {"post", "put", "patch"}:
                operation.setdefault("parameters", []).append({
                    "in": "header", "name": "Idempotency-Key", "required": False,
                    "schema": {"type": "string", "maxLength": 128},
                    "description": (
                        "Rejoue la réponse mise en cache pour une requête identique. "
                        "Verrou atomique : une requête concurrente portant la même clé "
                        "reçoit `409`; une clé réutilisée avec une autre charge utile "
                        "reçoit `422`."),
                })
                operation.setdefault("responses", {}).setdefault(
                    "409", {"description": "Requête identique déjà en cours de traitement."})
                operation["responses"].setdefault(
                    "422", {"description": "Idempotency-Key réutilisée avec un autre payload."})
            operation.setdefault("responses", {}).setdefault(
                "429", {"description": "Quota de débit dépassé."})

    result.setdefault("components", {}).setdefault("schemas", {})[
        "WebhookEnvelope"] = WEBHOOK_ENVELOPE_SCHEMA
    result["webhooks"] = openapi_webhooks()
    return result
