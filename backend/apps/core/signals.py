"""Signaux Django — capture mutations critiques vers le journal d'audit."""
from __future__ import annotations

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.payments.models import Payment


# Suppression du signal Order (Phase 01 - Purge Commerce)


@receiver(post_save, sender=Payment)
def audit_payment_post_save(sender, instance, created, **kwargs):  # noqa: D401
    from apps.core.services.audit import emit
    emit("payment", str(instance.id), "created" if created else "updated",
         {"state": instance.state, "amount_xof": instance.amount_xof})
