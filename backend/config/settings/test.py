"""KALYCE · Settings de test.

Le socle applicatif est Postgres-first (ArrayField, triggers/rules SQL,
contraintes d'intégrité). Les tests tournent donc sur PostgreSQL, comme la
production, afin de valider réellement les invariants métier.
"""
from .base import *  # noqa: F401,F403

DEBUG = False
SECRET_KEY = "test-secret"  # noqa: S105
ENVIRONMENT = "test"
PAYMENTS_ALLOW_SIMULATED_ADAPTERS = True
WEBAUTHN_RP_ID = "localhost"
WEBAUTHN_ALLOWED_ORIGINS = ["https://localhost"]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("DB_NAME", "kalyce"),  # noqa: F405
        "USER": os.getenv("DB_USER", "kalyce"),  # noqa: F405
        "PASSWORD": os.getenv("DB_PASSWORD", "kalyce"),  # noqa: F405
        "HOST": os.getenv("DB_HOST", "localhost"),  # noqa: F405
        "PORT": os.getenv("DB_PORT", "5432"),  # noqa: F405
        "TEST": {"NAME": os.getenv("DB_TEST_NAME", "test_kalyce")},  # noqa: F405
    }
}

# Cache local-memory : aucune dépendance Redis pour la suite de tests.
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
IDEMPOTENCY_TTL_SECONDS = 60
HSZ_SIGNING_KEY = "a" * 64
AUDIT_SIGNING_KEY = "b" * 64

# ---------- JWT : paire RSA éphémère (parité RS256 avec la production) ----------
from cryptography.hazmat.primitives import serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import rsa  # noqa: E402

_test_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
SIMPLE_JWT = {  # noqa: F405
    **SIMPLE_JWT,  # noqa: F405
    "SIGNING_KEY": _test_private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode(),
    "VERIFYING_KEY": _test_private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode(),
}

# ---------- OTP Argon2id : paramètres allégés (vitesse de suite de tests) ----------
os.environ.setdefault("OTP_ARGON2_TIME_COST", "1")  # noqa: F405
os.environ.setdefault("OTP_ARGON2_MEMORY_COST", "8192")  # noqa: F405
os.environ.setdefault("OTP_ARGON2_PARALLELISM", "1")  # noqa: F405
PROMETHEUS_METRICS_ENABLED = True
METRICS_TOKEN = "test-metrics-token"  # noqa: S105
