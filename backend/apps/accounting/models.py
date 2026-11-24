"""Muntu Core — Modèles comptables : Plan comptable, Écritures, Journée.

I1 : Aucune écriture financière hors grand livre.
I5 : Aucune journée sans arrêté scellé.
"""
from __future__ import annotations
from django.db import models
from django.utils import timezone


def generate_ulid() -> str:
    import uuid
    ts = int(timezone.now().timestamp() * 1000)
    rnd = uuid.uuid4().hex[:16]
    return f"{ts:013x}{rnd}"


class AccountCategory(models.TextChoices):
    """Catégories du plan comptable SFD."""
    ASSET = "ASSET", "Actif (Classe 1-5)"
    LIABILITY = "LIABILITY", "Passif (Classe 1-5)"
    EQUITY = "EQUITY", "Capitaux propres"
    REVENUE = "REVENUE", "Produits (Classe 7)"
    EXPENSE = "EXPENSE", "Charges (Classe 6)"
    OFF_BALANCE = "OFF_BALANCE", "Hors bilan (Engagements)"


class ChartAccount(models.Model):
    """Plan comptable d'une institution — arborescence conforme SFD."""
    id = models.CharField(max_length=26, primary_key=True, default=generate_ulid, editable=False)
    tenant_id = models.CharField(max_length=26, db_index=True)
    code = models.CharField(max_length=20, db_index=True, help_text="Code comptable (ex: '401000').")
    name = models.CharField(max_length=255)
    category = models.CharField(max_length=20, choices=AccountCategory.choices)
    parent_code = models.CharField(max_length=20, blank=True, null=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [["tenant_id", "code"]]
        verbose_name = "Compte comptable"
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} — {self.name}"


class AccountingDay(models.Model):
    """Journée comptable — une seule ouverte par institution à la fois.

    I5 : Aucune journée sans arrêté scellé.
    Le scellement produit un condensat Merkle de toutes les écritures de la journée.
    """
    id = models.CharField(max_length=26, primary_key=True, default=generate_ulid, editable=False)
    tenant_id = models.CharField(max_length=26, db_index=True)
    day_date = models.DateField(db_index=True, help_text="Date comptable (YYYY-MM-DD).")
    branch_code = models.CharField(max_length=20, blank=True, help_text="Code agence (vide = consolidation).")
    status = models.CharField(
        max_length=20,
        choices=[
            ("OPEN", "Ouverte"),
            ("IN_PROGRESS", "En cours de traitement"),
            ("SEALED", "Scellée"),
            ("CLOSED", "Clôturée"),
        ],
        default="OPEN",
        db_index=True,
    )
    opened_at = models.DateTimeField(default=timezone.now)
    sealed_at = models.DateTimeField(null=True, blank=True)
    sealed_by = models.CharField(max_length=26, blank=True)
    merkle_root = models.CharField(max_length=64, blank=True, help_text="Condensat Merkle des écritures.")
    total_debit = models.BigIntegerField(default=0)
    total_credit = models.BigIntegerField(default=0)
    entry_count = models.IntegerField(default=0)
    is_balanced = models.BooleanField(default=False)
    notes = models.TextField(blank=True)

    class Meta:
        unique_together = [["tenant_id", "day_date", "branch_code"]]
        indexes = [models.Index(fields=["tenant_id", "status"])]

    def __str__(self):
        return f"Day {self.day_date} @ {self.tenant_id} [{self.status}]"

    def seal(self, sealed_by: str, merkle_root: str) -> None:
        """Scellement de la journée — produit le condensat Merkle."""
        self.status = "SEALED"
        self.sealed_at = timezone.now()
        self.sealed_by = sealed_by
        self.merkle_root = merkle_root
        self.save(update_fields=[
            "status", "sealed_at", "sealed_by", "merkle_root", "updated_at",
        ])


class JournalEntry(models.Model):
    """Écriture comptable — append-only, jamais modifiée.
    Seule l'extourne (contre-écriture) est permise.

    I1 : Aucune écriture hors grand livre.
    """
    id = models.CharField(max_length=26, primary_key=True, default=generate_ulid, editable=False)
    tenant_id = models.CharField(max_length=26, db_index=True)
    accounting_day_id = models.CharField(max_length=26, db_index=True)
    account_code = models.CharField(max_length=20, db_index=True)
    direction = models.CharField(max_length=6, choices=[("DEBIT", "Débit"), ("CREDIT", "Crédit")])
    amount_xof = models.BigIntegerField(help_text="Montant en unités mineures (64 bits).")
    description = models.TextField(blank=True)
    reference = models.CharField(max_length=200, blank=True, db_index=True)
    original_entry_id = models.CharField(
        max_length=26, blank=True, null=True,
        help_text="Référence à l'écriture extournée (si extourne).",
    )
    recorded_by = models.CharField(max_length=26, db_index=True)
    recorded_at = models.DateTimeField(default=timezone.now)
    previous_hash = models.CharField(max_length=64, blank=True)
    entry_hash = models.CharField(max_length=64, db_index=True)
    signature = models.TextField()

    class Meta:
        ordering = ["recorded_at"]
        indexes = [
            models.Index(fields=["tenant_id", "account_code"]),
            models.Index(fields=["tenant_id", "reference"]),
        ]

    def __str__(self):
        return f"{self.direction} {self.amount_xof} → {self.account_code} ({self.reference})"
