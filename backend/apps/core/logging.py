"""Formatters JSON + handler SOC (webhook alerting)."""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone


_RESERVED = {
    "args", "asctime", "created", "exc_info", "exc_text", "filename", "funcName",
    "levelname", "levelno", "lineno", "module", "msecs", "message", "msg", "name",
    "pathname", "process", "processName", "relativeCreated", "stack_info",
    "thread", "threadName", "taskName",
}


class JsonFormatter(logging.Formatter):
    """Logs structurés JSON, corrélés par `request_id` / `reference` (ULID).

    Tout argument passé via `logger.info(..., extra={...})` est sérialisé au
    premier niveau du document, ce qui permet un filtrage direct côté
    agrégateur (Loki/ELK) : `reference="order:01H..."`.
    """

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": os.getenv("SERVICE_NAME", "kalyce-api"),
            "env": os.getenv("DJANGO_ENV", "dev"),
        }
        for key, value in record.__dict__.items():
            if key in _RESERVED or key.startswith("_"):
                continue
            if value in ("", None):
                continue
            try:
                json.dumps(value)
            except (TypeError, ValueError):
                value = repr(value)
            payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


class SOCWebhookHandler(logging.Handler):
    """Envoie les WARNING/CRITICAL vers le SOC webhook configuré."""

    def emit(self, record: logging.LogRecord) -> None:  # noqa: D401
        try:
            url = os.getenv("SOC_WEBHOOK_URL")
            if not url or record.levelno < logging.WARNING:
                return
            # On évite ici tout import réseau synchrone lourd ; un job Beat
            # lit la queue et dispatch en async.
            from ..tasks.security import enqueue_soc_event  # noqa: PLC0415
            enqueue_soc_event.delay(self.format(record))
        except Exception:  # pragma: no cover — handler best-effort
            self.handleError(record)
