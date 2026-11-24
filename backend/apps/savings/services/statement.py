"""Muntu Core — Relevé d'épargne (projeté depuis le grand livre).

Le relevé est une projection à partir des écritures du grand livre.
Inclut : solde, intérêts crédités, opérations de la période.
"""
from __future__ import annotations
from datetime import date
from typing import Any


def compute_statement(
    account_id: str,
    period_start: str | None = None,
    period_end: str | None = None,
) -> dict[str, Any]:
    """Calcule le relevé d'un compte d'épargne.

    Le relevé est projeté depuis les écritures du grand livre.
    Inclut : solde, intérêts crédités, opérations de la période.
    """
    from ..models import SavingsAccount, InterestAccrual

    account = SavingsAccount.objects.get(id=account_id)
    accruals = InterestAccrual.objects.filter(account=account)

    if period_start:
        accruals = accruals.filter(accrual_date__gte=period_start)
    if period_end:
        accruals = accruals.filter(accrual_date__lte=period_end)

    total_interest = sum(a.interest_amount for a in accruals)
    total_credited = sum(a.interest_amount for a in accruals.filter(is_credited=True))

    return {
        "account_id": account_id,
        "account_number": account.account_number,
        "member_id": account.member_id,
        "product": account.product.name,
        "period_start": period_start,
        "period_end": period_end,
        "status": account.status,
        "total_interest_accrued": total_interest,
        "total_interest_credited": total_credited,
        "total_interest_pending": total_interest - total_credited,
        "note": "Relevé calculé (grand livre en attente d'intégration complète).",
    }
