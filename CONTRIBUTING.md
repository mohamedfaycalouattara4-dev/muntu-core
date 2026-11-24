# Contribuer à Kalyce

Ce document est normatif. Une contribution qui ne le respecte pas est refusée
en revue, quelle que soit la qualité du code.

## 1. Prérequis

- Docker 24+ et Docker Compose v2
- Python 3.13, Node 20 (uniquement pour l'outillage local hors conteneur)
- `make` (interface unique du projet — ADR-0004)

```bash
git clone <url> && cd kalyce-monorepo-v2
make up          # secrets de dev + stack complète
make smoke       # /health doit répondre 200
```

Aucune commande `docker`, `pip` ou `npm` n'est à taper directement : si un
geste vous manque, ajoutez une cible `make` documentée plutôt qu'une
incantation locale.

## 2. Secrets

- `make secrets` génère des valeurs aléatoires locales dans `.env`.
- `.env` est ignoré par Git ; `.env.example` est la seule référence versionnée.
- Aucun secret réel ne doit apparaître dans un commit, un test, un fixture, un
  journal ou une capture d'écran. `detect-secrets` et `gitleaks` bloquent au
  commit ; un secret exposé impose une rotation immédiate, pas une réécriture
  d'historique discrète.

## 3. Branches et commits

Trunk-based (ADR-0005) : `main` est toujours déployable.

- Branches : `feat/<sujet>`, `fix/<sujet>`, `chore/<sujet>`, `docs/<sujet>`.
- Durée de vie visée : moins de 48 h. Au-delà, découpez.
- Commits au format **Conventional Commits**, vérifié par pre-commit :

```
feat(payments): idempotence des webhooks agrégateur
fix(checkout): rejette une transition FSM au mauvais acteur
docs(adr): ADR-0011 sur la rétention des journaux
```

Types admis : `feat`, `fix`, `perf`, `refactor`, `test`, `docs`, `build`,
`ci`, `chore`, `revert`.

## 4. Qualité avant push

```bash
make hooks       # une fois, installe pre-commit
make fmt         # formatage
make ci          # lint + tests backend + sécurité (identique à la CI)
```

Un push dont la CI échoue est traité comme un incident : on corrige ou on
revert, on n'accumule pas.

## 5. Revue — règle des quatre yeux

Toute pull request exige l'approbation d'un autre humain. Les zones
suivantes exigent en plus une revue d'un mainteneur du domaine :

| Zone                              | Raison                                 |
| --------------------------------- | -------------------------------------- |
| `apps/payments/`, `apps/ledger/`  | Argent : journal en partie double (R1)  |
| `apps/checkout/state_machine.py`  | Transitions signées, acteurs fermés     |
| `config/settings/`, `guards.py`   | Posture de sécurité et garde-fous R7    |
| Migrations SQL, politiques RLS    | Isolation multi-tenant                  |
| `docker-compose.yml`, Dockerfiles | Surface d'exécution                     |

## 6. Tests

- Tout correctif de bug commence par un test qui échoue.
- Tout événement financier est prouvé par un test d'équilibre du ledger.
- Les tests d'infrastructure (`backend/tests/infra/`) protègent le J0 :
  non-root, images épinglées, secrets obligatoires, ADR présentes.
- Pas de `sleep` arbitraire, pas d'assertion sur l'horloge murale : le temps
  se contrôle par injection ou par `freezegun`.

## 7. ADR

Une décision structurante (dépendance majeure, découpage, protocole,
stockage, modèle de sécurité) se documente dans `docs/adr/` avant fusion.
Copiez `docs/adr/README.md`, numérotez à la suite, remplissez les sections
**Contexte**, **Décision**, **Conséquences**, **Alternatives écartées**. Une
ADR n'est jamais éditée après fusion : elle est remplacée et marquée
`Superseded by ADR-XXXX`.

## 8. Definition of Done

Une contribution est terminée lorsque, et seulement lorsque :

1. `make ci` passe localement et en CI.
2. Les nouveaux comportements sont couverts par des tests, y compris les cas
   d'échec et de rejeu (idempotence).
3. Les erreurs sont explicites et bruyantes — aucun `except: pass`, aucun
   repli silencieux (R7).
4. Les mouvements d'argent sont journalisés et probants (R1, R8).
5. La documentation impactée est à jour (`README_V2.md`, `.env.example`, ADR).
6. Aucun secret n'a été ajouté au dépôt.
7. `git clone && make up` reste vert sur une machine vierge (R11).
