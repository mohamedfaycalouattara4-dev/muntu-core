"""MUNTU CORE · Middleware d'extraction et d'injection du tenant_id (Phase 00).

Extrait le tenant_id de la requête HTTP (sous-domaine, en-tête, ou session)
et le définit dans le contexte global pour que toutes les couches de l'application
y aient accès.

Refus explicite si aucun tenant_id n'est fourni sur les routes protégées.

Stratégies d'extraction (par ordre de priorité) :
1. En-tête HTTP `X-Tenant-ID`
2. Sous-domaine (ex: "institution-123.muntu.local" → "institution-123")
3. Session utilisateur (si l'utilisateur est authentifié et associé à une institution)
"""
from __future__ import annotations

import logging
import re
from typing import Callable, Optional

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils.deprecation import MiddlewareMixin

from apps.core.tenant_context import clear_tenant_id, set_tenant_id, get_tenant_id

logger = logging.getLogger("muntu.tenant")


class TenantMiddleware(MiddlewareMixin):
    """Middleware pour l'extraction et l'injection du tenant_id.

    Ce middleware doit être placé **après** le middleware d'authentification Django
    pour avoir accès à request.user.

    I2 : Aucune donnée ne traverse les institutions.
    """

    SUBDOMAIN_PATTERN = re.compile(r"^([a-z0-9-]+)\.")

    EXEMPT_PATHS = {
        "/admin/",
        "/api/schema/",
        "/api/docs/",
        "/health/",
        "/api/v1/auth/login",
        "/api/v1/auth/register",
    }

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        # Nettoyer le contexte en début de requête
        clear_tenant_id()

        # Exemptions pour les routes publiques
        if any(request.path.startswith(p) for p in self.EXEMPT_PATHS):
            return self.get_response(request)

        try:
            tenant_id = self._extract_tenant_id(request)
            if not tenant_id:
                logger.warning("Requête sans tenant_id path=%s", request.path)
                return JsonResponse(
                    {"detail": "En-tête X-Tenant-ID requis.", "code": "tenant_required"},
                    status=400,
                )

            # Validation : le tenant doit exister et être actif
            try:
                from apps.tenancy.models import Institution
                inst = Institution.objects.get(id=tenant_id)
                if not inst.is_active():
                    logger.warning("Tenant inactif id=%s", tenant_id)
                    return JsonResponse(
                        {"detail": "Institution suspendue ou archivée.", "code": "tenant_inactive"},
                        status=403,
                    )
            except Exception as e:
                logger.warning("Tenant introuvable id=%s error=%s", tenant_id, e)
                return JsonResponse(
                    {"detail": "Institution introuvable.", "code": "tenant_not_found"},
                    status=404,
                )

            set_tenant_id(tenant_id)
            logger.debug(f"Tenant ID extracted: {tenant_id}")
        except Exception as e:
            logger.warning(f"Failed to process tenant context: {e}", exc_info=True)
            return JsonResponse(
                {"detail": "Erreur de contexte tenant.", "code": "tenant_error"},
                status=400,
            )

        try:
            response = self.get_response(request)
        finally:
            clear_tenant_id()

        return response

    def _extract_tenant_id(self, request: HttpRequest) -> Optional[str]:
        """Extrait le tenant_id de la requête selon les stratégies définies."""
        # Stratégie 1 : En-tête HTTP X-Tenant-ID
        tenant_id = request.META.get("HTTP_X_TENANT_ID")
        if tenant_id:
            return tenant_id

        # Stratégie 2 : Sous-domaine
        host = request.META.get("HTTP_HOST", "")
        if host:
            match = self.SUBDOMAIN_PATTERN.match(host)
            if match:
                return match.group(1)

        # Stratégie 3 : Session utilisateur (si authentifié)
        if hasattr(request, "user") and request.user.is_authenticated:
            try:
                from apps.core.tenant_models import InstitutionUser
                affiliation = InstitutionUser.objects.filter(
                    user_id=str(request.user.id)
                ).first()
                if affiliation:
                    return affiliation.institution_id
            except Exception:
                pass

        return None
