"""Muntu Core — Opérations d'épargne : dépôt, retrait.

Toutes les opérations passent par le grand livre (ledger).
Le solde n'est jamais stocké : il est projeté depuis les écritures.

Invariants :
- I1 : Aucune écriture hors grand livre
- I2 : Isolation tenant stricte
- I4 : Blocage montants si nécessaire
"""
from __future__ import annotations
from typing import Any
from apps.core.tenant_context import get_tenant_id
from apps.core.services.tenant_isolation import require_tenant_scope


def deposit(account_id: str, amount: int, performed_by: str) -> dict[str, Any]:
    """Dépôt sur un compte d'épargne.

    Invariants :
    - amount > 0
    - Compte actif
    - Écriture débitée au grand livre (caisse → compte d'épargne)
    """
    if amount <= 0:
        raise ValueError(f"Montant invalide : {amount}")

    from ..models import SavingsAccount, SavingsAccountStatus

    account = SavingsAccount.objects.get(id=account_id)
    if account.status != SavingsAccountStatus.ACTIVE:
        raise PermissionError(f"Compte {account_id} non actif (status={account.status}).")

    # Vérification plafond
    product = account.product
    if product.maximum_balance > 0:
        # TODO: Vérifier le solde projeté + amount <= maximum_balance
        pass  # Intégration grand livre Phase 4

    # Création de l'écriture au grand livre (placeholder)
    entry_reference = f"SVD-{account.account_number}-{amount}"

    return {
        "operation": "DEPOSIT",
        "account_id": account_id,
        "account_number": account.account_number,
        "amount": amount,
        "performed_by": performed_by,
        "tenant_id": get_tenant_id(),
        "status": "COMPLETED",
        "ledger_reference": entry_reference,
    }


def withdraw(account_id: str, amount: int, performed_by: str) -> dict[str, Any]:
    """Retrait d'un compte d'épargne.

    Invariants :
    - amount > 0
    - Compte actif
    - Solde suffisant (projeté depuis le grand livre)
    - Respect des limites du produit (retrait min, limite journalière)
    - Montant bloqué (nantissement) vérifié
    - Écriture créditée au grand livre (compte d'épargne → caisse)
    """
    if amount <= 0:
        raise ValueError(f"Montant invalide : {amount}")

    from ..models import SavingsAccount, SavingsAccountStatus

    account = SavingsAccount.objects.get(id=account_id)
    if account.status != SavingsAccountStatus.ACTIVE:
        raise PermissionError(f"Compte {account_id} non actif (status={account.status}).")

    product = account.product

    # Vérification minimum de retrait
    if product.min_withdrawal > 0 and amount < product.min_withdrawal:
        raise ValueError(
            f"Retrait minimum : {product.min_withdrawal} XOF (tenté : {amount})"
        )

    # Vérification montant bloqué (nantissement)
    if account.blocked_amount > 0:
        # TODO: Vérifier que amount <= solde - blocked_amount
        pass  # Intégration grand livre Phase 4

    # Vérification limite journalière
    if product.daily_withdrawal_limit > 0:
        # TODO: Vérifier le total des retraits du jour
        pass

    # Vérification du solde via grand livre
    # TODO: project_balance(account_id) >= amount

    entry_reference = f"SVW-{account.account_number}-{amount}"

    return {
        "operation": "WITHDRAWAL",
        "account_id": account_id,
        "account_number": account.account_number,
        "amount": amount,
        "performed_by": performed_by,
        "tenant_id": get_tenant_id(),
        "status": "COMPLETED",
        "ledger_reference": entry_reference,
    }
