"""Muntu Core — Calcul des intérêts créditeurs (fonction pure).

Chaque accrual est une projection rejouable :
même date + même solde = même résultat.
"""
from __future__ import annotations
from decimal import Decimal, ROUND_DOWN


def compute_daily_interest(
    balance: int,
    annual_rate: Decimal,
    day_count_convention: int = 360,
) -> dict[str, int]:
    """Calcule l'intérêt créditeur d'une journée.

    Formulaire : balance × (annual_rate / day_count_convention)
    Tronqué à l'entier (pas d'arrondi).

    Args:
        balance: Solde en XOF.
        annual_rate: Taux annuel en décimal (ex: Decimal("0.035") = 3.5%).
        day_count_convention: 360 ou 365.

    Returns:
        Dictionnaire avec daily_rate et interest_amount.
    """
    if balance <= 0:
        return {"daily_rate": Decimal("0"), "interest_amount": 0}

    daily_rate = annual_rate / Decimal(day_count_convention)
    interest = (balance * daily_rate).quantize(Decimal("1"), rounding=ROUND_DOWN)

    return {
        "daily_rate": daily_rate,
        "interest_amount": int(interest),
    }


def compute_interest_for_period(
    balance: int,
    annual_rate: Decimal,
    days: int,
    day_count_convention: int = 360,
    compound: bool = False,
) -> dict[str, int]:
    """Calcule les intérêts sur une période de plusieurs jours.

    Args:
        balance: Solde initial.
        annual_rate: Taux annuel.
        days: Nombre de jours.
        day_count_convention: 360 ou 365.
        compound: Vrai si intérêts composés.

    Returns:
        Dictionnaire avec total_interest.
    """
    daily_rate = annual_rate / Decimal(day_count_convention)
    total_interest = 0

    if compound:
        current_balance = balance
        for _ in range(days):
            daily = (current_balance * daily_rate).quantize(Decimal("1"), rounding=ROUND_DOWN)
            total_interest += int(daily)
            current_balance += int(daily)
    else:
        daily = (balance * daily_rate).quantize(Decimal("1"), rounding=ROUND_DOWN)
        total_interest = int(daily) * days

    return {"total_interest": total_interest}


def compute_maturity_interest(
    principal: int,
    annual_rate: Decimal,
    term_days: int,
    day_count_convention: int = 360,
) -> int:
    """Calcule les intérêts à l'échéance d'un terme.

    Simple interest : principal × annual_rate × term_days / day_count_convention.
    """
    interest = (Decimal(principal) * annual_rate * Decimal(term_days) / Decimal(day_count_convention))
    return int(interest.quantize(Decimal("1"), rounding=ROUND_DOWN))


def compute_penalty(
    principal: int,
    penalty_rate: Decimal,
    days_early: int,
) -> int:
    """Calcule la pénalité de rupture anticipée.

    Args:
        principal: Montant du dépôt.
        penalty_rate: Taux de pénalité (ex: Decimal("0.01") = 1%).
        days_early: Nombre de jours de rupture anticipée.
    """
    penalty = (Decimal(principal) * penalty_rate * Decimal(days_early) / Decimal(30))
    return int(penalty.quantize(Decimal("1"), rounding=ROUND_DOWN))


def compute_daily_withdrawal_remaining(
    daily_limit: int,
    withdrawals_today: list[int],
) -> int:
    """Calcule le solde restant de la limite journalière de retrait.

    Args:
        daily_limit: Limite maximale (0 = illimité).
        withdrawals_today: Liste des montants déjà retirés aujourd'hui.
    """
    if daily_limit <= 0:
        return 0  # Pas de limite
    total_withdrawn = sum(withdrawals_today)
    remaining = daily_limit - total_withdrawn
    return max(0, remaining)
