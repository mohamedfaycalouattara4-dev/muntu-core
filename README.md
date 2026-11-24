# Muntu Core

Muntu Core est une plateforme backend multi-tenant orientée services financiers et opérations institutionnelles. Le projet met l’accent sur l’isolation des données, l’intégrité des opérations, l’idempotence et la sécurité d’exécution.

## Stack

- Python 3.12, Django 5, Django REST Framework.
- PostgreSQL 16 avec Row-Level Security.
- Redis 7 et Celery pour les tâches asynchrones.
- Django Channels pour les flux temps réel.
- React, TypeScript, Vite et PWA pour le client web.
- Docker Compose pour l’environnement reproductible.
- GitHub Actions, Ruff, Black, isort, mypy, Bandit, Gitleaks et detect-secrets.

## Fonctionnalités techniques

- Isolation multi-tenant au niveau application et base de données.
- Gestion des comptes, institutions, membres, épargne, crédit et caisse.
- Idempotence des opérations sensibles et protection contre les rejouements.
- Ledger append-only avec intégrité chaînée.
- Contrôles de concurrence et contraintes PostgreSQL.
- Healthchecks, migrations contrôlées et tâches Celery planifiées.
- Images Docker multi-stage exécutées en utilisateur non privilégié.
- Dépendances verrouillées avec hashes pour des builds reproductibles.
- Génération de schéma OpenAPI et contrôles de dérive des migrations.

## Architecture

```text
React/PWA
   │
   ▼
Django/DRF + Channels ── Redis ── Celery worker/beat
   │
   ▼
PostgreSQL + Row-Level Security
```

## Démarrage local

```bash
make secrets
make up
make smoke
```

Pour installer les outils de développement et exécuter les contrôles :

```bash
make install
make test
make lint
make typecheck
make security
make e2e
```

Les secrets de développement sont générés localement dans `.env` et ne doivent jamais être copiés dans GitHub.

## CI

Le workflow vérifie les dépendances, les migrations, le formatage, le lint, les tests PostgreSQL/Redis, la couverture, le schéma OpenAPI et les artefacts de livraison. Les images de production utilisent un build multi-stage, des versions épinglées et un utilisateur non-root.

## État du projet

Muntu Core est un projet avancé de portfolio et une base de préproduction. Les intégrations cloud réelles, les tests de charge, la restauration PostgreSQL, TLS, le monitoring opérationnel et un déploiement Kubernetes restent à réaliser avant une mise en production.

## Ce que le projet démontre

Ce projet met en évidence l’architecture backend Python, la conception multi-tenant, la sécurité PostgreSQL, les systèmes financiers, l’idempotence, la conteneurisation, la CI/CD et la préparation à l’exploitation.

## Sécurité

Aucun secret réel ne doit être ajouté au dépôt. Avant toute publication, exécuter Gitleaks et detect-secrets, vérifier les fichiers suivis et régénérer toute clé ayant pu être exposée.
