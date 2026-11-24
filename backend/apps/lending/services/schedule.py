"""Muntu Core — Calcul d'échéancier de prêt (fonction pure, déterministe).

Toute modification de ce module doit être couverte par des jeux de tests
dont les valeurs attendues ont été validées à la main.

Trois méthodes d'amortissement supportées :
- FLAT : intérêt constant chaque période (flat rate)
- DECLINING : intérêt sur solde restant (declining balance)
- FRENCH : annuité constante (méthode française)

Tous les montants sont en unités mineures (XOF, 64 bits).
Les taux sont exprimés en décimal (ex: 0.15 = 15%).
"""
from __future__ import annotations
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, getcontext

getcontext().prec = 50


@dataclass(frozen=True)
class InstallmentLine:
    """Ligne d'échéancier calculée."""
    number: int
    due_date: int  # nombre de jours depuis l'origine
    principal: int
    interest: int
    total: int

    @property
    def as_tuple(self) -> tuple[int, int, int, int]:
        return (self.number, self.due_date, self.principal, self.interest, self.total)


def _trunc(amount: Decimal) -> int:
    """Troncature vers zéro en entier (XOF)."""
    return int(amount.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def compute_flat_schedule(
    principal: int,
    annual_rate: Decimal,
    term_months: int,
    frequency_months: int,
    start_date_days: int = 0,
) -> list[InstallmentLine]:
    """Échéancier linéaire (flat rate).

    Intérêt total = principal × taux_annuel × (terme / 12)
    Chaque échéance : principal/periods + intérêt/periods
    """
    if principal <= 0 or term_months <= 0:
        raise ValueError(f"Paramètres invalides : principal={principal}, term={term_months}")

    periods = term_months // frequency_months
    if periods <= 0:
        periods = 1

    total_interest = _trunc(Decimal(principal) * annual_rate * Decimal(term_months) / Decimal(12))
    principal_per_period = _trunc(Decimal(principal) / Decimal(periods))
    interest_per_period = _trunc(Decimal(total_interest) / Decimal(periods))

    schedule: list[InstallmentLine] = []
    remaining_principal = principal

    for i in range(1, periods + 1):
        p = principal_per_period if i < periods else remaining_principal
        remaining_principal -= p
        if remaining_principal < 0:
            p += remaining_principal
            remaining_principal = 0
        schedule.append(InstallmentLine(
            number=i,
            due_date=start_date_days + i * frequency_months * 30,
            principal=p,
            interest=interest_per_period if i < periods else total_interest - interest_per_period * (periods - 1),
            total=p + (interest_per_period if i < periods else total_interest - interest_per_period * (periods - 1)),
        ))

    # Ajustement pour que la somme = principal + total_interest exactement
    total_paid_principal = sum(s.principal for s in schedule)
    total_paid_interest = sum(s.interest for s in schedule)
    diff_p = principal - total_paid_principal
    diff_i = total_interest - total_paid_interest
    if diff_p != 0 and schedule:
        schedule[-1] = schedule[-1]
        schedule[-1] = InstallmentLine(
            number=schedule[-1].number,
            due_date=schedule[-1].due_date,
            principal=schedule[-1].principal + diff_p,
            interest=schedule[-1].interest + diff_i,
            total=schedule[-1].total + diff_p + diff_i,
        )

    return schedule


def compute_declining_schedule(
    principal: int,
    annual_rate: Decimal,
    term_months: int,
    frequency_months: int,
    start_date_days: int = 0,
) -> list[InstallmentLine]:
    """Échéancier dégressif (declining balance).

    Intérêt = solde_restant × taux_périodique
    Principal constant = principal / periods
    """
    if principal <= 0 or term_months <= 0:
        raise ValueError(f"Paramètres invalides : principal={principal}, term={term_months}")

    periods = term_months // frequency_months
    if periods <= 0:
        periods = 1

    periodic_rate = annual_rate * Decimal(frequency_months) / Decimal(12)
    principal_per_period = _trunc(Decimal(principal) / Decimal(periods))

    schedule: list[InstallmentLine] = []
    remaining = principal
    total_interest = 0

    for i in range(1, periods + 1):
        interest = _trunc(Decimal(remaining) * periodic_rate)
        p = principal_per_period if i < periods else remaining
        remaining -= p
        total_interest += interest
        schedule.append(InstallmentLine(
            number=i,
            due_date=start_date_days + i * frequency_months * 30,
            principal=p,
            interest=interest,
            total=p + interest,
        ))

    # Ajustement
    total_paid = sum(s.principal for s in schedule)
    diff = principal - total_paid
    if diff != 0 and schedule:
        schedule[-1] = InstallmentLine(
            number=schedule[-1].number,
            due_date=schedule[-1].due_date,
            principal=schedule[-1].principal + diff,
            interest=schedule[-1].interest,
            total=schedule[-1].total + diff,
        )

    return schedule


def compute_french_schedule(
    principal: int,
    annual_rate: Decimal,
    term_months: int,
    frequency_months: int,
    start_date_days: int = 0,
) -> list[InstallmentLine]:
    """Échéancier à annuité constante (méthode française).

    A = P × r / (1 - (1+r)^-n)
    où r = taux périodique, n = nombre de périodes
    """
    if principal <= 0 or term_months <= 0:
        raise ValueError(f"Paramètres invalides : principal={principal}, term={term_months}")

    periods = term_months // frequency_months
    if periods <= 0:
        periods = 1

    periodic_rate = annual_rate * Decimal(frequency_months) / Decimal(12)

    if periodic_rate == 0:
        # Cas dégénéré : taux nul → simple division
        p_per = _trunc(Decimal(principal) / Decimal(periods))
        schedule = [InstallmentLine(
            number=i, due_date=start_date_days + i * frequency_months * 30,
            principal=p_per, interest=0, total=p_per,
        ) for i in range(1, periods + 1)]
        return schedule

    # Annuité constante
    r = periodic_rate
    n = Decimal(periods)
    annuity = Decimal(principal) * r / (Decimal(1) - (Decimal(1) + r) ** (-n))
    annuity_int = _trunc(annuity)

    schedule: list[InstallmentLine] = []
    remaining = Decimal(principal)

    for i in range(1, periods + 1):
        interest = _trunc(remaining * r)
        if i < periods:
            principal_part = annuity_int - interest
        else:
            principal_part = _trunc(remaining)
        remaining -= principal_part
        schedule.append(InstallmentLine(
            number=i,
            due_date=start_date_days + i * frequency_months * 30,
            principal=principal_part,
            interest=interest,
            total=annuity_int if i < periods else principal_part + interest,
        ))

    # Ajustement final
    total_principal = sum(s.principal for s in schedule)
    diff = principal - total_principal
    if diff != 0 and schedule:
        schedule[-1] = InstallmentLine(
            number=schedule[-1].number,
            due_date=schedule[-1].due_date,
            principal=schedule[-1].principal + diff,
            interest=schedule[-1].interest,
            total=schedule[-1].total + diff,
        )

    return schedule


def compute_schedule(
    principal: int,
    annual_rate: Decimal,
    term_months: int,
    frequency_months: int = 1,
    method: str = "FLAT",
    start_date_days: int = 0,
) -> list[InstallmentLine]:
    """Fonction d'entrée unique pour le calcul d'échéancier.

    Args:
        principal: Montant du prêt en unités mineures.
        annual_rate: Taux annuel en décimal (ex: 0.15 pour 15%).
        term_months: Durée totale en mois.
        frequency_months: Fréquence de remboursement en mois (1=mensuel).
        method: 'FLAT', 'DECLINING' ou 'FRENCH'.
        start_date_days: Décalage en jours depuis la date de référence.
    """
    methods = {
        "FLAT": compute_flat_schedule,
        "DECLINING": compute_declining_schedule,
        "FRENCH": compute_french_schedule,
    }
    fn = methods.get(method.upper())
    if fn is None:
        raise ValueError(f"Méthode inconnue : {method}. Choisir parmi FLAT, DECLINING, FRENCH.")

    schedule = fn(
        principal=principal,
        annual_rate=annual_rate,
        term_months=term_months,
        frequency_months=frequency_months,
        start_date_days=start_date_days,
    )

    # Vérification invariante : somme des principaux = principal
    total_principal = sum(s.principal for s in schedule)
    if total_principal != principal:
        raise RuntimeError(
            f"Invariant violé : somme des principaux ({total_principal}) != principal ({principal})"
        )

    return schedule
