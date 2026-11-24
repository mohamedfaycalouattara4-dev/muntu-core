"""Réception webhook agrégateur + Pull-After-Push — V2 §9.5.

Domaine microfinance : le webhook porte l'institution (`tenant_id`) et la
finalité de l'opération (`purpose`). Aucune notion de commande/séquestre.
"""
from __future__ import annotations

import logging
import secrets

from django.db import transaction

from ..models import Payment, PaymentState
from ..services.adapters import registry as adapters_registry
from ..services.payments import VALID_PURPOSES, PaymentError, complete_payment
from ..services.signature import verify_aggregator_signature

logger = logging.getLogger("muntu.payments.webhooks")

REQUIRED_FIELDS = ("tenant_id", "amount_xof", "purpose", "aggregator_ref")


def _ensure_payment(*, tenant_id: str, purpose: str, aggregator: str,
                    aggregator_ref: str, amount_xof: int,
                    idempotency_key: str, member_id: str = "",
                    loan_id: str = "", savings_account_id: str = "") -> Payment:
    payment, _ = Payment.objects.get_or_create(
        idempotency_key=idempotency_key,
        defaults={
            "tenant_id": tenant_id,
            "member_id": member_id,
            "loan_id": loan_id,
            "savings_account_id": savings_account_id,
            "aggregator": aggregator,
            "aggregator_ref": aggregator_ref,
            "means": aggregator,
            "amount_xof": int(amount_xof),
            "state": PaymentState.CAPTURED,
        },
    )
    if payment.state == PaymentState.INITIALIZED or payment.state == PaymentState.AUTHORIZED:
        payment.state = PaymentState.CAPTURED
        payment.aggregator_ref = aggregator_ref or payment.aggregator_ref
        payment.save(update_fields=["state", "aggregator_ref", "updated_at"])
    return payment


def process_webhook(*, aggregator: str, raw_body: bytes,
                    signature_header: str | None,
                    payload: dict) -> str:
    """Vérifie la signature HMAC puis ré-interroge l'agrégateur avant transition.

    Returns:
        "ok" si le paiement a été enregistré, "ignored" sinon.

    Raises:
        ValueError: signature invalide ou charge utile incomplète.
    """
    if not verify_aggregator_signature(raw_body, signature_header):
        raise ValueError("invalid webhook signature")

    missing = [f for f in REQUIRED_FIELDS if not payload.get(f)]
    if missing:
        raise ValueError(f"champs webhook manquants : {', '.join(missing)}")
    purpose = payload["purpose"]
    if purpose not in VALID_PURPOSES:
        raise ValueError(f"finalité inconnue : {purpose}")

    # Pull-After-Push : la notification seule ne fait jamais foi.
    aggregator_ref = payload["aggregator_ref"]
    intent = adapters_registry.get(aggregator).query(aggregator_ref=aggregator_ref)
    if intent.status != "CAPTURED":
        logger.info("webhook_ignored", extra={"aggregator_ref": aggregator_ref,
                                              "status": intent.status})
        return "ignored"

    return _register_payment_success(
        tenant_id=payload["tenant_id"],
        purpose=purpose,
        aggregator=aggregator,
        aggregator_ref=aggregator_ref,
        amount_xof=int(payload["amount_xof"]),
        idempotency_key=payload.get("idempotency_key") or secrets.token_hex(16),
        member_id=payload.get("member_id", ""),
        loan_id=payload.get("loan_id", ""),
        savings_account_id=payload.get("savings_account_id", ""),
    )


@transaction.atomic
def _register_payment_success(*, tenant_id: str, purpose: str, aggregator: str,
                              aggregator_ref: str, amount_xof: int,
                              idempotency_key: str, member_id: str = "",
                              loan_id: str = "",
                              savings_account_id: str = "") -> str:
    """Enregistre l'encaissement et produit les écritures du grand livre."""
    payment = _ensure_payment(
        tenant_id=tenant_id, purpose=purpose, aggregator=aggregator,
        aggregator_ref=aggregator_ref, amount_xof=amount_xof,
        idempotency_key=idempotency_key, member_id=member_id,
        loan_id=loan_id, savings_account_id=savings_account_id,
    )
    try:
        result = complete_payment(tenant_id=tenant_id, payment_id=payment.id,
                                  purpose=purpose, recorded_by="webhook")
    except PaymentError:
        logger.exception("webhook_completion_failed",
                         extra={"payment_id": payment.id, "tenant_id": tenant_id})
        raise

    logger.info("webhook_processed", extra={
        "aggregator_ref": aggregator_ref, "tenant_id": tenant_id,
        "payment_id": payment.id, "result": result,
    })
    return "ok"
