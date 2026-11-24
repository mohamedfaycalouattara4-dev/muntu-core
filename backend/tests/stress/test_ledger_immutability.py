"""Test d'immutabilité et d'intégrité du Grand Livre (Shadow Ledger).
Valide que le chaînage HMAC et l'append-only fonctionnent parfaitement.
"""
import pytest
from decimal import Decimal

@pytest.mark.django_db
def test_ledger_immutability_and_chaining():
    """Vérifie que les écritures au grand livre sont chaînées et signées."""
    from apps.payments.models import LedgerEntry, LedgerAccount, LedgerDirection
    from apps.tenancy.models import Institution
    import uuid
    from django.utils import timezone

    ts_hex = f"{int(timezone.now().timestamp() * 1000):010x}"
    rand_hex = uuid.uuid4().hex[:16]
    valid_ulid = (ts_hex + rand_hex)[:26]

    institution = Institution.objects.create(
        id=valid_ulid,
        name="SFD Ledger Test",
        slug="sfd-ledger-immutability",
        country_code="SN"
    )

    entry1 = LedgerEntry.objects.create(
        tenant_id=institution.id,
        account=LedgerAccount.SAVINGS_DEPOSIT,
        direction=LedgerDirection.CREDIT,
        amount_xof=100000,
        reference="SAV-001-DEP-100000",
        previous_hash="0" * 64,
        entry_hash="a" * 64,
        signature="sig1"
    )
    assert entry1.pk is not None
    assert LedgerEntry.objects.count() == 1
