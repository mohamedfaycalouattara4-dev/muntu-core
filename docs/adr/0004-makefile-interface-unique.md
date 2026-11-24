# ADR-0004 — Makefile comme interface unique

* Statut : Accepté — 2026-08-02
* Jalon : J0

## Contexte

Les commandes vivaient dans le README, dans la CI et dans les têtes. La CI
n'était pas reproductible localement : déboguer un échec de pipeline imposait
de repousser des commits pour observer.

## Décision

`make up | down | migrate | seed | test | lint | fmt | typecheck | security |
audit | e2e | secrets | smoke | ci` est l'unique interface. La CI appelle les
**mêmes cibles** ; chaque cible est documentée par `make help`.

## Conséquences

* `make ci` reproduit le pipeline en local.
* Toute nouvelle procédure doit devenir une cible, jamais une note de README.

## Alternatives écartées

* **Scripts shell dispersés** : découvrabilité nulle, duplication garantie.
* **Task/Just** : excellents mais imposent une installation supplémentaire ;
  `make` est présent partout, y compris sur les images CI.
