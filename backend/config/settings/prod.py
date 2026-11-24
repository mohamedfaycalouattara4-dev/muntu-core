from .base import *  # noqa: F401,F403

ENVIRONMENT = "production"
DEBUG = False

# Aucun adaptateur simulé ne peut déplacer de faux argent en production (P0-07).
PAYMENTS_ALLOW_SIMULATED_ADAPTERS = False

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY")  # noqa: F405
HSZ_SIGNING_KEY = os.getenv("HSZ_SIGNING_KEY")  # noqa: F405
AUDIT_SIGNING_KEY = os.getenv("AUDIT_SIGNING_KEY")  # noqa: F405

WEBAUTHN_RP_ID = os.getenv("WEBAUTHN_RP_ID", "muntu.bf")  # noqa: F405
WEBAUTHN_ALLOWED_ORIGINS = [  # noqa: F405
    o for o in os.getenv("WEBAUTHN_ALLOWED_ORIGINS", "https://app.muntu.bf").split(",") if o
]

# Rôle applicatif NON propriétaire : indispensable pour que la RLS s'applique
# (le propriétaire des tables contourne les politiques sans FORCE RLS).
DATABASES["default"]["USER"] = os.getenv("DB_APP_USER", "kalyce_app_login")  # noqa: F405
DATABASES["default"]["PASSWORD"] = os.getenv("DB_APP_PASSWORD", "")  # noqa: F405
ALLOWED_HOSTS = os.getenv("DJANGO_ALLOWED_HOSTS", "api.muntu.bf").split(",")  # noqa: F405

# Sécurité durcie — prod uniforme, "Fail Secure".
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31_536_000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Strict"
CSRF_COOKIE_SECURE = True
X_FRAME_OPTIONS = "DENY"
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = os.getenv("CORS_ALLOWED_ORIGINS", "https://app.muntu.bf").split(",")

# mTLS requis en zone ZHS (cold world).
ZONE_HAUTE_SECURITE_MTLS = True
ZHS_PUBLIC_HTTP_ALLOWED = False

# Content-Security-Policy strict.
SECURE_CSP = {
    "default-src": ["'self'"],
    "script-src": ["'self'"],
    "style-src": ["'self'"],
    "connect-src": ["'self'", "https://api.muntu.bf", "wss://api.muntu.bf"],
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"json": {"()": "apps.core.logging.JsonFormatter"}},
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "json"},
        "security_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": "/var/log/kalyce/security.log",
            "maxBytes": 10 * 1024 * 1024,
            "backupCount": 20,
            "formatter": "json",
        },
        "soc_webhook": {"class": "apps.core.logging.SOCWebhookHandler"},
    },
    "loggers": {
        "muntu.security": {"handlers": ["security_file", "soc_webhook"], "level": "INFO", "propagate": False},
        "django.security": {"handlers": ["security_file"], "level": "DEBUG", "propagate": False},
    },
}


# ---------- Garde-fous « fail secure » (P0-05) ----------
# Placés en fin de fichier : la configuration production est alors complète
# (rôle base de données applicatif inclus), et le processus refuse de démarrer
# si un seul contrôle échoue.
from .guards import enforce as _enforce_security_guards  # noqa: E402

_enforce_security_guards("production", database=DATABASES["default"], debug=DEBUG)  # noqa: F405
