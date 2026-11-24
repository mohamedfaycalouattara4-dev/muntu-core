# ADR-0001 — Docker Compose en développement, Kubernetes en production

* Statut : Accepté — 2026-08-02
* Décideurs : Ingénierie plateforme KALYCE
* Jalon : J0

## Contexte

Le dépôt ne contenait aucun fichier d'infrastructure. La CI instanciait
PostgreSQL et Redis en services GitHub Actions, sans équivalent local : chaque
poste divergeait, le « ça marche chez moi » devenait la norme et le PRA exigé
au §17.4 était structurellement impossible.

## Décision

Le développement s'exécute avec **Docker Compose** (`docker-compose.yml` à la
racine) : `api`, `worker`, `beat`, `postgres:16.4`, `redis:7.4`, `minio`,
`mailhog`, `frontend`, réseau interne dédié, volumes **nommés**.
La production cible **Kubernetes**, avec les mêmes images construites par les
mêmes Dockerfile — seule l'orchestration diffère.

## Conséquences

* Parité de version stricte entre poste, CI et production.
* Un développeur obtient la plateforme complète avec `make up`.
* Les manifestes Kubernetes restent à écrire (hors périmètre J0) ; l'artefact
  conteneur, lui, est déjà celui de la production.

## Alternatives écartées

* **Environnements locaux natifs** (virtualenv + Postgres système) :
  reproduisent mal les versions, les contraintes réseau et les droits.
* **Kubernetes local (kind/minikube) pour tous** : coût cognitif et matériel
  disproportionné pour un travail quotidien de développement.
