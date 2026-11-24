import logging

from celery import shared_task

logger = logging.getLogger("muntu.compliance")


@shared_task(name="apps.compliance.tasks.generate_daily_reports")
def generate_daily_reports() -> dict:
    """Synthèse réglementaire BCEAO quotidienne."""
    from apps.payments.models import Payment, LedgerEntry  # noqa
    from apps.risk.models import AMLAlert  # noqa
    from django.utils import timezone
    today = timezone.now().date().isoformat()
    report = {
        "date": today,
        "payments_count": Payment.objects.count(),
        "ledger_entries": LedgerEntry.objects.count(),
        "open_aml_alerts": AMLAlert.objects.filter(status="open").count(),
    }
    logger.info("Compliance daily report=%s", report)
    return report
