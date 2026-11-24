"""Génère `docs/schema.sql` — le diff de schéma lisible en revue de code.

Le fichier est versionné : toute migration doit être accompagnée de sa
régénération (`make schema`). Un test d'infrastructure vérifie sa présence.
"""
from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import connection

HEADER = """-- Généré automatiquement par `python manage.py dump_schema`.
-- Ne pas éditer à la main : régénérer après chaque migration.
"""

QUERY_TABLES = """
SELECT c.relname,
       CASE c.relkind WHEN 'p' THEN 'PARTITIONED' ELSE 'TABLE' END,
       c.relrowsecurity, c.relforcerowsecurity
FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p')
  AND c.relname NOT LIKE '%\\_p2%'
ORDER BY c.relname
"""

QUERY_COLUMNS = """
SELECT column_name, data_type, is_nullable, coalesce(column_default, '')
FROM information_schema.columns
WHERE table_schema = 'public' AND table_name = %s
ORDER BY ordinal_position
"""

QUERY_CONSTRAINTS = """
SELECT conname, pg_get_constraintdef(oid)
FROM pg_constraint
WHERE conrelid = ('public.' || %s)::regclass
ORDER BY conname
"""

QUERY_POLICIES = """
SELECT polname, pg_get_expr(polqual, polrelid), pg_get_expr(polwithcheck, polrelid)
FROM pg_policy WHERE polrelid = ('public.' || %s)::regclass ORDER BY polname
"""


class Command(BaseCommand):
    help = "Écrit docs/schema.sql (tables, contraintes, RLS, politiques)."

    def add_arguments(self, parser):
        parser.add_argument("--output", default=None)

    def handle(self, *args, **options):
        target = Path(options["output"] or
                      Path(__file__).resolve().parents[5] / "docs" / "schema.sql")
        target.parent.mkdir(parents=True, exist_ok=True)
        lines = [HEADER]
        with connection.cursor() as cur:
            cur.execute(QUERY_TABLES)
            tables = cur.fetchall()
            for name, kind, rls, force in tables:
                lines.append(f"\n-- {kind} public.{name} "
                             f"(RLS={'on' if rls else 'off'}, FORCE={'on' if force else 'off'})")
                cur.execute(QUERY_COLUMNS, [name])
                for col, dtype, nullable, default in cur.fetchall():
                    suffix = "" if nullable == "YES" else " NOT NULL"
                    default_txt = f" DEFAULT {default}" if default else ""
                    lines.append(f"--   {col} {dtype}{suffix}{default_txt}")
                cur.execute(QUERY_CONSTRAINTS, [name])
                for cname, cdef in cur.fetchall():
                    lines.append(f"--   CONSTRAINT {cname} {cdef}")
                cur.execute(QUERY_POLICIES, [name])
                for pname, using, check in cur.fetchall():
                    lines.append(f"--   POLICY {pname} USING ({using}) WITH CHECK ({check})")
        target.write_text("\n".join(lines) + "\n", encoding="utf-8")
        self.stdout.write(f"Schéma écrit dans {target}")
