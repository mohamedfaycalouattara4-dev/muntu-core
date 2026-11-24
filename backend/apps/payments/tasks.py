"""Celery tasks : reconciliation paiement, retry webhook."""
from __future__ import annotations

import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from .models import Payment, PaymentState
from .services.adapters import registry
from .services.circuit_breaker import call as cb_call

logger = logging.getLogger("muntu.payments")


@shared_task(name="apps.payments.tasks.reconcile_pending_payments")
def reconcile_pending_payments() -> int:
    cutoff = timezone.now() - timedelta(hours=24)
    qs = Payment.objects.filter(state=PaymentState.AUTHORIZED, intent_created_at__lt=cutoff).only(
        "id", "tenant_id", "aggregator", "aggregator_ref")[:200]
    reconciled = 0
    for payment in qs:
        try:
            cb_call(payment.aggregator, registry.get(payment.aggregator).query,
                    aggregator_ref=payment.aggregator_ref)
            reconciled += 1
        except Exception as exc:  # noqa: BLE001
            logger.warning("Reconcile failed for %s: %s", payment.aggregator_ref, exc)
    return reconciled
