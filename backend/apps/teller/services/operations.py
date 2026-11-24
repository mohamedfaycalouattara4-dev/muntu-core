"""Muntu Core — Opérations de caisse."""
from __future__ import annotations
from typing import Any
from apps.core.tenant_context import get_tenant_id
from ..models import TellerSession, TellerOperation, TellerOperationType, TellerSessionStatus


def process_teller_operation(
    session_id: str,
    operation_type: str,
    amount: int,
    counterparty_member_id: str,
    performed_by: str,
) -> dict[str, Any]:
    """Traite une opération de caisse.

    Invariants :
    - Session ouverte
    - amount > 0
    - Écriture au grand livre
    """
    if amount <= 0:
        raise ValueError(f"Montant invalide : {amount}")

    session = TellerSession.objects.get(id=session_id)
    if session.status != TellerSessionStatus.OPEN:
        raise PermissionError(f"Session {session_id} non ouverte (status={session.status}).")

    op = TellerOperation.objects.create(
        tenant_id=get_tenant_id(),
        session=session,
        operation_type=operation_type,
        amount=amount,
        counterparty_member_id=counterparty_member_id,
        performed_by=performed_by,
    )

    # Mise à jour des totaux de la session
    if operation_type == "DEPOSIT":
        session.total_deposits += amount
    elif operation_type == "WITHDRAWAL":
        session.total_withdrawals += amount
    elif operation_type == "TRANSFER_IN":
        session.total_transfers_in += amount
    elif operation_type == "TRANSFER_OUT":
        session.total_transfers_out += amount

    session.operation_count += 1
    session.save(update_fields=[
        "total_deposits", "total_withdrawals", "total_transfers_in",
        "total_transfers_out", "operation_count", "updated_at",
    ])

    return {
        "operation_id": op.id,
        "type": operation_type,
        "amount": amount,
        "current_balance": session.current_balance,
        "status": "COMPLETED",
    }
