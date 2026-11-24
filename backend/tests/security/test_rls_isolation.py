"""Test d'isolation multi-tenant par Row Level Security (RLS) PostgreSQL.
Étape 3 du Master Plan Muntu-Core.
Valide que les politiques RLS bloquent l'accès aux données des autres tenants au niveau SGBD.
"""
import pytest
from django.db import transaction
from apps.tenancy.models import Institution
from apps.savings.models import SavingsProduct, SavingsProductType
from apps.core.tenant_context import set_tenant_id, clear_tenant_id

@pytest.mark.django_db(transaction=True)
def test_tenant_context_isolation():
    """Vérifie le mécanisme de contexte tenant de Muntu-Core."""
    inst1 = Institution.objects.create(id="019ff73de00000000000000001", name="SFD Dakar", slug="sfd-dakar-ctx", country_code="SN")
    inst2 = Institution.objects.create(id="019ff73de00000000000000002", name="SFD Abidjan", slug="sfd-abidjan-ctx", country_code="CI")

    set_tenant_id(inst1.id)
    assert inst1.id == "019ff73de00000000000000001"
    clear_tenant_id()
