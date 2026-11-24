"""MUNTU CORE · Base settings — plateforme SFD/IMF."""
import os
from datetime import timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-only-do-not-use-in-prod")  # noqa: S105
DEBUG = os.getenv("DJANGO_DEBUG", "false").lower() == "true"
ALLOWED_HOSTS = os.getenv("DJANGO_ALLOWED_HOSTS", "*").split(",")

# ---------- Apps (Django 5 modular monolith) ----------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "drf_spectacular",
    "corsheaders",
    "channels",
    "apps.core",
    "apps.tenancy",
    "apps.accounts",
    "apps.members",
    "apps.savings",
    "apps.lending",
    "apps.teller",
    "apps.accounting",
    "apps.regulatory",
    "apps.payments",
    "apps.risk",
    "apps.compliance",
    "apps.audit",
    "apps.notifications",
    "apps.claims",
    "apps.documents",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.core.middleware.observability.CorrelationIdMiddleware",
    "apps.core.middleware.observability.MetricsMiddleware",
    "apps.core.middleware.idempotency.IdempotencyMiddleware",
    "apps.core.middleware.audit.AuditContextMiddleware",
    # Extraction et injection du tenant_id (Phase 00).
    "apps.core.middleware.tenant_middleware.TenantMiddleware",
    # Contexte PostgreSQL RLS (pose/reset par requête) — cf. P0-06.
    "apps.core.middleware.rls.RowLevelSecurityMiddleware",
]

AUTH_USER_MODEL = "accounts.User"

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [],
    "APP_DIRS": True,
    "OPTIONS": {
        "context_processors": [
            "django.template.context_processors.debug",
            "django.template.context_processors.request",
            "django.contrib.auth.context_processors.auth",
            "django.contrib.messages.context_processors.messages",
        ],
    },
}]

# ---------- PostgreSQL 16 (Postgres-first strategy) ----------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("DB_NAME", "kalyce"),
        "USER": os.getenv("DB_USER", "kalyce"),
        "PASSWORD": os.getenv("DB_PASSWORD", "kalyce"),
        "HOST": os.getenv("DB_HOST", "localhost"),
        "PORT": os.getenv("DB_PORT", "5432"),
        "ATOMIC_REQUESTS": False,
        "CONN_MAX_AGE": 60,
        "OPTIONS": {"application_name": "muntu-core-v1"},
    }
}

# ---------- Redis 7 (cache + Celery + Channels + JWT blacklist) ----------
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL,
        "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
    },
}
CHANNEL_LAYERS = {
    "default": {"BACKEND": "channels_redis.core.RedisChannelLayer", "CONFIG": {"hosts": [REDIS_URL]}},
}
SIMPLE_JWT = {
    "ALGORITHM": "RS256",
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

# ---------- DRF ----------
REST_FRAMEWORK = {
    # Authentification JWT qui installe le contexte RLS PostgreSQL (P0-06).
    "DEFAULT_AUTHENTICATION_CLASSES": ("apps.core.authentication.RLSJWTAuthentication",),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_THROTTLE_CLASSES": (
        "apps.core.throttling.OtpRequestThrottle",
        "apps.core.throttling.FinancialOperationThrottle",
        "apps.core.throttling.TellerOperationThrottle",
    ),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PARSER_CLASSES": ("rest_framework.parsers.JSONParser",),
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Muntu Core — Plateforme SFD/IMF",
    "VERSION": "1.0.0",
    "OAS_VERSION": "3.1.0",
    "DESCRIPTION": (
        "API de la plateforme bancaire **Muntu Core** pour les institutions "
        "financières (SFD/IMF) de la zone UEMOA.\n\n"
        "### Principes\n"
        "* **Grand livre immuable** : append-only, chaîné HMAC, double entrée.\n"
        "* **Multi-tenant** : isolation logique forte par institution (RLS PostgreSQL).\n"
        "* **Idempotence** : en-tête `Idempotency-Key` (verrou atomique).\n"
        "* **Observabilité** : `X-Request-ID` (ULID), logs JSON, métriques Prometheus.\n\n"
        "### Authentification\n"
        "JWT Bearer + en-tête `X-Tenant-ID` requis pour toute requête métier."
    ),
    "CONTACT": {"name": "Muntu Core Engineering", "email": "api@muntu.africa"},
    "LICENSE": {"name": "Propriétaire — usage sous contrat"},
    "SERVE_INCLUDE_SCHEMA": False,
    "SORT_OPERATIONS": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "ENUM_NAME_OVERRIDES": {
        "PaymentStateEnum": "apps.payments.models.PaymentState.choices",
        "LoanStatusEnum": "apps.lending.models.LoanStatus.choices",
    },
    "POSTPROCESSING_HOOKS": [
        "drf_spectacular.hooks.postprocess_schema_enums",
        "apps.core.openapi.postprocess_schema",
    ],
    "TAGS": [
        {"name": "Authentification", "description": "OTP et jetons JWT."},
        {"name": "Membres & KYC", "description": "Adhésion, identité, pièces justificatives."},
        {"name": "Épargne", "description": "Comptes, opérations, intérêts créditeurs."},
        {"name": "Crédit", "description": "Dossiers, comité, échéanciers, règlements."},
        {"name": "Caisse", "description": "Sessions de guichet, arrêts, transferts."},
        {"name": "Comptabilité", "description": "Plan comptable, écritures, balance."},
        {"name": "Réglementaire", "description": "États BCEAO, centrale des risques, AML."},
        {"name": "Webhooks & événements",
         "description": "Webhooks agrégateurs et événements sortants signés."},
        {"name": "Réclamations", "description": "Litiges membres, quorum d'arbitrage."},
        {"name": "Back-office", "description": "Opérations d'administration."},
        {"name": "Risque & conformité", "description": "Anti-blanchiment et seuils BCEAO."},
        {"name": "Audit", "description": "Journal d'audit inviolable."},
        {"name": "Documents", "description": "Contrats, reçus, relevés, attestations."},
        {"name": "Exploitation", "description": "Santé et métriques Prometheus."},
    ],
    "SWAGGER_UI_SETTINGS": {"deepLinking": True, "persistAuthorization": True,
                            "displayRequestDuration": True},
}

# ---------- Argon2 (sécurité back-office) ----------
PASSWORD_HASHERS = ["django.contrib.auth.hashers.Argon2PasswordHasher",
                    "django.contrib.auth.hashers.PBKDF2PasswordHasher"]
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
     "OPTIONS": {"min_length": 16}},  # back-office ≥16
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---------- Celery ----------
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_TASK_ROUTES = {
    "muntu.payments.*": {"queue": "critical"},
    "muntu.security.*": {"queue": "critical"},
    "muntu.savings.*": {"queue": "critical"},
    "muntu.lending.*": {"queue": "critical"},
    "muntu.teller.*": {"queue": "high"},
    "muntu.accounting.*": {"queue": "high"},
    "muntu.regulatory.*": {"queue": "normal"},
    "muntu.audit.*": {"queue": "normal"},
    "muntu.documents.*": {"queue": "normal"},
    "muntu.notifications.*": {"queue": "low"},
}

# ---------- Idempotency ----------
IDEMPOTENCY_TTL_SECONDS = int(os.getenv("IDEMPOTENCY_TTL", "86400"))
# Durée de vie du verrou posé AVANT traitement (anti race condition).
IDEMPOTENCY_LOCK_TTL_SECONDS = int(os.getenv("IDEMPOTENCY_LOCK_TTL", "60"))

# ---------- Domain secrets ----------
HSZ_SIGNING_KEY = os.getenv("HSZ_SIGNING_KEY", "a" * 64)  # 32 bytes hex
AUDIT_SIGNING_KEY = os.getenv("AUDIT_SIGNING_KEY", "b" * 64)
QUORUM_XOF_THRESHOLD = int(os.getenv("QUORUM_XOF_THRESHOLD", "500000"))
# Nombre d'approbateurs distincts (WebAuthn vérifié) au-delà du seuil (P0-02).
QUORUM_MIN_APPROVERS = int(os.getenv("QUORUM_MIN_APPROVERS", "2"))

# ---------- Environnement d'exécution ----------
# dev | test | staging | production — pilote les garde-fous « fail secure ».
ENVIRONMENT = os.getenv("KALYCE_ENVIRONMENT", "dev").lower()

# ---------- WebAuthn / FIDO2 (P0-03) ----------
WEBAUTHN_RP_ID = os.getenv("WEBAUTHN_RP_ID", "localhost")
WEBAUTHN_ALLOWED_ORIGINS = [
    o for o in os.getenv("WEBAUTHN_ALLOWED_ORIGINS", "http://localhost:5173").split(",") if o
]

# ---------- Adaptateurs de paiement (P0-07) ----------
# Les adaptateurs simulés ne déplacent aucun argent réel : ils sont interdits
# hors développement et ne peuvent jamais être activés en production.
PAYMENTS_ALLOW_SIMULATED_ADAPTERS = (
    ENVIRONMENT not in {"production", "prod", "staging"}
    and os.getenv("PAYMENTS_ALLOW_SIMULATED_ADAPTERS", "true").lower() == "true"
)

# ---------- Risque / AML (P0-04) ----------
# Nombre de comptes DISTINCTS en alerte HIGH avant escalade SOC (jamais de gel
# global automatique).
RISK_GLOBAL_ESCALATION_USERS = int(os.getenv("RISK_GLOBAL_ESCALATION_USERS", "25"))

USE_TZ = True
TIME_ZONE = "Africa/Ouagadougou"
LANGUAGE_CODE = "fr-fr"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
STATIC_URL = "static/"
LOGIN_URL = "/api/v1/auth/login/"

KEY_ROTATION_INTERVAL_DAYS = 90


# ---------- Observabilité : logs structurés JSON + Prometheus ----------
PROMETHEUS_METRICS_ENABLED = os.getenv("PROMETHEUS_METRICS_ENABLED", "true").lower() == "true"
METRICS_TOKEN = os.getenv("METRICS_TOKEN", "")  # si vide : accès réservé au staff
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "correlation": {"()": "apps.core.observability.LogContextFilter"},
    },
    "formatters": {
        "json": {"()": "apps.core.logging.JsonFormatter"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
            "filters": ["correlation"],
        },
        "soc": {
            "class": "apps.core.logging.SOCWebhookHandler",
            "level": "WARNING",
            "formatter": "json",
            "filters": ["correlation"],
        },
    },
    "root": {"handlers": ["console"], "level": LOG_LEVEL},
    "loggers": {
        "django.request": {"handlers": ["console"], "level": "ERROR", "propagate": False},
        "kalyce": {"handlers": ["console", "soc"], "level": LOG_LEVEL, "propagate": False},
    },
}


# ---------- Garde-fous « fail secure » au chargement (P0-05) ----------
# Exécutés ici, et non dans un check Django, afin qu'AUCUN processus (ASGI,
# worker Celery, commande de management) ne puisse démarrer avec un secret
# manquant, trop court, factice ou un rôle base de données contournant la RLS.
from .guards import enforce as _enforce_security_guards  # noqa: E402

_enforce_security_guards(ENVIRONMENT, database=DATABASES["default"], debug=DEBUG)
