"""Capture de l'identité de l'auditeur (IP, user) pour les services d'audit."""
from __future__ import annotations

from typing import Callable


class AuditContextMiddleware:
    def __init__(self, get_response: Callable):
        self.get_response = get_response

    def __call__(self, request):
        from ..services.audit import audit_context  # lazy
        with audit_context(user=getattr(request, "user", None),
                           ip=request.META.get("REMOTE_ADDR")):
            return self.get_response(request)
