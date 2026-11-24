# ADR-0008 — Gestion des secrets : génération locale, SOPS + age partagés

* Statut : Accepté — 2026-08-02
* Jalon : J0

## Contexte

R7 impose l'échec bruyant sur secret manquant ; il faut donc un moyen simple
d'obtenir des secrets **valides** en local, sans jamais versionner de valeur réelle.

## Décision

* `make secrets` génère localement (`openssl rand`) les valeurs de développement
  dans `.env`, gitignoré. Aucune valeur n'est écrasée si elle est déjà réelle.
* `.env.example` documente **chaque** variable et son caractère obligatoire en production.
* Environnements partagés (staging, production) : **SOPS + age**, fichiers
  chiffrés versionnés, clés détenues par l'équipe plateforme. HashiCorp Vault
  reste l'option si l'organisation l'exploite déjà.
* `gitleaks` scanne l'intégralité de l'historique en CI.

## Conséquences

* Zéro secret réel dans le dépôt, vérifiable automatiquement.
* Rotation d'un secret partagé = un commit chiffré, donc traçable et revu.

## Alternatives écartées

* **Secrets committés « juste pour le dev »** : la valeur finit invariablement
  copiée en production.
* **Vault dès J0** : opérationnellement lourd pour une équipe qui ne l'exploite pas encore.
