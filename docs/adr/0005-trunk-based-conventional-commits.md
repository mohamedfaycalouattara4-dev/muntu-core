# ADR-0005 — Trunk-based, Conventional Commits, revue à quatre yeux

* Statut : Accepté — 2026-08-02
* Jalon : J0

## Contexte

Le domaine est financier : paiement, FSM de commande, grand livre, sécurité.
Une modification non revue sur ces zones peut coûter des fonds réels et
l'agrément BCEAO.

## Décision

* **Trunk-based** : branches courtes (< 2 jours) issues de `main`.
* **Conventional Commits** obligatoires, vérifiés par hook `commit-msg`.
* Revue **à deux yeux** par défaut ; **à quatre yeux** obligatoire dès qu'un
  diff touche `apps/payments`, `apps/checkout` (FSM), `apps/core/security*`,
  `apps/audit`, les migrations ou l'infrastructure (CODEOWNERS).
* `main` protégé : CI verte obligatoire, pas de push direct.

## Conséquences

* Historique exploitable pour le changelog et l'audit réglementaire.
* Léger surcoût de délai sur les zones sensibles — assumé.

## Alternatives écartées

* **Git flow** : branches longues, divergences et conflits de migrations.
* **Revue facultative** : incompatible avec un système de paiement.
