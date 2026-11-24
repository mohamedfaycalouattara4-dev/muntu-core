"""Catalogue des webhooks entrants et des événements sortants KALYCE.

Source unique de vérité pour :
  * la documentation OpenAPI (section ``webhooks`` de l'OAS 3.1) ;
  * l'endpoint public ``GET /api/v1/webhooks/events/`` destiné aux intégrateurs ;
  * les tests de contrat (chaque exemple doit rester valide).

Convention d'enveloppe des événements sortants ::

    {
      "event": "<domaine>.<action>",
      "event_id": "<ULID>",            # idempotence côté consommateur
      "occurred_at": "<ISO-8601 UTC>",
      "reference": "order:<id>",       # clé de corrélation ledger/logs
      "data": { ... }                  # charge utile spécifique
    }

Signature : ``X-Kalyce-Signature: sha256=<hmac>`` calculé sur le corps brut
avec le secret partagé, comparé en temps constant. Rejouer un événement déjà
traité doit être sans effet (``event_id`` = clé d'idempotence).
"""
from __future__ import annotations

from typing import Any

SIGNATURE_HEADER = "X-Kalyce-Signature"
IDEMPOTENCY_HEADER = "Idempotency-Key"

# --------------------------------------------------------------------------
# 1. Webhooks ENTRANTS : agrégateur de paiement -> KALYCE
#    POST /api/v1/webhooks/payment/{aggregator}/
# --------------------------------------------------------------------------
INBOUND_WEBHOOKS: dict[str, dict[str, Any]] = {
    "payment.captured": {
        "summary": "Paiement capturé (fonds placés en séquestre)",
        "description": (
            "Notification d'encaissement. KALYCE applique le **Pull-After-Push** : "
            "l'agrégateur est ré-interrogé (`query`) avant toute transition d'état. "
            "Le webhook seul ne fait jamais foi."
        ),
        "endpoint": "POST /api/v1/webhooks/payment/{aggregator}/",
        "headers": {SIGNATURE_HEADER: "sha256=6f1c…c0de",
                    "Content-Type": "application/json"},
        "payload": {
            "event": "payment.captured",
            "aggregator_ref": "ORANGE-9F2K-77120",
            "order_id": "0f8d9d5c-3f5b-4d5f-9d43-2c9a1e2b7c11",
            "amount_xof": 28_000,
            "currency": "XOF",
            "status": "CAPTURED",
            "idempotency_key": "pay_01HZX8Y7QK3N2M",
            "occurred_at": "2025-03-04T10:32:11Z",
        },
        "response": {"status": "ok"},
    },
    "payment.failed": {
        "summary": "Échec de paiement",
        "description": "Aucune écriture de ledger n'est produite ; la commande reste "
                       "en `EN_ATTENTE_PAIEMENT` jusqu'à expiration.",
        "endpoint": "POST /api/v1/webhooks/payment/{aggregator}/",
        "headers": {SIGNATURE_HEADER: "sha256=a91b…f004"},
        "payload": {
            "event": "payment.failed",
            "aggregator_ref": "WAVE-2K1L-44810",
            "order_id": "0f8d9d5c-3f5b-4d5f-9d43-2c9a1e2b7c11",
            "amount_xof": 28_000,
            "status": "FAILED",
            "failure_code": "INSUFFICIENT_FUNDS",
            "occurred_at": "2025-03-04T10:33:02Z",
        },
        "response": {"status": "ignored"},
    },
    "payment.refund_settled": {
        "summary": "Remboursement confirmé par l'agrégateur",
        "endpoint": "POST /api/v1/webhooks/payment/{aggregator}/",
        "headers": {SIGNATURE_HEADER: "sha256=17aa…9b31"},
        "payload": {
            "event": "payment.refund_settled",
            "aggregator_ref": "ORANGE-9F2K-77120",
            "order_id": "0f8d9d5c-3f5b-4d5f-9d43-2c9a1e2b7c11",
            "amount_xof": 28_000,
            "status": "REFUNDED",
            "idempotency_key": "rfd_01HZX9A2BC4D5E",
            "occurred_at": "2025-03-05T08:12:44Z",
        },
        "response": {"status": "ok"},
    },
}

# --------------------------------------------------------------------------
# 2. Événements SORTANTS : KALYCE -> partenaire (outbox, at-least-once)
# --------------------------------------------------------------------------
OUTBOUND_EVENTS: dict[str, dict[str, Any]] = {
    "order.created": {
        "summary": "Commande créée, en attente de paiement",
        "payload": {
            "event": "order.created",
            "event_id": "01HZX8Y7QK3N2MFRT5W9B0CDEF",
            "occurred_at": "2025-03-04T10:30:00Z",
            "reference": "order:0f8d9d5c-3f5b-4d5f-9d43-2c9a1e2b7c11",
            "data": {
                "order_id": "0f8d9d5c-3f5b-4d5f-9d43-2c9a1e2b7c11",
                "order_number": "KLY-250304-7F2K9QAB",
                "session_id": "6b0f2f9e-1a2b-4c3d-8e9f-0a1b2c3d4e5f",
                "state": "EN_ATTENTE_PAIEMENT",
                "subtotal_xof": 26_500,
                "delivery_fee_xof": 1_500,
                "total_xof": 28_000,
                "lines": [
                    {"product_name": "Ensemble Faso Dan Fani",
                     "quantity": 1, "unit_price_xof": 25_000},
                    {"product_name": "Beurre de karité 500g",
                     "quantity": 1, "unit_price_xof": 1_500},
                ],
            },
        },
    },
    "order.state_changed": {
        "summary": "Transition d'état de commande (machine à états auditée)",
        "payload": {
            "event": "order.state_changed",
            "event_id": "01HZX8ZB3M4P5Q6R7S8T9UVWXY",
            "occurred_at": "2025-03-04T10:32:12Z",
            "reference": "order:0f8d9d5c-3f5b-4d5f-9d43-2c9a1e2b7c11",
            "data": {
                "order_id": "0f8d9d5c-3f5b-4d5f-9d43-2c9a1e2b7c11",
                "from_state": "EN_ATTENTE_PAIEMENT",
                "to_state": "PAYEE_FONDS_RESERVES",
                "trigger": "payment_confirmed",
                "actor_type": "AGGREGATOR",
                "actor_id": "ORANGE",
            },
        },
    },
    "escrow.funds_held": {
        "summary": "Fonds séquestrés — écritures ledger en partie double",
        "payload": {
            "event": "escrow.funds_held",
            "event_id": "01HZX900A1B2C3D4E5F6G7H8IJ",
            "occurred_at": "2025-03-04T10:32:12Z",
            "reference": "order:0f8d9d5c-3f5b-4d5f-9d43-2c9a1e2b7c11",
            "data": {
                "amount_xof": 28_000,
                "entries": [
                    {"account": "CASH_AGGREGATOR", "direction": "DEBIT", "amount_xof": 28_000},
                    {"account": "ESCROW_LIABILITY", "direction": "CREDIT", "amount_xof": 28_000},
                ],
            },
        },
    },
    "delivery.mission_assigned": {
        "summary": "Mission de livraison attribuée à un livreur",
        "payload": {
            "event": "delivery.mission_assigned",
            "event_id": "01HZX91K2L3M4N5P6Q7R8S9TUV",
            "occurred_at": "2025-03-04T11:05:00Z",
            "reference": "order:0f8d9d5c-3f5b-4d5f-9d43-2c9a1e2b7c11",
            "data": {
                "mission_id": "b3c4d5e6-7f80-4912-a3b4-c5d6e7f80912",
                "deliverer_id": "8a7b6c5d-4e3f-4021-9a8b-7c6d5e4f3021",
                "deadline": "2025-03-04T15:05:00Z",
                "fee_xof": 1_500,
                "pickup_address": {"city": "Ouagadougou", "district": "Zone du Bois"},
            },
        },
    },
    "delivery.otp_validated": {
        "summary": "Livraison scellée : OTP validé + preuve photo + géofence",
        "description": "Le code OTP n'apparaît **jamais** dans l'événement : seul le "
                       "sceau (hash Argon2id + signature) est diffusé.",
        "payload": {
            "event": "delivery.otp_validated",
            "event_id": "01HZX92V3W4X5Y6Z7A8B9C0DEF",
            "occurred_at": "2025-03-04T12:41:07Z",
            "reference": "order:0f8d9d5c-3f5b-4d5f-9d43-2c9a1e2b7c11",
            "data": {
                "mission_id": "b3c4d5e6-7f80-4912-a3b4-c5d6e7f80912",
                "geo_valid": True,
                "distance_m": 34,
                "photo_sha256": "9c1185a5c5e9fc54612808977ee8f548b2258d31",
                "seal_signature": "e3b0c44298fc1c149afbf4c8996fb924…",
            },
        },
    },
    "escrow.funds_released": {
        "summary": "Fonds libérés au vendeur (J+0 après livraison scellée)",
        "payload": {
            "event": "escrow.funds_released",
            "event_id": "01HZX93G4H5J6K7L8M9N0P1QRS",
            "occurred_at": "2025-03-04T12:56:07Z",
            "reference": "order:0f8d9d5c-3f5b-4d5f-9d43-2c9a1e2b7c11",
            "data": {
                "vendor_amount_xof": 25_175,
                "platform_revenue_xof": 1_325,
                "delivery_payable_xof": 1_500,
                "entries": [
                    {"account": "ESCROW_LIABILITY", "direction": "DEBIT", "amount_xof": 28_000},
                    {"account": "VENDOR_PAYABLE", "direction": "CREDIT", "amount_xof": 25_175},
                    {"account": "PLATFORM_REVENUE", "direction": "CREDIT", "amount_xof": 1_325},
                    {"account": "DELIVERY_PAYABLE", "direction": "CREDIT", "amount_xof": 1_500},
                ],
            },
        },
    },
    "escrow.refunded": {
        "summary": "Remboursement acheteur (litige ou délai d'expédition dépassé)",
        "payload": {
            "event": "escrow.refunded",
            "event_id": "01HZX94T5U6V7W8X9Y0Z1A2BCD",
            "occurred_at": "2025-03-05T08:12:45Z",
            "reference": "order:0f8d9d5c-3f5b-4d5f-9d43-2c9a1e2b7c11",
            "data": {"amount_xof": 28_000, "reason": "shipping_delay_exceeded"},
        },
    },
    "dispute.opened": {
        "summary": "Litige ouvert : le séquestre est gelé",
        "payload": {
            "event": "dispute.opened",
            "event_id": "01HZX95E6F7G8H9J0K1L2M3NPQ",
            "occurred_at": "2025-03-05T09:00:00Z",
            "reference": "order:0f8d9d5c-3f5b-4d5f-9d43-2c9a1e2b7c11",
            "data": {
                "dispute_id": "d1e2f3a4-b5c6-4778-89a0-b1c2d3e4f5a6",
                "reason": "PRODUIT_NON_CONFORME",
                "opened_by": "BUYER",
                "sla_deadline": "2025-03-08T09:00:00Z",
                "evidence_count": 2,
            },
        },
    },
    "dispute.resolved": {
        "summary": "Litige arbitré : issue et répartition des fonds",
        "payload": {
            "event": "dispute.resolved",
            "event_id": "01HZX96R7S8T9U0V1W2X3Y4ZAB",
            "occurred_at": "2025-03-06T14:20:00Z",
            "reference": "order:0f8d9d5c-3f5b-4d5f-9d43-2c9a1e2b7c11",
            "data": {
                "dispute_id": "d1e2f3a4-b5c6-4778-89a0-b1c2d3e4f5a6",
                "resolution": "REFUND_BUYER",
                "refunded_xof": 28_000,
                "arbitrated_by": "OPERATOR",
            },
        },
    },
    "risk.alert_raised": {
        "summary": "Alerte anti-fraude / seuil BCEAO franchi",
        "payload": {
            "event": "risk.alert_raised",
            "event_id": "01HZX97C8D9E0F1G2H3J4K5LMN",
            "occurred_at": "2025-03-06T15:00:00Z",
            "reference": "user:8a7b6c5d-4e3f-4021-9a8b-7c6d5e4f3021",
            "data": {
                "rule": "KYC_BCEAO_THRESHOLD_XOF",
                "threshold_xof": 10_000_000,
                "observed_xof": 10_450_000,
                "severity": "HIGH",
                "action": "WITHDRAWALS_FROZEN",
            },
        },
    },
}

ALL_EVENTS: dict[str, dict[str, Any]] = {
    "inbound": INBOUND_WEBHOOKS,
    "outbound": OUTBOUND_EVENTS,
}


def openapi_webhooks() -> dict[str, Any]:
    """Construit la section ``webhooks`` de l'OpenAPI 3.1 à partir du catalogue."""
    webhooks: dict[str, Any] = {}
    for name, spec in OUTBOUND_EVENTS.items():
        webhooks[name] = {
            "post": {
                "tags": ["Webhooks & événements"],
                "summary": spec["summary"],
                "description": spec.get("description", ""),
                "operationId": f"event_{name.replace('.', '_')}",
                "parameters": [{
                    "in": "header", "name": SIGNATURE_HEADER, "required": True,
                    "schema": {"type": "string"},
                    "description": "HMAC-SHA256 du corps brut, préfixé `sha256=`.",
                }],
                "requestBody": {
                    "required": True,
                    "content": {"application/json": {
                        "schema": {"$ref": "#/components/schemas/WebhookEnvelope"},
                        "examples": {name: {"summary": spec["summary"],
                                            "value": spec["payload"]}},
                    }},
                },
                "responses": {
                    "200": {"description": "Événement accepté (accusé de réception)."},
                    "401": {"description": "Signature HMAC invalide."},
                },
            }
        }
    return webhooks
