# Architecture Decision Records (ADR)

Une ADR par décision structurante. Numérotée, datée, **jamais modifiée** :
une décision qui évolue est *remplacée* par une nouvelle ADR qui la supersede.

Format : Contexte · Décision · Conséquences · Alternatives écartées · Statut.

| N°  | Titre | Statut |
|-----|-------|--------|
| [0001](0001-docker-compose-dev-kubernetes-prod.md) | Docker Compose en développement, Kubernetes en production | Accepté |
| [0002](0002-image-docker-multi-etages-non-root.md) | Image Docker multi-étages, non-root, slim | Accepté |
| [0003](0003-verrouillage-dependances-hache.md) | Verrouillage des dépendances avec hachage | Accepté |
| [0004](0004-makefile-interface-unique.md) | Makefile comme interface unique | Accepté |
| [0005](0005-trunk-based-conventional-commits.md) | Trunk-based, Conventional Commits, revue à quatre yeux | Accepté |
| [0006](0006-pre-commit-qualite-securite.md) | Pre-commit : ruff, mypy, bandit, detect-secrets | Accepté |
| [0007](0007-postgresql-16-source-de-verite.md) | PostgreSQL 16 seule source de vérité, tests sur Postgres | Accepté |
| [0008](0008-gestion-des-secrets-dev-et-partages.md) | Gestion des secrets : génération locale, SOPS + age partagés | Accepté |
| [0009](0009-utc-partout-parite-runtime.md) | UTC partout et parité stricte du runtime | Accepté |
| [0010](0010-psycopg3-remplace-psycopg2.md) | psycopg 3 remplace psycopg2-binary | Accepté |
