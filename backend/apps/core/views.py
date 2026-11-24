"""Endpoints opérationnels : health check et exposition Prometheus."""
from __future__ import annotations

import hmac

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET

from .metrics import CONTENT_TYPE_LATEST, render_latest
from .observability import get_request_id


@require_GET
def health(request):
    return JsonResponse({"status": "ok", "request_id": get_request_id()})


def _metrics_authorized(request) -> bool:
    token = getattr(settings, "METRICS_TOKEN", "")
    if token:
        header = request.headers.get("Authorization", "")
        presented = header[7:] if header.startswith("Bearer ") else ""
        return hmac.compare_digest(presented, token)
    user = getattr(request, "user", None)
    return bool(user and user.is_authenticated and user.is_staff)


@csrf_exempt
@require_GET
def metrics(request):
    """`GET /api/v1/metrics` — format texte Prometheus.

    Protection : `METRICS_TOKEN` (Bearer) si configuré, sinon staff Django.
    """
    if not getattr(settings, "PROMETHEUS_METRICS_ENABLED", True):
        return JsonResponse({"detail": "metrics disabled"}, status=404)
    if not _metrics_authorized(request):
        return JsonResponse({"detail": "Non autorisé."}, status=401)
    return HttpResponse(render_latest(), content_type=CONTENT_TYPE_LATEST)
