"""Garde-fous « fail secure » exécutés au chargement des réglages (P0-05).

Objectif : rendre *impossible* le démarrage d'un processus (API, worker Celery,
commande de management) avec un secret manquant, trop court ou issu du jeu de
valeurs de développement. Les contrôles Django (`apps/core/checks.py`) ne
suffisent pas : ils ne s'exécutent que sur `manage.py check`/`runserver`, pas
sur un worker ou un serveur ASGI.

Ce module ne dépend de rien d'autre que la stdlib et `django.core.exceptions`
afin d'être appelable très tôt, avant l'initialisation des applications.
"""
from __future__ import annotations

import os
import re

from django.core.exceptions import ImproperlyConfigured

#: Environnements où aucune facilité de développement n'est tolérée.
PROTECTED_ENVIRONMENTS = frozenset({"production", "prod", "staging", "preprod"})

#: Secret -> longueur minimale exigée (en caractères).
REQUIRED_SECRETS: dict[str, int] = {
    "DJANGO_SECRET_KEY": 50,
    "FIELD_ENCRYPTION_KEY": 32,
    "HSZ_SIGNING_KEY": 64,
    "AUDIT_SIGNING_KEY": 64,
}

#: Valeurs interdites : ce sont exactement les replis de développement du dépôt.
FORBIDDEN_VALUES = frozenset({
    "dev-only-do-not-use-in-prod",
    "test-secret",
    "changeme",
    "change-me",
    "secret",
    "kalyce-v2-dev-fernet-key",
    "a" * 64,
    "b" * 64,
})

#: Motifs révélateurs d'une valeur factice (« dev », « test », « example »…).
FORBIDDEN_PATTERNS = (
    re.compile(r"dev[-_]?only", re.I),
    re.compile(r"do[-_]?not[-_]?use", re.I),
    re.compile(r"^(test|demo|sample|example|placeholder|todo)", re.I),
    re.compile(r"^(.)\1{15,}$"),  # une même lettre répétée : « aaaa… »
)

INSECURE_FLAG = "KALYCE_ALLOW_INSECURE_DEV_KEYS"
TRUTHY = {"1", "true", "yes", "on"}


def is_protected(environment: str) -> bool:
    return str(environment or "").lower() in PROTECTED_ENVIRONMENTS


def _value_problems(name: str, value: str, min_length: int) -> list[str]:
    problems: list[str] = []
    if not value:
        return [f"{name} est absent."]
    if len(value) < min_length:
        problems.append(f"{name} fait {len(value)} caractères (minimum {min_length}).")
    if value in FORBIDDEN_VALUES:
        problems.append(f"{name} utilise une valeur de développement connue.")
    elif any(pattern.search(value) for pattern in FORBIDDEN_PATTERNS):
        problems.append(f"{name} ressemble à une valeur factice.")
    return problems


def collect_problems(environment: str, *, env: dict[str, str] | None = None,
                     database: dict | None = None, debug: bool = False) -> list[str]:
    """Retourne la liste des violations. Vide = configuration acceptable."""
    env = os.environ if env is None else env
    if not is_protected(environment):
        return []

    problems: list[str] = []
    for name, min_length in REQUIRED_SECRETS.items():
        problems.extend(_value_problems(name, str(env.get(name, "") or ""), min_length))

    if str(env.get(INSECURE_FLAG, "")).lower() in TRUTHY:
        problems.append(f"{INSECURE_FLAG} est activé : interdit hors développement.")
    if debug:
        problems.append("DEBUG=True est interdit hors développement.")
    if str(env.get("PAYMENTS_ALLOW_SIMULATED_ADAPTERS", "")).lower() in TRUTHY:
        problems.append("Les adaptateurs de paiement simulés sont interdits (P0-07).")

    db_user = str((database or {}).get("USER", "") or "")
    if db_user in {"postgres", "kalyce"}:
        problems.append(
            f"Le rôle base de données « {db_user} » est propriétaire des tables : "
            "la RLS serait contournée (P0-06). Utilisez DB_APP_USER (NOBYPASSRLS).")
    return problems


def enforce(environment: str, *, env: dict[str, str] | None = None,
            database: dict | None = None, debug: bool = False) -> None:
    """Lève `ImproperlyConfigured` au premier démarrage non conforme."""
    problems = collect_problems(environment, env=env, database=database, debug=debug)
    if problems:
        raise ImproperlyConfigured(
            "Démarrage refusé — configuration de sécurité non conforme "
            f"(environnement « {environment} ») :\n  - " + "\n  - ".join(problems))
