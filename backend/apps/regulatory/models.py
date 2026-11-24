"""Muntu Core — Modèles réglementaires : états BCEAO, centrale des risques, AML."""
from __future__ import annotations
from django.db import models
from django.utils import timezone


def generate_ulid() -> str:
    import uuid
    ts = int(timezone.now().timestamp() * 1000)
    rnd = uuid.uuid4().hex[:16]
    return f"{ts:013x}{rnd}"


class RegulatoryReportType(models.TextChoices):
    BALANCE_SHEET = "BALANCE_SHEET", "Bilan"
    INCOME_STATEMENT = "INCOME_STATEMENT", "Compte de résultat"
    PRUDENTIAL_RATIOS = "PRUDENTIAL_RATIOS", "Ratios prudentiels"
    RISK_CENTER = "RISK_CENTER", "Centrale des risques"
    AML_REPORT = "AML_REPORT", "Déclaration de soupçon"
    CASH_POSITION = "CASH_POSITION", "Situation de caisse"
    PORTFOLIO_SUMMARY = "PORTFOLIO_SUMMARY", "État du portefeuille"
    MEMBER_LIST = "MEMBER_LIST", "Liste des membres"


class RegulatoryReport(models.Model):
    """État réglementaire généré pour une période donnée."""
    id = models.CharField(max_length=26, primary_key=True, default=generate_ulid, editable=False)
    tenant_id = models.CharField(max_length=26, db_index=True)
    report_type = models.CharField(max_length=30, choices=RegulatoryReportType.choices)
    period_start = models.DateField(db_index=True)
    period_end = models.DateField()
    generated_at = models.DateTimeField(default=timezone.now)
    generated_by = models.CharField(max_length=26)
    file_path = models.CharField(max_length=500, blank=True, help_text="Chemin du fichier généré (PDF/XLSX).")
    file_hash = models.CharField(max_length=64, blank=True)
    data_snapshot = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=20,
        choices=[("DRAFT", "Brouillon"), ("GENERATED", "Généré"), ("SUBMITTED", "Transmis"), ("APPROVED", "Approuvé")],
        default="DRAFT",
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [["tenant_id", "report_type", "period_start", "period_end"]]
        indexes = [models.Index(fields=["tenant_id", "report_type", "period_end"])]

    def __str__(self):
        return f"{self.report_type} {self.period_start} → {self.period_end}"


class RiskCenterEntry(models.Model):
    """Entrée centrale des risques — crédit par membre."""
    id = models.CharField(max_length=26, primary_key=True, default=generate_ulid, editable=False)
    tenant_id = models.CharField(max_length=26, db_index=True)
    member_id = models.CharField(max_length=26, db_index=True)
    reporting_date = models.DateField(db_index=True)
    total_credit_granted = models.BigIntegerField(default=0)
    total_credit_outstanding = models.BigIntegerField(default=0)
    total_credit_overdue = models.BigIntegerField(default=0)
    total_credit_defaulted = models.BigIntegerField(default=0)
    number_of_active_loans = models.IntegerField(default=0)
    number_of_overdue_loans = models.IntegerField(default=0)
    risk_classification = models.CharField(max_length=5, blank=True)

    class Meta:
        unique_together = [["tenant_id", "member_id", "reporting_date"]]


class AMLAlert(models.Model):
    """Alerte anti-blanchiment — seuil de déclaration, soupçon, listes de surveillance."""
    id = models.CharField(max_length=26, primary_key=True, default=generate_ulid, editable=False)
    tenant_id = models.CharField(max_length=26, db_index=True)
    member_id = models.CharField(max_length=26, db_index=True)
    alert_type = models.CharField(
        max_length=30,
        choices=[
            ("THRESHOLD", "Dépassement de seuil"),
            ("SUSPICIOUS", "Opération suspecte"),
            ("WATCHLIST", "Correspondance liste de surveillance"),
            ("PATTERN", "Motif atypique"),
        ],
    )
    description = models.TextField()
    amount_xof = models.BigIntegerField(default=0)
    severity = models.CharField(
        max_length=10, choices=[("LOW", "Faible"), ("MEDIUM", "Moyenne"), ("HIGH", "Élevée"), ("CRITICAL", "Critique")],
        default="MEDIUM",
    )
    status = models.CharField(
        max_length=20,
        choices=[("NEW", "Nouvelle"), ("UNDER_REVIEW", "En examen"), ("REPORTED", "Déclarée"), ("CLOSED", "Clôturée")],
        default="NEW",
    )
    reviewed_by = models.CharField(max_length=26, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    declared_to_authority = models.BooleanField(default=False)
    declared_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["tenant_id", "severity", "status"])]
