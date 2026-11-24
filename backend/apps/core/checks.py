"""Contrôles de démarrage « fail secure » (P0-05 / P0-07).

Django refuse de démarrer si une configuration rend un contrôle de sécurité
décoratif : clé de chiffrement absente, adaptateurs simulés en production, RLS
exécutée avec un rôle propriétaire de base.
"""
from __future__ import annotations

import os

from django.conf import settings
from django.core.checks import Error, Warning, register

SECURITY_TAG = "muntu.security"


@register(SECURITY_TAG)
def check_secrets(app_configs, **kwargs):
    errors = []
    env = str(getattr(settings, "ENVIRONMENT", "dev")).lower()
    if env in {"production", "prod", "staging"}:
        for name in ("FIELD_ENCRYPTION_KEY", "HSZ_SIGNING_KEY", "AUDIT_SIGNING_KEY"):
            if not os.getenv(name):
                errors.append(Error(
                    f"{name} absente en environnement « {env} ».",
                    hint="Aucune clé de repli n'est dérivée : configurez le secret.",
                    id="muntu.E001"))
        if os.getenv("KALYCE_ALLOW_INSECURE_DEV_KEYS", "").lower() in {"1", "true", "yes"}:
            errors.append(Error(
                "KALYCE_ALLOW_INSECURE_DEV_KEYS activé hors développement.",
                id="muntu.E002"))
    return errors


@register(SECURITY_TAG)
def check_payment_adapters(app_configs, **kwargs):
    from apps.payments.services.adapters import environment, simulated_adapters_allowed

    if environment() in {"production", "prod", "staging"} and simulated_adapters_allowed():
        return [Error(
            "Adaptateurs de paiement simulés autorisés en environnement non-dev.",
            hint="PAYMENTS_ALLOW_SIMULATED_ADAPTERS doit rester False.",
            id="muntu.E003")]
    return []


@register(SECURITY_TAG)
def check_rls_role(app_configs, **kwargs):
    env = str(getattr(settings, "ENVIRONMENT", "dev")).lower()
    if env not in {"production", "prod", "staging"}:
        return []
    db_user = settings.DATABASES["default"].get("USER", "")
    if db_user in {"postgres", "kalyce"}:
        return [Warning(
            f"La connexion applicative utilise le rôle « {db_user} », "
            "probablement propriétaire des tables.",
            hint="Utilisez un rôle dédié NOBYPASSRLS (DB_APP_USER).",
            id="muntu.W001")]
    return []
