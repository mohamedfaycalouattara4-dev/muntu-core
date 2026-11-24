# ADR-0002 — Image Docker multi-étages, non-root, slim

* Statut : Accepté — 2026-08-02
* Jalon : J0

## Contexte

Un conteneur exécuté en `root` est un point d'escalade évident lors d'un
pentest et un constat systématique des auditeurs ISO 27001. Une image obèse
augmente la surface d'attaque et le temps de déploiement.

## Décision

* `backend/Dockerfile` en **deux étages** : compilation des roues
  (`build-essential`) puis runtime `python:3.12.7-slim-bookworm`.
* Exécution sous l'UID/GID **10001** non privilégié, shell `nologin`.
* `HEALTHCHECK` sur `/health`, `gunicorn` + worker `uvicorn` (ASGI requis par
  Channels, §9).
* `frontend/Dockerfile` : build Vite puis `nginx-unprivileged` (UID 101), avec
  compression, en-têtes de sécurité et cache immuable sur les actifs hachés.
* Le **code est copié** dans l'image : aucun montage de source en production.

## Conséquences

* Image runtime sans chaîne de compilation ; cible < 200 Mo.
* Immutabilité de l'artefact : prérequis de la traçabilité SLSA.
* Toute dépendance système nouvelle doit être ajoutée explicitement.

## Alternatives écartées

* **Image unique `python:3.12`** : ~1 Go, compilateurs présents en production.
* **Distroless** : envisagé, écarté pour J0 car il complique le `HEALTHCHECK`
  (pas de `curl`/shell) et le diagnostic sur incident ; à réévaluer en J-ultérieur.
