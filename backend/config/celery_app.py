"""Muntu Core — Configuration Celery."""
import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.prod")

app = Celery("muntu_core")
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discovery des tâches dans les modules Muntu Core
app.autodiscover_tasks([
    "apps.core",
    "apps.payments",
    "apps.tenancy",
    "apps.members",
    "apps.savings",
    "apps.lending",
    "apps.teller",
    "apps.accounting",
    "apps.regulatory",
    "apps.risk",
    "apps.compliance",
    "apps.audit",
    "apps.notifications",
    "apps.claims",
    "apps.documents",
])

# Tâches système : contexte RLS explicite (jamais de contournement)
from celery.signals import task_postrun, task_prerun  # noqa: E402


@task_prerun.connect
def _enter_system_rls_context(**_kwargs):
    """Pose le contexte système avant chaque tâche Celery."""
    from apps.core.middleware.rls import set_rls_context
    set_rls_context(user_id="system", roles=("system",), system=True)


@task_postrun.connect
def _exit_system_rls_context(**_kwargs):
    """Nettoie le contexte système après chaque tâche Celery."""
    from apps.core.middleware.rls import clear_rls_context
    clear_rls_context()


# ---------------------------------------------------------------------
# Beat schedule — tâches périodiques Muntu Core
# ---------------------------------------------------------------------
app.conf.beat_schedule = {
    # --- Sortie outbox (événements asynchrones) ---
    "dispatch-outbox": {
        "task": "apps.core.tasks.dispatch_outbox",
        "schedule": 5.0,
    },

    # --- Vérification intégrité grand livre (chainage HMAC) ---
    "verify-ledger-chain": {
        "task": "apps.core.tasks.verify_ledger_chain",
        "schedule": crontab(minute=0),  # toutes les heures
    },

    # --- Scellement quotidien (racine Merkle) ---
    "anchor-daily-merkle-root": {
        "task": "apps.core.tasks.anchor_daily_merkle_root",
        "schedule": crontab(hour=2, minute=0),  # 02h00 chaque jour
    },

    # --- Nettoyage nonces expirés ---
    "cleanup-expired-nonces": {
        "task": "apps.core.tasks.cleanup_expired_nonces",
        "schedule": crontab(hour=3, minute=0),
    },

    # --- Rotation clés de signature (mensuel, tolérance 90j) ---
    "rotate-signing-keys": {
        "task": "apps.core.tasks.rotate_signing_keys",
        "schedule": crontab(day_of_month=1, hour=4, minute=0),
    },

    # --- Reconciliation paiements en attente ---
    "reconcile-pending-payments": {
        "task": "apps.payments.tasks.reconcile_pending_payments",
        "schedule": 60.0,
    },

    # --- Vérification timeouts paiements (webhooks/aggregators) ---
    "check-payment-timeouts": {
        "task": "apps.payments.tasks.check_payment_timeouts",
        "schedule": 60.0,
    },

    # --- Calcul intérêts créditeurs quotidiens ---
    "compute-daily-interest-accruals": {
        "task": "apps.savings.tasks.compute_daily_interest",
        "schedule": crontab(hour=23, minute=30),  # 23h30 chaque jour
    },

    # --- Vérification échéances prêt (retards, provisions) ---
    "check-loan-due-dates": {
        "task": "apps.lending.tasks.check_due_dates",
        "schedule": crontab(hour=6, minute=0),
    },

    # --- Alertes AML / conformité ---
    "generate-compliance-reports": {
        "task": "apps.compliance.tasks.generate_daily_reports",
        "schedule": crontab(hour=6, minute=0),
    },

    # --- Purge notifications expirées ---
    "cleanup-expired-notifications": {
        "task": "apps.notifications.tasks.cleanup_expired",
        "schedule": crontab(hour=4, minute=0),
    },
}
