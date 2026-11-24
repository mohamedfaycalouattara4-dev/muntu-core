"""Ledger append-only : rules PostgreSQL bloquant UPDATE/DELETE (V2 §8).

Les règles sont posées sur la table réelle du modèle `LedgerEntry`
(`payments_ledgerentry`). La migration est un no-op sur les backends
non-PostgreSQL afin de rester exécutable en local/CI dégradé.
"""
from django.db import migrations

FORWARD_SQL = """
CREATE OR REPLACE FUNCTION deny_ledger_mutation() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'payments_ledgerentry is append-only';
END;
$$ LANGUAGE plpgsql;

DROP RULE IF EXISTS no_update_ledger ON payments_ledgerentry;
DROP RULE IF EXISTS no_delete_ledger ON payments_ledgerentry;
CREATE RULE no_update_ledger AS ON UPDATE TO payments_ledgerentry DO INSTEAD NOTHING;
CREATE RULE no_delete_ledger AS ON DELETE TO payments_ledgerentry DO INSTEAD NOTHING;
"""

REVERSE_SQL = """
DROP RULE IF EXISTS no_update_ledger ON payments_ledgerentry;
DROP RULE IF EXISTS no_delete_ledger ON payments_ledgerentry;
DROP FUNCTION IF EXISTS deny_ledger_mutation();
"""


def apply_rules(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(FORWARD_SQL)


def drop_rules(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(REVERSE_SQL)


class Migration(migrations.Migration):
    dependencies = [("payments", "0001_initial")]

    operations = [migrations.RunPython(apply_rules, drop_rules)]
