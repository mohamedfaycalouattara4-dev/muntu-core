from .base import *  # noqa: F401,F403

ENVIRONMENT = "dev"
DEBUG = True
ALLOWED_HOSTS = ["*"]
# Secrets de développement uniquement — jamais utilisés hors poste local.
SECRET_KEY = "dev-secret-not-for-prod"  # noqa: S105
os.environ.setdefault("KALYCE_ALLOW_INSECURE_DEV_KEYS", "true")  # noqa: F405
PAYMENTS_ALLOW_SIMULATED_ADAPTERS = True
WEBAUTHN_RP_ID = os.getenv("WEBAUTHN_RP_ID", "localhost")  # noqa: F405
WEBAUTHN_ALLOWED_ORIGINS = [  # noqa: F405
    o for o in os.getenv("WEBAUTHN_ALLOWED_ORIGINS",
                         "http://localhost:5173,http://localhost:3000").split(",") if o
]
