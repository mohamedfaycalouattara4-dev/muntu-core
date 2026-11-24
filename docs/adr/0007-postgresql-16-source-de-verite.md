# ADR-0007 — PostgreSQL 16 seule source de vérité, tests sur Postgres

* Statut : Accepté — 2026-08-02
* Jalon : J0

## Contexte

Les invariants financiers vivent dans la base : `CHECK
(quantity_reserved + quantity_sold <= quantity_total)`, règles append-only du
grand livre, politiques RLS, `select_for_update(skip_locked=True)`.

## Décision

PostgreSQL **16** en développement, en CI et en production. La suite de tests
s'exécute sur Postgres, jamais sur SQLite. Redis est un cache et un courtier,
**jamais** une source de vérité financière.

## Conséquences

* Les tests valident réellement les contraintes et la RLS (R5).
* Le poste de développement doit faire tourner Postgres : d'où Compose (ADR-0001).

## Alternatives écartées

* **SQLite pour les tests** : ne connaît ni RLS, ni règles, ni `skip_locked` —
  les contrôles de sécurité passeraient « verts » sans exister.
