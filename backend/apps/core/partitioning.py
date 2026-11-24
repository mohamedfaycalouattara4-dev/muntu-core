"""Partitionnement déclaratif mensuel (Étape 2, travaux §7).

`ledger_entries`, `audit_events` et `notifications` croissent linéairement avec
le volume de transactions. À 50 000 commandes/mois, l'index devient le facteur
limitant et l'archivage décennal (§15) impose de détacher plutôt que supprimer.

Une partition manquante = arrêt immédiat des écritures. La tâche Celery
`muntu.core.ensure_partitions` crée donc systématiquement trois mois d'avance.
"""
from __future__ import annotations

import datetime as dt
import logging
import re

from django.db import connection

logger = logging.getLogger("muntu.partitioning")

#: Tables partitionnées par mois sur `created_at`.
PARTITIONED_TABLES: tuple[str, ...] = (
    "payments_ledgerentry",
    "audit_auditevent",
    "notifications_notification",
)

MONTHS_AHEAD = 3
_IDENT = re.compile(r"^[a-z_][a-z0-9_]*$")


def _check_identifier(name: str) -> str:
    if not _IDENT.match(name):
        raise ValueError(f"Identifiant SQL invalide : {name!r}")
    return name


def month_bounds(day: dt.date) -> tuple[dt.date, dt.date]:
    start = day.replace(day=1)
    end = (start + dt.timedelta(days=32)).replace(day=1)
    return start, end


def partition_name(table: str, day: dt.date) -> str:
    start, _ = month_bounds(day)
    return f"{table}_p{start:%Y%m}"


def is_partitioned(table: str, *, cursor=None) -> bool:
    sql = ("SELECT relkind = 'p' FROM pg_class c JOIN pg_namespace n "
           "ON n.oid = c.relnamespace WHERE n.nspname = 'public' AND c.relname = %s")
    if cursor is not None:
        cursor.execute(sql, [table])
        row = cursor.fetchone()
        return bool(row and row[0])
    with connection.cursor() as cur:
        cur.execute(sql, [table])
        row = cur.fetchone()
    return bool(row and row[0])


def create_partition(table: str, day: dt.date, *, cursor=None) -> str | None:
    """Crée (si absente) la partition mensuelle contenant `day`."""
    _check_identifier(table)
    name = partition_name(table, day)
    start, end = month_bounds(day)
    statement = (
        f'CREATE TABLE IF NOT EXISTS public."{name}" PARTITION OF public."{table}" '
        f"FOR VALUES FROM ('{start:%Y-%m-%d}') TO ('{end:%Y-%m-%d}')"
    )

    def _run(cur):
        if not is_partitioned(table, cursor=cur):
            return None
        cur.execute(statement)
        return name

    if cursor is not None:
        return _run(cursor)
    with connection.cursor() as cur:
        return _run(cur)


def ensure_partitions(*, months_ahead: int = MONTHS_AHEAD,
                      today: dt.date | None = None,
                      tables: tuple[str, ...] = PARTITIONED_TABLES,
                      cursor=None) -> list[str]:
    """Garantit la partition du mois courant et des `months_ahead` suivants."""
    today = today or dt.date.today()
    created: list[str] = []

    def _run(cur):
        cursor_created = []
        for table in tables:
            reference = today
            for _ in range(months_ahead + 1):
                name = create_partition(table, reference, cursor=cur)
                if name:
                    cursor_created.append(name)
                start, end = month_bounds(reference)
                reference = end
        return cursor_created

    if cursor is not None:
        created = _run(cursor)
    else:
        with connection.cursor() as cur:
            created = _run(cur)
    logger.info("Partitions garanties", extra={"partitions": created})
    return created


def existing_partitions(table: str) -> list[str]:
    with connection.cursor() as cur:
        cur.execute(
            "SELECT c.relname FROM pg_inherits i "
            "JOIN pg_class c ON c.oid = i.inhrelid "
            "JOIN pg_class p ON p.oid = i.inhparent "
            "WHERE p.relname = %s ORDER BY c.relname", [table])
        return [row[0] for row in cur.fetchall()]


def detach_partition(table: str, day: dt.date) -> str:
    """Détache une partition (archivage §15 : on détache, on ne supprime pas)."""
    _check_identifier(table)
    name = partition_name(table, day)
    with connection.cursor() as cur:
        cur.execute(f'ALTER TABLE public."{table}" DETACH PARTITION public."{name}"')
    return name
