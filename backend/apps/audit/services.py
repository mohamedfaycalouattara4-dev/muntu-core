"""Audit · intégrité chaîne."""
from django.db import transaction
from .models import AuditEvent


def verify_chain() -> int:
    previous = "0" * 64
    broken = 0
    for entry in AuditEvent.objects.order_by("id"):
        if entry.previous_hash != previous:
            broken += 1
        previous = entry.current_hash
    return broken


@transaction.atomic
def append_event(*, entity_type: str, entity_id: str, action: str,
                  payload: dict, actor_id: str = "", actor_ip: str = "") -> str:
    from apps.core.services.audit import emit
    return emit(entity_type, entity_id, action, payload)
