"""Applique réellement les politiques RLS (P0-06).

Le fichier `sql/002_rls_policies.sql` est exécuté de façon idempotente.
Tables Muntu Core : tenancy, members, savings, lending, teller, accounting,
payments, regulatory, claims, documents, accounts.
"""
from __future__ import annotations

from pathlib import Path

from django.db import migrations

SQL_DIR = Path(__file__).resolve().parents[3] / "sql"

TABLES = [
    # Tenancy
    "tenancy_institution",
    "tenancy_branch",
    "tenancy_moduletoggle",
    # Members
    "members_member",
    "members_memberdocument",
    "members_solidaritygroup",
    "members_solidaritygroupmember",
    # Savings
    "savings_savingsproduct",
    "savings_savingsaccount",
    "savings_interestaccrual",
    # Lending
    "lending_loanproduct",
    "lending_loan",
    "lending_loaninstallment",
    "lending_loanpayment",
    "lending_guarantee",
    # Teller
    "teller_tellersession",
    "teller_telleroperation",
    "teller_tellertransfer",
    # Accounting
    "accounting_chartaccount",
    "accounting_journalentry",
    "accounting_accountingday",
    # Payments & Ledger
    "payments_payment",
    "payments_ledgerentry",
    # Regulatory
    "regulatory_regulatoryreport",
    "regulatory_riskcenterentry",
    "regulatory_amlalert",
    # Claims
    "claims_claim",
    "claims_claimresolution",
    # Documents
    "documents_document",
    "documents_documenttemplate",
    # Accounts
    "accounts_user",
    # Audit
    "audit_auditevent",
]

REVERSE_SQL = "\n".join(
    f"ALTER TABLE IF EXISTS public.{t} NO FORCE ROW LEVEL SECURITY;\n"
    f"ALTER TABLE IF EXISTS public.{t} DISABLE ROW LEVEL SECURITY;"
    for t in TABLES
)


def apply_rls(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":  # pragma: no cover
        return
    sql = (SQL_DIR / "002_rls_policies.sql").read_text(encoding="utf-8")
    with schema_editor.connection.cursor() as cursor:
        # Les migrations s'exécutent en contexte système explicite.
        cursor.execute("SELECT set_config('muntu.system', 'on', false)")
        cursor.execute(sql)


def revert_rls(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":  # pragma: no cover
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(REVERSE_SQL)


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0001_initial"),
        ("tenancy", "0001_initial"),
        ("payments", "0002_immutable_ledger"),
        ("members", "0001_initial"),
        ("savings", "0001_initial"),
        ("lending", "0001_initial"),
        ("teller", "0001_initial"),
        ("accounting", "0001_initial"),
        ("regulatory", "0001_initial"),
        ("claims", "0001_initial"),
        ("documents", "0001_initial"),
        ("accounts", "0001_initial"),
        ("audit", "0001_initial"),
    ]

    operations = [migrations.RunPython(apply_rls, revert_rls)]
