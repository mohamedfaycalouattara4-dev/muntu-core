# ADR-0009 — UTC partout et parité stricte du runtime

* Statut : Accepté — 2026-08-02
* Jalon : J0

## Contexte

Un litige d'escrow se tranche sur des horodatages. Une ambiguïté de fuseau
(Ouagadougou = UTC+0 sans heure d'été, mais serveurs et clients varient) rend
la chaîne d'audit contestable.

## Décision

`TZ=UTC` dans toutes les images et tous les services Compose, `USE_TZ=True`
côté Django, stockage exclusivement en UTC, conversion **à l'affichage
seulement**. Même version de Python (3.12.7), même utilisateur, mêmes réglages
de locale (`C.UTF-8`) en développement et en production.

## Conséquences

* Les chaînes de hachage d'audit sont comparables entre environnements.
* Le frontend porte la responsabilité de l'affichage local.

## Alternatives écartées

* **Heure locale africaine côté serveur** : ingérable dès qu'un agrégateur ou
  un prestataire étranger entre dans la boucle.
