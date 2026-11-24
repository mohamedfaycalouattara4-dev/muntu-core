# ADR-0006 — Pre-commit : ruff, mypy, bandit, detect-secrets

* Statut : Accepté — 2026-08-02
* Jalon : J0

## Contexte

Un secret poussé sur une branche est compromis définitivement, même supprimé
ensuite : l'historique Git et les caches des forges le conservent. Le contrôle
doit intervenir **avant** le commit.

## Décision

`.pre-commit-config.yaml` exécute : `ruff` (lint + format), `mypy` en mode
**strict progressif** (noyau `core`/`checkout`/`payments` d'abord), `bandit`,
`detect-secrets` avec baseline, `gitleaks`, `check-merge-conflict`,
`end-of-file-fixer`, `detect-private-key`, `eslint` + `prettier` côté frontend,
et `conventional-pre-commit` sur le message.

## Conséquences

* Un commit contenant un secret factice est effectivement bloqué (critère de DoD).
* La CI rejoue les mêmes hooks : impossible de contourner par `--no-verify`.

## Alternatives écartées

* **Contrôles uniquement en CI** : le secret est déjà publié quand l'alerte tombe.
* **mypy strict immédiat sur tout le dépôt** : des milliers d'erreurs, donc
  désactivation en une semaine. Le strict progressif est la seule voie tenable.
