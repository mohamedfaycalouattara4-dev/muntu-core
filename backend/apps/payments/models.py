"""Muntu Core — Payments : Payment, LedgerEntry (grand livre append-only).

Comptes ledger (domaine microfinance) :
    CASH, SAVINGS_DEPOSIT, LOAN_DISBURSEMENT, LOAN_REPAYMENT,
    INTEREST_PAID, FEE_REVENUE, PROVISION_EXPENSE, TRANSFER_IN, TRANSFER_OUT
"""
from __future__ import annotations

from django.db import models

from apps.core.models import TimeStampedModel, generate_ulid


class PaymentState(models.TextChoices):
    INITIALIZED = "INITIALIZED", "Initialisé"
    AUTHORIZED = "AUTHORIZED", "Autorisé"
    CAPTURED = "CAPTURED", "Capturé"
    COMPLETED = "COMPLETED", "Terminé"
    FAILED = "FAILED", "Échoué"
    REFUNDED = "REFUNDED", "Remboursé"


class Payment(TimeStampedModel):
    """Paiement — D5 corrigée : tenant_id + montant 64 bits."""
    id = models.CharField(max_length=26, primary_key=True, default=generate_ulid, editable=False)
    tenant_id = models.CharField(max_length=26, db_index=True, help_text="Isolation I2 : institution propriétaire.")

    # Références métier
    member_id = models.CharField(max_length=26, blank=True, db_index=True, help_text="ULID du membre (épargne/crédit).")
    loan_id = models.CharField(max_length=26, blank=True, db_index=True, help_text="ULID du prêt (si applicable).")
    savings_account_id = models.CharField(max_length=26, blank=True, db_index=True, help_text="ULID du compte épargne (si applicable).")
    teller_session_id = models.CharField(max_length=26, blank=True, db_index=True, help_text="ULID de la session caisse (si applicable).")

    aggregator = models.CharField(max_length=50, blank=True, help_text="WAVE / ORANGE_MONEY / MOOV / GIM_UEMOA / CASH / INTERNAL.")
    aggregator_ref = models.CharField(max_length=200, blank=True)
    means = models.CharField(max_length=50, default="INTERNAL", help_text="Mode de paiement.")

    # D5 : BigIntegerField (64 bits) — supporte jusqu'à 9 223 372 036 854 775 807 XOF
    amount_xof = models.BigIntegerField(help_text="Montant en XOF (64 bits, non signé via validation).")

    state = models.CharField(max_length=20, choices=PaymentState.choices, default=PaymentState.INITIALIZED, db_index=True)
    idempotency_key = models.CharField(max_length=64, unique=True, help_text="Clé d'idempotence.")
    aggregator_response = models.JSONField(default=dict, blank=True)
    intent_created_at = models.DateTimeField(null=True, blank=True)
    captured_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    refunded_at = models.DateTimeField(null=True, blank=True)
    version = models.IntegerField(default=0)
    performed_by = models.CharField(max_length=26, blank=True, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=["tenant_id", "state"]),
            models.Index(fields=["tenant_id", "member_id"]),
            models.Index(fields=["tenant_id", "created_at"]),
        ]

    def __str__(self):
        return f"Payment {self.id[:8]} — {self.amount_xof} XOF [{self.state}]"


class LedgerAccount(models.TextChoices):
    """Comptes du grand livre — domaine microfinance Muntu Core."""
    CASH = "CASH", "Caisse (espèces)"
    SAVINGS_DEPOSIT = "SAVINGS_DEPOSIT", "Dépôt d'épargne"
    LOAN_DISBURSEMENT = "LOAN_DISBURSEMENT", "Décaissement prêt"
    LOAN_REPAYMENT = "LOAN_REPAYMENT", "Remboursement prêt"
    LOAN_PRINCIPAL = "LOAN_PRINCIPAL", "Capital prêt"
    INTEREST_INCOME = "INTEREST_INCOME", "Revenus intérêts créditeurs"
    INTEREST_EXPENSE = "INTEREST_EXPENSE", "Charges intérêts débiteurs"
    FEE_REVENUE = "FEE_REVENUE", "Revenus frais"
    FEE_EXPENSE = "FEE_EXPENSE", "Charges frais"
    PROVISION_EXPENSE = "PROVISION_EXPENSE", "Provision dépréciation"
    TRANSFER_IN = "TRANSFER_IN", "Transfert entrant"
    TRANSFER_OUT = "TRANSFER_OUT", "Transfert sortant"
    EQUITY_SHARES = "EQUITY_SHARES", "Capital social (parts)"
    RESERVE = "RESERVE", "Réserve réglementaire"


class LedgerDirection(models.TextChoices):
    DEBIT = "DEBIT", "Débit"
    CREDIT = "CREDIT", "Crédit"


class LedgerEntry(TimeStampedModel):
    """Append-only · double-entry · chaînée HMAC · I2 tenant_id."""
    id = models.BigAutoField(primary_key=True)
    tenant_id = models.CharField(max_length=26, db_index=True, help_text="Isolation I2 : institution propriétaire.")

    account = models.CharField(max_length=30, choices=LedgerAccount.choices, db_index=True)
    direction = models.CharField(max_length=6, choices=LedgerDirection.choices)
    amount_xof = models.BigIntegerField(help_text="Montant en XOF (64 bits).")
    reference = models.CharField(max_length=200, db_index=True, help_text="Référence métier (ex: SAV-001-DEP-500000).")

    # Chaînage HMAC (intégrité I5)
    previous_hash = models.CharField(max_length=64, default="0" * 64)
    entry_hash = models.CharField(max_length=64, unique=True)
    signature = models.TextField(blank=True, help_text="Signature HMAC de la ligne.")

    # Audit
    recorded_by = models.CharField(max_length=26, default="system", db_index=True)
    day_id = models.CharField(max_length=26, blank=True, help_text="Référence à AccountingDay (scellement).")

    class Meta:
        ordering = ["id"]
        indexes = [
            models.Index(fields=["tenant_id", "account", "id"]),
            models.Index(fields=["tenant_id", "reference"]),
            models.Index(fields=["tenant_id", "day_id"]),
        ]

    def __str__(self):
        return f"#{self.id} {self.direction} {self.amount_xof} → {self.account}"
