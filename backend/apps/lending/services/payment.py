"""Muntu Core — Règlement de prêt.

Imputation stricte : 1) frais de retard, 2) intérêt, 3) principal.
Aucun montant ne peut être affecté hors de cette priorité.
"""
from __future__ import annotations
from typing import Any


def process_payment(
    loan_id: str,
    installment_id: str | None,
    amount: int,
    payment_method: str,
    performed_by: str,
    late_fee_amount: int = 0,
    interest_amount: int = 0,
    principal_amount: int = 0,
) -> dict[str, Any]:
    """Traite un règlement de prêt avec imputation stricte.

    Ordre d'imputation :
    1. Frais de retard (late_fee)
    2. Intérêts courus (interest)
    3. Principal restant (principal)

    Args:
        loan_id: ULID du prêt.
        installment_id: ULID de l'échéance (optionnel).
        amount: Montant total reçu.
        payment_method: CASH, TRANSFER, MOBILE_MONEY, DEBIT.
        performed_by: ULID de l'agent.
        late_fee_amount: Frais de retard dus.
        interest_amount: Intérêts dus.
        principal_amount: Principal dû.

    Returns:
        Dictionnaire avec le détail de l'imputation.

    Raises:
        ValueError: Si amount <= 0 ou si les montants sont invalides.
    """
    if amount <= 0:
        raise ValueError(f"Montant invalide : {amount}")

    remaining = amount
    result: dict[str, Any] = {
        "loan_id": loan_id,
        "installment_id": installment_id,
        "amount_received": amount,
        "payment_method": payment_method,
        "performed_by": performed_by,
    }

    # 1. Imputation frais de retard
    late_fee_applied = min(remaining, late_fee_amount)
    remaining -= late_fee_applied
    result["late_fee_applied"] = late_fee_applied

    # 2. Imputation intérêts
    interest_applied = min(remaining, interest_amount)
    remaining -= interest_applied
    result["interest_applied"] = interest_applied

    # 3. Imputation principal
    principal_applied = min(remaining, principal_amount)
    remaining -= principal_applied
    result["principal_applied"] = principal_applied

    # Vérification : le montant non affecté
    result["unallocated"] = remaining
    result["total_allocated"] = amount - remaining

    # Statut
    if remaining == 0:
        result["status"] = "FULLY_ALLOCATED"
    elif late_fee_amount > 0 or interest_amount > 0:
        result["status"] = "PARTIALLY_ALLOCATED"
    else:
        result["status"] = "FULLY_ALLOCATED"

    return result


def compute_late_fee(
    amount_due: int,
    days_late: int,
    grace_period_days: int,
    late_fee_rate: float,
) -> int:
    """Calcule les frais de retard.

    Args:
        amount_due: Montant dû de l'échéance.
        days_late: Nombre de jours de retard.
        grace_period_days: Jours de tolérance.
        late_fee_rate: Taux de pénalité (ex: 0.01 = 1% par mois).
    """
    if days_late <= grace_period_days:
        return 0

    effective_days = days_late - grace_period_days
    months_late = effective_days / 30
    fee = int(amount_due * late_fee_rate * months_late)
    return fee


def compute_outstanding(
    original_principal: int,
    total_principal_repaid: int,
    original_interest: int,
    total_interest_repaid: int,
) -> dict[str, int]:
    """Calcule le capital et les intérêts restants dus."""
    return {
        "outstanding_principal": max(0, original_principal - total_principal_repaid),
        "outstanding_interest": max(0, original_interest - total_interest_repaid),
    }
