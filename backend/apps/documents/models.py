"""Muntu Core — Documents : contrats, échéanciers, reçus, relevés, attestations."""
from __future__ import annotations
from django.db import models
from django.utils import timezone


def generate_ulid() -> str:
    import uuid
    ts = int(timezone.now().timestamp() * 1000)
    rnd = uuid.uuid4().hex[:16]
    return f"{ts:013x}{rnd}"


class DocumentType(models.TextChoices):
    MEMBERSHIP_CARD = "MEMBERSHIP_CARD", "Carte de membre / Livret"
    LOAN_CONTRACT = "LOAN_CONTRACT", "Contrat de prêt"
    SAVINGS_STATEMENT = "SAVINGS_STATEMENT", "Relevé d'épargne"
    LOAN_STATEMENT = "LOAN_STATEMENT", "Relevé de prêt"
    REPAYMENT_SCHEDULE = "REPAYMENT_SCHEDULE", "Échéancier de remboursement"
    RECEIPT = "RECEIPT", "Reçu de transaction"
    INTEGRITY_ATTESTATION = "INTEGRITY_ATTESTATION", "Attestation d'intégrité Merkle"
    CLOSING_STATEMENT = "CLOSING_STATEMENT", "Arrêté de caisse"
    ACCOUNT_STATEMENT = "ACCOUNT_STATEMENT", "Relevé de compte"


class Document(models.Model):
    """Document généré — traçabilité complète."""
    id = models.CharField(max_length=26, primary_key=True, default=generate_ulid, editable=False)
    tenant_id = models.CharField(max_length=26, db_index=True)
    member_id = models.CharField(max_length=26, blank=True)
    document_type = models.CharField(max_length=30, choices=DocumentType.choices, db_index=True)
    reference = models.CharField(max_length=200, blank=True, help_text="Référence liée (compte, prêt, transaction).")
    period_start = models.DateField(null=True, blank=True)
    period_end = models.DateField(null=True, blank=True)
    file_path = models.CharField(max_length=500, blank=True)
    file_format = models.CharField(max_length=10, default="PDF", choices=[("PDF", "PDF"), ("XLSX", "Excel"), ("CSV", "CSV")])
    file_hash = models.CharField(max_length=64, blank=True, help_text="SHA-256 du fichier généré.")
    generated_by = models.CharField(max_length=26)
    generated_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["tenant_id", "document_type"]),
            models.Index(fields=["tenant_id", "member_id"]),
        ]

    def __str__(self):
        return f"{self.document_type} {self.reference} ({self.file_format})"


class DocumentTemplate(models.Model):
    """Modèle de document paramétrable par institution."""
    id = models.CharField(max_length=26, primary_key=True, default=generate_ulid, editable=False)
    tenant_id = models.CharField(max_length=26, db_index=True)
    document_type = models.CharField(max_length=30, choices=DocumentType.choices)
    template_name = models.CharField(max_length=255)
    content_html = models.TextField(blank=True, help_text="Modèle HTML avec variables {{variable}}.")
    language = models.CharField(max_length=5, default="fr")
    is_active = models.BooleanField(default=True)
    version = models.IntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [["tenant_id", "document_type", "version"]]
