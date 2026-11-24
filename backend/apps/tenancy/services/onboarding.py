"""Muntu Core — Service d'onboarding d'institution (P0-00).

Création complète d'une institution avec :
1. Institution (tenant racine)
2. Agence principale (HQ)
3. Plan comptable SFD initial
4. Modules activés par défaut
5. Compte admin root
"""
from __future__ import annotations
from typing import Any
from django.utils import timezone
from django.db import transaction
from ..models import (
    Institution, InstitutionStatus, CurrencyCode,
    Branch, ModuleToggle,
)


DEFAULT_MODULES = [
    "savings", "lending", "teller", "accounting",
    "regulatory", "claims", "documents", "risk",
    "compliance", "audit", "notifications",
]

DEFAULT_ACCOUNTS = [
    # Classe 1 — Capitaux propres
    ("101000", "Capital", "EQUITY"),
    ("108000", "Compte de l'exploitant", "EQUITY"),
    ("109000", "Capital social", "EQUITY"),
    # Classe 2 — Immobilisations
    ("201000", "Frais d'établissement", "ASSET"),
    ("211000", "Immobilisations incorporelles", "ASSET"),
    ("212000", "Immobilisations corporelles", "ASSET"),
    # Classe 3 — Stocks
    ("301000", "Billets et monnaie", "ASSET"),
    ("311000", "Titres de placement", "ASSET"),
    # Classe 4 — Comptes de tiers
    ("401000", "Comptes de dépôts à vue", "LIABILITY"),
    ("402000", "Comptes d'épargne à terme", "LIABILITY"),
    ("411000", "Prêts à la clientèle", "ASSET"),
    ("421000", "Prêts en souffrance", "ASSET"),
    ("431000", "Intérêts courus à recevoir", "ASSET"),
    ("432000", "Intérêts courus à payer", "LIABILITY"),
    # Classe 5 — Trésorerie
    ("501000", "Caisse principale", "ASSET"),
    ("502000", "Caisse auxiliaire", "ASSET"),
    ("511000", "Banque centrale", "ASSET"),
    # Classe 6 — Charges
    ("601000", "Intérêts versés aux déposants", "EXPENSE"),
    ("602000", "Charges de personnel", "EXPENSE"),
    ("603000", "Charges générales d'exploitation", "EXPENSE"),
    ("604000", "Dotations aux amortissements", "EXPENSE"),
    ("605000", "Dotations aux provisions", "EXPENSE"),
    # Classe 7 — Produits
    ("701000", "Intérêts perçus sur prêts", "REVENUE"),
    ("702000", "Commissions et frais de dossier", "REVENUE"),
    ("703000", "Produits des titres", "REVENUE"),
    ("704000", "Produits divers d'exploitation", "REVENUE"),
]


@transaction.atomic
def onboard_institution(
    name: str,
    slug: str,
    country_code: str = "BF",
    currency: str = CurrencyCode.XOF,
    registration_number: str = "",
    timezone_str: str = "Africa/Ouagadougou",
    config: dict | None = None,
) -> dict[str, Any]:
    """Création complète d'une institution financière.

    Returns:
        Dictionnaire avec l'ID de l'institution, l'agence HQ et le nombre de modules.
    """
    if not name or not slug:
        raise ValueError("name et slug sont requis.")

    # 1. Créer l'institution
    inst = Institution.objects.create(
        name=name,
        slug=slug,
        country_code=country_code,
        currency=currency,
        registration_number=registration_number,
        timezone=timezone_str,
        config=config or {},
        status=InstitutionStatus.PENDING,
    )

    # 2. Créer l'agence principale (HQ)
    hq = Branch.objects.create(
        institution=inst,
        name=f"Siège — {name}",
        code="HQ",
        is_hq=True,
    )

    # 3. Créer le plan comptable SFD initial
    from apps.accounting.models import ChartAccount
    for code, name, category in DEFAULT_ACCOUNTS:
        ChartAccount.objects.create(
            tenant_id=inst.id,
            code=code,
            name=name,
            category=category,
            parent_code=code[:2] + "0000" if len(code) > 2 else None,
        )

    # 4. Activer les modules par défaut
    from django.utils import timezone as tz
    for module in DEFAULT_MODULES:
        toggle = ModuleToggle.objects.create(
            institution=inst,
            module_name=module,
            is_enabled=False,
        )
        # Activer savings, teller, accounting par défaut
        if module in ("savings", "teller", "accounting"):
            toggle.enable()

    # 5. Activer l'institution
    inst.activate()

    return {
        "institution_id": inst.id,
        "institution_name": inst.name,
        "slug": inst.slug,
        "currency": inst.currency,
        "hq_branch_id": hq.id,
        "hq_branch_code": hq.code,
        "modules_enabled": sum(1 for m in ModuleToggle.objects.filter(institution=inst, is_enabled=True)),
        "chart_accounts": len(DEFAULT_ACCOUNTS),
        "status": inst.status,
    }
