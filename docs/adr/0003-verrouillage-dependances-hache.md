# ADR-0003 — Verrouillage des dépendances avec hachage

* Statut : Accepté — 2026-08-02
* Jalon : J0

## Contexte

Les `requirements/*.txt` étaient incomplets — `requirements.txt` ne contenait
qu'une seule ligne (`prometheus-client`) alors que l'application importe Django,
Channels, Celery, webauthn… Aucune empreinte : une substitution de paquet en
amont serait indétectable.

## Décision

* Fichiers **d'intention** lisibles : `requirements/{base,dev,test}.txt`,
  versions épinglées exactement.
* Fichiers **verrouillés** générés : `requirements/{base,dev,test}.lock.txt`
  avec `--generate-hashes` (via `uv pip compile`, compatible pip-tools).
* L'image de production installe **uniquement** le lock, avec
  `pip install --require-hashes` : toute altération d'archive fait échouer le build.

## Conséquences

* Reconstruction bit-à-bit identique ; prérequis NIST SSDF.
* Mettre à jour une dépendance impose de régénérer le lock (`make lock`),
  ce qui rend la modification visible en revue.

## Alternatives écartées

* **Poetry** : verrouillage correct mais impose son propre format et son
  résolveur au conteneur de production.
* **Versions flottantes (`>=`)** : reproductibilité nulle, écartée d'emblée.
