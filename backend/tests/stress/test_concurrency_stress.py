"""Banc d'essai de concurrence (Stress-Test) pour Muntu-Core.
Simule des transactions simultanées (multi-guichets) sur un même compte pour valider
l'efficacité de select_for_update et des contraintes d'intégrité en base.
"""
import concurrent.futures
import pytest
from django.db import transaction

@pytest.mark.django_db(transaction=True)
def test_concurrent_savings_withdrawal_stress():
    """Simule 20 retraits simultanés de 10 000 XOF sur un compte ayant 50 000 XOF.
    Le solde est stocké en unités mineures (entiers).
    Seuls 5 retraits doivent réussir, les 15 autres doivent échouer.
    Aucun solde ne doit devenir négatif.
    """
    from apps.savings.models import SavingsAccount, SavingsProduct, SavingsProductType
    from apps.tenancy.models import Institution

    institution = Institution.objects.create(name="SFD Pilote UEMOA", slug="sfd-stress-test")
    product = SavingsProduct.objects.create(
        tenant_id=institution.id,
        name="Dépôt à vue Standard",
        product_type=SavingsProductType.CURRENT,
        minimum_balance=0
    )

    # Solde initial : 50 000 XOF stocké en entiers
    account = SavingsAccount.objects.create(
        tenant_id=institution.id,
        member_id="member-001-ulid",
        product=product,
        account_number="SAV-STRESS-001",
        status="ACTIVE"
    )

    # On simule un solde initial via une écriture directe ou en créant un champ balance temporaire pour le test si nécessaire,
    # ou en vérifiant comment les services modifient le solde. Comme SavingsAccount n'a pas de champ balance direct dans models.py
    # mais que le plan de test l'utilise, ajoutons dynamiquement un solde ou testons via SavingsProduct/Account.
    # Attends, regardons SavingsAccount dans models.py : il n'a pas de champ balance ! Le solde est calculé ou géré par le Ledger.
    # Testons donc directement la table des transactions ou ajoutons balance si besoin, ou inspectons apps/savings/services/operations.py
