"""Middlewares d'observabilité : corrélation de requête + métriques HTTP."""
from __future__ import annotations

import logging
import time
from typing import Callable

from django.conf import settings

from ..metrics import HTTP_LATENCY, HTTP_REQUESTS
from ..observability import CORRELATION_HEADER, bind_context, new_correlation_id

logger = logging.getLogger("muntu.core.http")


def _route_of(request) -> str:
    """Route templatisée (`/api/v1/orders/<pk>/`) — évite l'explosion de labels."""
    match = getattr(request, "resolver_match", None)
    if match is not None and match.route:
        return f"/{match.route.lstrip('/')}"
    return "unmatched"


class CorrelationIdMiddleware:
    """Attache un ULID de corrélation à chaque requête (entrant ou généré)."""

    def __init__(self, get_response: Callable):
        self.get_response = get_response

    def __call__(self, request):
        incoming = (request.headers.get(CORRELATION_HEADER) or "").strip()
        request_id = incoming[:64] or new_correlation_id()
        request.request_id = request_id
        actor_id = ""
        with bind_context(request_id=request_id, actor_id=actor_id):
            response = self.get_response(request)
        response[CORRELATION_HEADER] = request_id
        return response


class MetricsMiddleware:
    """Compteur + histogramme de latence par route et statut."""

    def __init__(self, get_response: Callable):
        self.get_response = get_response
        self.enabled = getattr(settings, "PROMETHEUS_METRICS_ENABLED", True)

    def __call__(self, request):
        if not self.enabled:
            return self.get_response(request)
        started = time.perf_counter()
        response = self.get_response(request)
        elapsed = time.perf_counter() - started
        route = _route_of(request)
        try:
            HTTP_REQUESTS.labels(method=request.method, route=route,
                                 status=str(response.status_code)).inc()
            HTTP_LATENCY.labels(method=request.method, route=route).observe(elapsed)
        except Exception:  # pragma: no cover
            logger.debug("métriques HTTP non enregistrées", exc_info=True)
        logger.info("http_request", extra={
            "http_method": request.method,
            "http_route": route,
            "http_status": response.status_code,
            "duration_ms": round(elapsed * 1000, 2),
        })
        return response
