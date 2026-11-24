"""Muntu Core — Modèles crédit : produits, dossiers, échéanciers, règlements, garanties.

Le domaine crédit est le plus lourd et le plus décisif à l'achat.
Toutes les fonctions de calcul d'échéancier sont pures et testables unitairement.
"""
from __future__ import annotations
from decimal import Decimal
from django.db import models
from django.utils import timezone


def generate_ulid() -> str:
    import uuid
    ts = int(timezone.now().timestamp() * 1000)
    rnd = uuid.uuid4().hex[:16]
    return f"{ts:013x}{rnd}"


class LoanProduct(models.Model):
    """Définition immuable d'un produit de crédit — versionnée."""
    id = models.CharField(max_length=26, primary_key=True, default=generate_ulid, editable=False)
    tenant_id = models.CharField(max_length=26, db_index=True)
    name = models.CharField(max_length=255)
    version = models.IntegerField(default=1)
    is_active = models.BooleanField(default=True)

    # Paramètres
    minimum_amount = models.BigIntegerField(default=10000)
    maximum_amount = models.BigIntegerField(default=50000000)
    minimum_term_months = models.IntegerField(default=1)
    maximum_term_months = models.IntegerField(default=60)
    annual_interest_rate = models.DecimalField(max_digits=10, decimal_places=6, default=Decimal("0"))
    late_fee_rate = models.DecimalField(
        max_digits=5, decimal_places=4, default=Decimal("0.01"),
        help_text="Pénalité de retard mensuelle (ex: 0.0100 = 1%/mois).",
    )
    grace_period_days = models.IntegerField(default=3, help_text="Jours de tolérance après échéance.")
    repayment_frequency = models.CharField(
        max_length=20,
        choices=[("WEEKLY", "Hebdomadaire"), ("BIWEEKLY", "Bi-hebdomadaire"), ("MONTHLY", "Mensuelle")],
        default="MONTHLY",
    )
    amortization_method = models.CharField(
        max_length=20,
        choices=[("FLAT", "Linéaire (flat)"), ("DECLINING", "Dégressive (declining balance)"), ("FRENCH", "Française")],
        default="FLAT",
        help_text="Méthode de calcul de l'échéancier.",
    )
    requires_guarantor = models.BooleanField(default=False)
    requires_collateral = models.BooleanField(default=False)
    min_guarantor_count = models.IntegerField(default=0)

    # Seuil de délégation (quorum)
    committee_threshold = models.BigIntegerField(
        default=1000000,
        help_text="Montant au-delà duquel le comité de crédit est obligatoire.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [["tenant_id", "name", "version"]]

    def __str__(self):
        return f"{self.name} v{self.version}"


class LoanStatus(models.TextChoices):
    DRAFT = "DRAFT", "Brouillon"
    UNDER_REVIEW = "UNDER_REVIEW", "En examen"
    COMMITTEE = "COMMITTEE", "En comité de crédit"
    APPROVED = "APPROVED", "Approuvé"
    DISBURSED = "DISBURSED", "Décaissé (actif)"
    REPAID = "REPAID", "Remboursé"
    DELINQUENT = "DELINQUENT", "Impayé"
    RESCHEDULED = "RESCHEDULED", "Rééchelonné"
    WRITTEN_OFF = "WRITTEN_OFF", "Radié"
    REJECTED = "REJECTED", "Rejeté"
    CANCELLED = "CANCELLED", "Annulé"


class Loan(models.Model):
    """Dossier de crédit — machine à états signée.

    L'échéancier est figé après approbation.
    Tout calcul d'échéancier est une fonction pure.
    """
    id = models.CharField(max_length=26, primary_key=True, default=generate_ulid, editable=False)
    tenant_id = models.CharField(max_length=26, db_index=True)
    loan_number = models.CharField(max_length=50, unique=True, db_index=True, help_text="Numéro de prêt (ex: 'P-2024-00001').")
    product = models.ForeignKey(LoanProduct, on_delete=models.PROTECT, related_name="loans")
    member_id = models.CharField(max_length=26, db_index=True)
    group_id = models.CharField(max_length=26, blank=True, help_text="ULID du groupe solidaire (si applicable).")

    # Montants
    requested_amount = models.BigIntegerField()
    approved_amount = models.BigIntegerField(default=0)
    disbursement_amount = models.BigIntegerField(default=0)
    outstanding_principal = models.BigIntegerField(default=0, help_text="Capital restant dû (64 bits).")
    outstanding_interest = models.BigIntegerField(default=0, help_text="Intérêts restants dus (64 bits).")
    total_repaid = models.BigIntegerField(default=0, help_text="Total des règlements reçus.")

    # Paramètres du prêt
    interest_rate = models.DecimalField(max_digits=10, decimal_places=6)
    term_months = models.IntegerField()
    repayment_frequency = models.CharField(max_length=20)

    # Dates
    requested_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    disbursed_at = models.DateTimeField(null=True, blank=True)
    first_due_date = models.DateField(null=True, blank=True)
    maturity_date = models.DateField(null=True, blank=True)
    repaid_at = models.DateTimeField(null=True, blank=True)
    last_payment_at = models.DateTimeField(null=True, blank=True)

    # Cycle de vie
    status = models.CharField(max_length=20, choices=LoanStatus.choices, default=LoanStatus.DRAFT, db_index=True)
    approved_by = models.CharField(max_length=26, blank=True)
    disbursed_by = models.CharField(max_length=26, blank=True)
    agent_id = models.CharField(max_length=26, blank=True, help_text="Agent de crédit responsable.")
    branch_code = models.CharField(max_length=20, blank=True)

    # État machine à états signée
    fsm_state = models.CharField(max_length=20, default="DRAFT", db_index=True, help_text="État de la machine signée.")
    fsm_signature = models.CharField(max_length=64, blank=True, help_text="Dernière signature HMAC de transition.")

    # Risque
    risk_class = models.CharField(max_length=10, blank=True, help_text="Classification du risque (A-E ou 0-5).")
    impairment_provision = models.BigIntegerField(default=0, help_text="Provision pour dépréciation.")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["tenant_id", "member_id"]),
            models.Index(fields=["tenant_id", "status"]),
            models.Index(fields=["tenant_id", "agent_id"]),
        ]

    def __str__(self):
        return f"{self.loan_number} [{self.status}]"

    @property
    def is_active(self) -> bool:
        return self.status in (LoanStatus.DISBURSED, LoanStatus.DELINQUENT)


class LoanInstallment(models.Model):
    """Ligne d'échéancier — fonction pure, déterministe.

    Fixé après approbation. Jamais modifié (rééchelonnement = clôture + remplacement).
    """
    id = models.CharField(max_length=26, primary_key=True, default=generate_ulid, editable=False)
    loan = models.ForeignKey(Loan, on_delete=models.CASCADE, related_name="installments")
    installment_number = models.IntegerField(help_text="Numéro de l'échéance (1-based).")
    due_date = models.DateField(db_index=True)
    principal_amount = models.BigIntegerField()
    interest_amount = models.BigIntegerField()
    total_amount = models.BigIntegerField(help_text="Principal + intérêt + frais.")
    paid_amount = models.BigIntegerField(default=0)
    paid_at = models.DateTimeField(null=True, blank=True)
    is_paid = models.BooleanField(default=False)
    late_fee = models.BigIntegerField(default=0)
    days_late = models.IntegerField(default=0)

    class Meta:
        unique_together = [["loan", "installment_number"]]
        ordering = ["installment_number"]

    def __str__(self):
        status = "PAYÉ" if self.is_paid else f"EN RETARD ({self.days_late}j)" if self.days_late > 0 else "EN ATTENTE"
        return f"Échéance {self.installment_number}: {self.total_amount} [{status}]"


class LoanPayment(models.Model):
    """Règlement partiel ou total d'une échéance.

    Imputation stricte : 1) frais de retard, 2) intérêt, 3) principal.
    """
    id = models.CharField(max_length=26, primary_key=True, default=generate_ulid, editable=False)
    loan = models.ForeignKey(Loan, on_delete=models.CASCADE, related_name="payments")
    installment = models.ForeignKey(LoanInstallment, on_delete=models.PROTECT, null=True, blank=True)
    amount = models.BigIntegerField()
    late_fee_applied = models.BigIntegerField(default=0)
    interest_applied = models.BigIntegerField(default=0)
    principal_applied = models.BigIntegerField(default=0)
    payment_date = models.DateField(db_index=True)
    payment_method = models.CharField(
        max_length=20,
        choices=[("CASH", "Espèces"), ("TRANSFER", "Virement"), ("MOBILE_MONEY", "Mobile money"), ("DEBIT", "Prélèvement")],
        default="CASH",
    )
    received_by = models.CharField(max_length=26, db_index=True)
    reference = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["payment_date"]


class Guarantee(models.Model):
    """Garantie d'un prêt — caution personnelle ou nantissement."""
    id = models.CharField(max_length=26, primary_key=True, default=generate_ulid, editable=False)
    loan = models.ForeignKey(Loan, on_delete=models.CASCADE, related_name="guarantees")
    type = models.CharField(
        max_length=20,
        choices=[
            ("PERSONAL", "Caution personnelle"),
            ("GROUP", "Caution solidaire (groupe)"),
            ("COLLATERAL", "Nantissement / sûreté réelle"),
        ],
    )
    guarantor_member_id = models.CharField(max_length=26, blank=True, help_text="ULID du garant (si personnel).")
    group_id = models.CharField(max_length=26, blank=True, help_text="ULID du groupe solidaire (si groupe).")
    collateral_type = models.CharField(max_length=100, blank=True, help_text="Type de bien garanti.")
    collateral_value = models.BigIntegerField(default=0)
    collateral_reference = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)

    class Meta:
        indexes = [models.Index(fields=["loan", "type"])]

    def __str__(self):
        return f"Garantie {self.type} pour {self.loan.loan_number}"
