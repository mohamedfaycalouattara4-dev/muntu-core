"""Durcissement du socle de données (Étape 2, travaux §1-§9).

Applique par migration — jamais par script manuel (R11) — :
  * les contraintes CHECK, unicités partielles, FK ON DELETE RESTRICT et index ;
  * le trigger append-only du grand livre et du journal d'audit (R1, R8) ;
  * les rôles PostgreSQL (propriétaire / applicatif) et leurs garde-fous ;
  * la RLS FORCE et les politiques par rôle, réappliquées après partitionnement.
"""
from __future__ import annotations

from pathlib import Path

from django.db import migrations

SQL_DIR = Path(__file__).resolve().parents[3] / "sql"
FILES = ("002_rls_policies.sql", "003_hardening.sql", "004_roles_and_timeouts.sql")

REVERSE_SQL = """
DROP TRIGGER IF EXISTS trg_ledger_append_only ON public.payments_ledgerentry;
DROP TRIGGER IF EXISTS deny_ledger_mutation ON public.payments_ledgerentry;
DROP TRIGGER IF EXISTS trg_audit_append_only ON public.audit_auditevent;
DROP FUNCTION IF EXISTS muntu_add_check(text, text, text);
"""


def apply_hardening(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":  # pragma: no cover
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("SELECT set_config('muntu.system', 'on', false)")
        for filename in FILES:
            cursor.execute((SQL_DIR / filename).read_text(encoding="utf-8"))


def revert_hardening(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":  # pragma: no cover
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(REVERSE_SQL)


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0004_monthly_partitioning"),
        ("tenancy", "0001_initial"),
        ("members", "0001_initial"),
        ("savings", "0001_initial"),
        ("lending", "0001_initial"),
        ("teller", "0001_initial"),
        ("accounting", "0001_initial"),
        ("regulatory", "0001_initial"),
        ("claims", "0001_initial"),
        ("documents", "0001_initial"),
        ("payments", "0001_initial"),
    ]

    operations = [migrations.RunPython(apply_hardening, revert_hardening)]
