# ADR-0010 — psycopg 3 remplace psycopg2-binary

* Statut : Accepté — 2026-08-02
* Jalon : J0

## Contexte

`psycopg2-binary==2.9.9` ne publie pas de roue pour les interpréteurs récents :
l'installation retombe sur une compilation source qui échoue sans `libpq-dev`.
Un développeur sur un interpréteur neuf ne pouvait pas installer le projet —
contradiction directe avec l'objectif de J0.

## Décision

Adopter `psycopg[binary]==3.2.3`, pilote officiellement supporté par Django 5.0.
Aucun changement de code : `django.db.backends.postgresql` sélectionne psycopg 3
automatiquement lorsqu'il est présent.

## Conséquences

* Installation sans chaîne de compilation sur toutes les plateformes cibles.
* Accès ultérieur aux curseurs côté serveur et au pipeline mode.
* La suite de tests complète a été rejouée sur psycopg 3 : aucune régression.

## Alternatives écartées

* **Rester sur psycopg2 en figeant Python 3.12** : repousse le problème et
  interdit toute mise à niveau d'interpréteur.
