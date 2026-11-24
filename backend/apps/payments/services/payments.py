"""Services paiement — domaine microfinance (initiation, capture, remboursement).

Phase 02 : l'héritage commerce (commande, séquestre, reversement vendeur) est
entièrement supprimé. Un paiement est désormais rattaché à une **institution**
(`tenant_id`) et, selon le cas, à un membre, un compte d'épargne, un prêt ou
une session de caisse.
"""
from __future__ import annotations

import logging

from django.db import transaction
from django.utils import timezone

from ..models import Payment, PaymentState
from ..services.adapters import registry
from ..services.circuit_breaker import call as cb_call
from ..services.ledger import (
    post_loan_disbursement,
    post_loan_repayment,
    post_savings_deposit,
    post_savings_withdrawal,
)

logger = logging.getLogger("muntu.payments")


class PaymentError(Exception):
    """Erreur métier de paiement (état invalide, cible inconnue…)."""


#: Sens du flux monétaire, déterminé par la nature de l'opération.
PURPOSE_SAVINGS_DEPOSIT = "SAVINGS_DEPOSIT"
PURPOSE_SAVINGS_WITHDRAWAL = "SAVINGS_WITHDRAWAL"
PURPOSE_LOAN_DISBURSEMENT = "LOAN_DISBURSEMENT"
PURPOSE_LOAN_REPAYMENT = "LOAN_REPAYMENT"

VALID_PURPOSES = frozenset({
    PURPOSE_SAVINGS_DEPOSIT,
    PURPOSE_SAVINGS_WITHDRAWAL,
    PURPOSE_LOAN_DISBURSEMENT,
    PURPOSE_LOAN_REPAYMENT,
})


def build_reference(*, purpose: str, target_id: str, amount_xof: int) -> str:
    """Référence métier normalisée du grand livre."""
    return f"{purpose}:{target_id}:{amount_xof}"


def initiate_payment(
    *,
    tenant_id: str,
    amount_xof: int,
    aggregator: str,
    idempotency_key: str,
    purpose: str,
    member_id: str = "",
    loan_id: str = "",
    savings_account_id: str = "",
    teller_session_id: str = "",
    performed_by: str = "",
) -> Payment:
    """Initie un paiement pour une opération microfinance.

    Raises:
        PaymentError: montant non strictement positif, tenant absent ou
            finalité inconnue.
    """
    if not tenant_id:
        raise PaymentError("tenant_id obligatoire (isolation I2)")
    if purpose not in VALID_PURPOSES:
        raise PaymentError(f"Finalité de paiement inconnue : {purpose}")
    if int(amount_xof) <= 0:
        raise PaymentError("Le montant doit être strictement positif.")

    target_id = loan_id or savings_account_id or member_id or teller_session_id
    reference = build_reference(purpose=purpose, target_id=target_id,
                                amount_xof=int(amount_xof))

    with transaction.atomic():
        payment, created = Payment.objects.get_or_create(
            idempotency_key=idempotency_key,
            defaults={
                "tenant_id": tenant_id,
                "member_id": member_id,
                "loan_id": loan_id,
                "savings_account_id": savings_account_id,
                "teller_session_id": teller_session_id,
                "aggregator": aggregator,
                "means": aggregator or "INTERNAL",
                "amount_xof": int(amount_xof),
                "intent_created_at": timezone.now(),
                "state": PaymentState.INITIALIZED,
                "performed_by": performed_by,
            },
        )
    if not created:
        # Rejeu idempotent : on renvoie le paiement mémorisé tel quel.
        logger.info("payment_replayed", extra={"payment_id": payment.id,
                                               "tenant_id": tenant_id})
        return payment

    adapter = registry.get(aggregator)
    intent = cb_call(adapter.name, adapter.authorize,
                     reference=reference, amount_xof=int(amount_xof),
                     idempotency_key=idempotency_key)
    payment.aggregator_ref = intent.aggregator_ref
    payment.state = PaymentState.AUTHORIZED
    payment.save(update_fields=["aggregator_ref", "state", "updated_at"])
    logger.info("payment_initiated", extra={
        "payment_id": payment.id, "tenant_id": tenant_id,
        "amount_xof": payment.amount_xof, "purpose": purpose,
    })
    return payment


def _post_ledger(*, purpose: str, payment: Payment, reference: str,
                 recorded_by: str, day_id: str = "") -> None:
    """Traduit la finalité du paiement en écritures de grand livre."""
    common = {
        "reference": reference,
        "amount_xof": payment.amount_xof,
        "tenant_id": payment.tenant_id,
        "recorded_by": recorded_by,
        "day_id": day_id,
    }
    if purpose == PURPOSE_SAVINGS_DEPOSIT:
        post_savings_deposit(**common)
    elif purpose == PURPOSE_SAVINGS_WITHDRAWAL:
        post_savings_withdrawal(**common)
    elif purpose == PURPOSE_LOAN_DISBURSEMENT:
        post_loan_disbursement(**common)
    elif purpose == PURPOSE_LOAN_REPAYMENT:
        post_loan_repayment(
            reference=reference, principal_xof=payment.amount_xof,
            interest_xof=0, fee_xof=0, tenant_id=payment.tenant_id,
            recorded_by=recorded_by, day_id=day_id,
        )
    else:  # pragma: no cover - garde-fou
        raise PaymentError(f"Finalité de paiement inconnue : {purpose}")


def complete_payment(
    *,
    tenant_id: str,
    payment_id: str,
    purpose: str,
    recorded_by: str = "system",
    day_id: str = "",
) -> str:
    """Confirme un paiement autorisé/capturé et produit les écritures (I1).

    L'opération est idempotente : un paiement déjà `COMPLETED` ne reposte
    aucune écriture.
    """
    if purpose not in VALID_PURPOSES:
        raise PaymentError(f"Finalité de paiement inconnue : {purpose}")

    with transaction.atomic():
        payment = (Payment.objects.select_for_update()
                   .filter(tenant_id=tenant_id, id=payment_id).first())
        if payment is None:
            raise PaymentError("Paiement introuvable pour cette institution.")
        if payment.state == PaymentState.COMPLETED:
            return "already_completed"
        if payment.state not in {PaymentState.AUTHORIZED, PaymentState.CAPTURED}:
            raise PaymentError(
                f"Transition interdite depuis l'état {payment.state}.")

        target_id = (payment.loan_id or payment.savings_account_id
                     or payment.member_id or payment.teller_session_id)
        reference = build_reference(purpose=purpose, target_id=target_id,
                                    amount_xof=payment.amount_xof)
        _post_ledger(purpose=purpose, payment=payment, reference=reference,
                     recorded_by=recorded_by, day_id=day_id)

        payment.state = PaymentState.COMPLETED
        payment.completed_at = timezone.now()
        payment.save(update_fields=["state", "completed_at", "updated_at"])

    logger.info("payment_completed", extra={
        "payment_id": payment.id, "tenant_id": tenant_id,
        "amount_xof": payment.amount_xof, "purpose": purpose,
    })
    return "completed"


def refund_payment(*, tenant_id: str, payment_id: str, reason: str,
                   recorded_by: str = "system", day_id: str = "") -> str:
    """Rembourse un paiement d'épargne encaissé (contre-passation)."""
    with transaction.atomic():
        payment = (Payment.objects.select_for_update()
                   .filter(tenant_id=tenant_id, id=payment_id).first())
        if payment is None:
            raise PaymentError("Paiement introuvable pour cette institution.")
        if payment.state == PaymentState.REFUNDED:
            return "already_refunded"
        if payment.state not in {PaymentState.CAPTURED, PaymentState.COMPLETED}:
            raise PaymentError(
                f"Remboursement impossible depuis l'état {payment.state}.")

        if payment.aggregator:
            cb_call(payment.aggregator, registry.get(payment.aggregator).refund,
                    aggregator_ref=payment.aggregator_ref,
                    amount_xof=payment.amount_xof)

        target_id = (payment.savings_account_id or payment.member_id
                     or payment.loan_id or payment.teller_session_id)
        post_savings_withdrawal(
            reference=f"REFUND:{target_id}:{payment.id}",
            amount_xof=payment.amount_xof,
            tenant_id=payment.tenant_id,
            recorded_by=f"{recorded_by}:refund:{reason}"[:26],
            day_id=day_id,
        )
        payment.state = PaymentState.REFUNDED
        payment.refunded_at = timezone.now()
        payment.save(update_fields=["state", "refunded_at", "updated_at"])

    logger.info("payment_refunded", extra={
        "payment_id": payment.id, "tenant_id": tenant_id, "reason": reason,
    })
    return "refunded"
