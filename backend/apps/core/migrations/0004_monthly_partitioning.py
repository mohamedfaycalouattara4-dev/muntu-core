"""Partitionnement déclaratif mensuel des tables à forte croissance (Étape 2 §7).

`payments_ledgerentry`, `audit_auditevent` et `notifications_notification` sont
converties en tables partitionnées par RANGE sur `created_at`. La conversion est
faite par renommage + copie : elle est atomique (DDL transactionnel PostgreSQL)
et réversible.

Conséquence assumée : la clé primaire et les contraintes d'unicité incluent la
clé de partition (contrainte PostgreSQL). L'unicité applicative reste garantie
par des identifiants ULID/BigInt et par la chaîne de hachage du grand livre.
"""
from __future__ import annotations

import datetime as dt

from django.db import migrations

from apps.core.partitioning import ensure_partitions

SPECS = {
    "payments_ledgerentry": {
        "pk": ("id", "created_at"),
        "identity": "id",
        "indexes": [
            ("payments_ledgerentry_entry_hash_uniq", "UNIQUE", "(entry_hash, created_at)"),
            ("payments_ledgerentry_account_idx", "", "(account, id)"),
            ("payments_ledgerentry_reference_idx", "", "(reference)"),
            ("payments_ledgerentry_created_at_idx", "", "(created_at)"),
        ],
    },
    "audit_auditevent": {
        "pk": ("id", "created_at"),
        "identity": "id",
        "indexes": [
            ("audit_auditevent_current_hash_uniq", "UNIQUE", "(current_hash, created_at)"),
            ("audit_auditevent_entity_idx", "", "(entity_type, entity_id)"),
            ("audit_auditevent_previous_hash_idx", "", "(previous_hash)"),
            ("audit_auditevent_created_at_idx", "", "(created_at)"),
        ],
    },
    "notifications_notification": {
        "pk": ("id", "created_at"),
        "identity": None,
        "indexes": [
            ("notifications_notification_recipient_idx", "", "(recipient_id)"),
            ("notifications_notification_state_idx", "", "(state, created_at)"),
        ],
    },
}


def _convert(cursor, table: str, spec: dict) -> None:
    cursor.execute(
        "SELECT relkind FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
        "WHERE n.nspname = 'public' AND c.relname = %s", [table])
    row = cursor.fetchone()
    if not row or row[0] == "p":  # table absente ou déjà partitionnée
        return

    legacy = f"{table}_legacy"
    cursor.execute(f'ALTER TABLE public."{table}" RENAME TO "{legacy}"')
    cursor.execute(
        f'CREATE TABLE public."{table}" (LIKE public."{legacy}" '
        "INCLUDING DEFAULTS INCLUDING IDENTITY INCLUDING GENERATED "
        "INCLUDING CONSTRAINTS INCLUDING STORAGE INCLUDING COMMENTS) "
        "PARTITION BY RANGE (created_at)")

    today = dt.date.today()
    # 24 mois de rétro-couverture pour absorber les données existantes.
    start = (today.replace(day=1) - dt.timedelta(days=760)).replace(day=1)
    reference = start
    while reference <= today.replace(day=1) + dt.timedelta(days=200):
        month_start = reference.replace(day=1)
        month_end = (month_start + dt.timedelta(days=32)).replace(day=1)
        cursor.execute(
            f'CREATE TABLE IF NOT EXISTS public."{table}_p{month_start:%Y%m}" '
            f'PARTITION OF public."{table}" '
            f"FOR VALUES FROM ('{month_start:%Y-%m-%d}') TO ('{month_end:%Y-%m-%d}')")
        reference = month_end

    cursor.execute(f'INSERT INTO public."{table}" SELECT * FROM public."{legacy}"')
    cursor.execute(f'DROP TABLE public."{legacy}" CASCADE')

    pk_cols = ", ".join(f'"{c}"' for c in spec["pk"])
    cursor.execute(
        f'ALTER TABLE public."{table}" ADD CONSTRAINT "{table}_pkey" PRIMARY KEY ({pk_cols})')
    for name, kind, cols in spec["indexes"]:
        cursor.execute(f'CREATE {kind} INDEX IF NOT EXISTS "{name}" ON public."{table}" {cols}')
    if spec["identity"]:
        cursor.execute(
            f"SELECT setval(pg_get_serial_sequence('public.\"{table}\"', "
            f"'{spec['identity']}'), GREATEST(COALESCE(MAX({spec['identity']}), 1), 1)) "
            f'FROM public."{table}"')


def apply_partitioning(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":  # pragma: no cover
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("SELECT set_config('kalyce.system', 'on', false)")
        for table, spec in SPECS.items():
            _convert(cursor, table, spec)
        ensure_partitions(cursor=cursor)


def revert_partitioning(apps, schema_editor):
    """Reconvertit en tables simples (les données sont conservées)."""
    if schema_editor.connection.vendor != "postgresql":  # pragma: no cover
        return
    with schema_editor.connection.cursor() as cursor:
        for table in SPECS:
            cursor.execute(
                "SELECT relkind FROM pg_class c JOIN pg_namespace n "
                "ON n.oid = c.relnamespace WHERE n.nspname='public' AND c.relname = %s",
                [table])
            row = cursor.fetchone()
            if not row or row[0] != "p":
                continue
            flat = f"{table}_flat"
            cursor.execute(
                f'CREATE TABLE public."{flat}" (LIKE public."{table}" '
                "INCLUDING DEFAULTS INCLUDING IDENTITY INCLUDING CONSTRAINTS)")
            cursor.execute(f'INSERT INTO public."{flat}" SELECT * FROM public."{table}"')
            cursor.execute(f'DROP TABLE public."{table}" CASCADE')
            cursor.execute(f'ALTER TABLE public."{flat}" RENAME TO "{table}"')


class Migration(migrations.Migration):
    atomic = True

    dependencies = [
        ("core", "0003_financialapproval"),
        ("payments", "0002_immutable_ledger"),
        ("audit", "0001_initial"),
        ("notifications", "0001_initial"),
    ]

    operations = [migrations.RunPython(apply_partitioning, revert_partitioning)]
