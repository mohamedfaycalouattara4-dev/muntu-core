"""Authentification JWT qui installe le contexte RLS (P0-06).

DRF authentifie *dans la vue*, après l'exécution des middlewares : poser le
contexte PostgreSQL uniquement dans un middleware laisserait toutes les requêtes
API en contexte anonyme. Cette classe pose le contexte dès que l'identité est
établie ; `RowLevelSecurityMiddleware` garantit la remise à zéro en fin de
requête.
"""
from __future__ import annotations

from rest_framework_simplejwt.authentication import JWTAuthentication

from apps.core.middleware.rls import set_rls_context


class RLSJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        result = super().authenticate(request)
        if result is not None:
            user, _token = result
            set_rls_context(user_id=str(user.id), roles=tuple(user.roles or ()))
        return result
