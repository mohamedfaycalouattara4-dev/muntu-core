# syntax=docker/dockerfile:1.7
# =============================================================================
# KALYCE · Image backend — multi-étages, non-root, slim (< 200 Mo)
# ADR-0002 (image durcie) · ADR-0003 (verrouillage haché) · R11
# Les versions sont épinglées jusqu'au patch : jamais de tag « latest ».
# =============================================================================

########################  Étage 1 — construction des roues  ###################
FROM python:3.12.7-slim-bookworm AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1

# build-essential n'existe que dans cet étage : il ne suit pas dans le runtime.
RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential libpq-dev \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /wheels
COPY requirements/base.txt requirements/base.txt
COPY requirements/base.lock.txt requirements/base.lock.txt

# Le lock haché est la source de vérité ; base.txt ne sert qu'à la lisibilité.
RUN pip wheel --require-hashes --wheel-dir /wheels/dist -r requirements/base.lock.txt

##########################  Étage 2 — exécution  ##############################
FROM python:3.12.7-slim-bookworm AS runtime

# Parité stricte avec la production : UTC partout, C.UTF-8, pas de .pyc.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONHASHSEED=random \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    TZ=UTC \
    DJANGO_SETTINGS_MODULE=config.settings.prod \
    PATH="/home/kalyce/.local/bin:${PATH}"

RUN apt-get update \
 && apt-get install -y --no-install-recommends curl \
 && rm -rf /var/lib/apt/lists/* \
 && groupadd --gid 10001 kalyce \
 && useradd --uid 10001 --gid 10001 --create-home --shell /usr/sbin/nologin kalyce

WORKDIR /app

COPY --from=builder /wheels/dist /tmp/wheels
COPY requirements/base.lock.txt /tmp/base.lock.txt
RUN pip install --no-cache-dir --no-index --find-links=/tmp/wheels -r /tmp/base.lock.txt \
 && rm -rf /tmp/wheels /tmp/base.lock.txt

# Le code est COPIÉ dans l'artefact : jamais monté en volume en production
# (immutabilité de l'artefact — provenance SLSA, cf. ADR-0002).
COPY --chown=10001:10001 . /app

RUN chmod +x /app/docker/entrypoint.sh && mkdir -p /app/staticfiles && chown 10001:10001 /app/staticfiles

USER 10001:10001

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=5 \
  CMD curl -fsS http://127.0.0.1:8000/health || exit 1

ENTRYPOINT ["/app/docker/entrypoint.sh"]
# ASGI obligatoire : Channels/WebSockets (§9 du CDC).
CMD ["gunicorn", "config.asgi:application", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "3", \
     "--timeout", "60", \
     "--graceful-timeout", "30", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
