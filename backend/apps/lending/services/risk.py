"""Muntu Core — Scoring de risque crédit (fonction pure).

Classification A-E (BCEAO) basée sur :
- Ancienneté client
- Historique de remboursement
- Montant du prêt vs revenus
- Existence de garanties
"""
from __future__ import annotations
from decimal import Decimal
from typing import Any


def compute_risk_score(
    member_age_months: int,
    previous_loans: int,
    previous_defaults: int,
    loan_amount: int,
    estimated_monthly_income: int,
    has_guarantor: bool,
    has_collateral: bool,
    collateral_value: int,
) -> dict[str, Any]:
    """Calcule le score de risque d'un dossier de crédit.

    Returns:
        Dictionnaire avec risk_class (A-E), score (0-100), rationale.
    """
    score = 100

    # Ancienneté client
    if member_age_months < 3:
        score -= 25
    elif member_age_months < 6:
        score -= 15
    elif member_age_months < 12:
        score -= 5

    # Historique de remboursement
    if previous_loans > 0:
        default_rate = previous_defaults / previous_loans
        if default_rate > 0.5:
            score -= 40
        elif default_rate > 0.2:
            score -= 20
        elif default_rate > 0:
            score -= 5
        else:
            score += 10  # Bon payeur
    else:
        score -= 5  # Premier prêt

    # Ratio endettement (prêt / revenus mensuels)
    if estimated_monthly_income > 0:
        ratio = loan_amount / estimated_monthly_income
        if ratio > 12:
            score -= 30
        elif ratio > 6:
            score -= 15
        elif ratio > 3:
            score -= 5

    # Garanties
    if has_guarantor:
        score += 5
    if has_collateral and collateral_value > 0:
        coverage = collateral_value / loan_amount if loan_amount > 0 else 0
        if coverage >= 1.5:
            score += 15
        elif coverage >= 1.0:
            score += 10
        elif coverage > 0:
            score += 5

    score = max(0, min(100, score))

    # Classification BCEAO
    if score >= 80:
        risk_class = "A"
        label = "Excellent"
    elif score >= 65:
        risk_class = "B"
        label = "Bon"
    elif score >= 50:
        risk_class = "C"
        label = "Acceptable"
    elif score >= 35:
        risk_class = "D"
        label = "Risque élevé"
    else:
        risk_class = "E"
        label = "Très haut risque"

    return {
        "risk_class": risk_class,
        "risk_label": label,
        "score": score,
        "rationale": {
            "member_age_months": member_age_months,
            "previous_loans": previous_loans,
            "previous_defaults": previous_defaults,
            "debt_income_ratio": round(loan_amount / estimated_monthly_income, 2) if estimated_monthly_income > 0 else 0,
            "has_guarantor": has_guarantor,
            "collateral_coverage": round(collateral_value / loan_amount, 2) if loan_amount > 0 else 0,
        },
    }


def compute_impairment_provision(
    outstanding_principal: int,
    days_overdue: int,
    risk_class: str,
) -> int:
    """Calcule la provision pour dépréciation (normes BCEAO).

    Provisions :
    - A (sain) : 0%
    - B (sous surveillance) : 0%
    - C (défaut 1-30 jours) : 20%
    - D (douteux 31-90 jours) : 50%
    - E (perte 90+ jours) : 100%
    """
    provision_rates = {"A": 0, "B": 0, "C": 20, "D": 50, "E": 100}
    rate = provision_rates.get(risk_class, 0)

    # Si jours de retard dépasse le seuil de la classe, monter
    if days_overdue > 90 and risk_class != "E":
        rate = 100
    elif days_overdue > 30 and risk_class not in ("D", "E"):
        rate = max(rate, 50)
    elif days_overdue > 1 and risk_class not in ("C", "D", "E"):
        rate = max(rate, 20)

    return (outstanding_principal * rate) // 100
