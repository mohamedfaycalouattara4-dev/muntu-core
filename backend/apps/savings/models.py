"""Muntu Core — Modèles épargne : produits, comptes, intérêts créditeurs, blocages.

Produits pilotés par le moteur de paramétrage :
- Dépôt à vue, Épargne à terme, Épargne programmée, Épargne nantie, Part sociale.

Calcul des intérêts : quotidien, traçable dans le grand livre, idempotent, rejouable.
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


class SavingsProductType(models.TextChoices):
    CURRENT = "CURRENT", "Dépôt à vue"
    TERM = "TERM", "Épargne à terme"
    PROGRAMMED = "PROGRAMMED", "Épargne programmée"
    COLLATERAL = "COLLATERAL", "Épargne nantie"
    SHARE = "SHARE", "Part sociale"


class SavingsAccountStatus(models.TextChoices):
    DRAFT = "DRAFT", "En cours de création"
    ACTIVE = "ACTIVE", "Actif"
    BLOCKED = "BLOCKED", "Bloqué"
    CLOSED = "CLOSED", "Clôturé"


class InterestFrequency(models.TextChoices):
    DAILY = "DAILY", "Quotidien"
    MONTHLY = "MONTHLY", "Mensuel"
    QUARTERLY = "QUARTERLY", "Trimestriel"
    SEMI_ANNUAL = "SEMI_ANNUAL", "Semestriel"
    ANNUAL = "ANNUAL", "Annuel"
    AT_MATURITY = "AT_MATURITY", "À l'échéance"


class SavingsProduct(models.Model):
    """Définition immuable d'un produit d'épargne — versionnée."""
    id = models.CharField(max_length=26, primary_key=True, default=generate_ulid, editable=False)
    tenant_id = models.CharField(max_length=26, db_index=True)
    name = models.CharField(max_length=255)
    product_type = models.CharField(max_length=20, choices=SavingsProductType.choices)
    version = models.IntegerField(default=1)
    is_active = models.BooleanField(default=True)

    # Paramètres
    minimum_balance = models.BigIntegerField(default=0, help_text="Solde minimum en unités mineures.")
    maximum_balance = models.BigIntegerField(default=0, help_text="0 = pas de plafond.")
    annual_interest_rate = models.DecimalField(
        max_digits=10, decimal_places=6, default=Decimal("0"),
        help_text="Taux créditeur annuel en pourcentage (ex: 3.500000 = 3.5%).",
    )
    interest_frequency = models.CharField(
        max_length=20, choices=InterestFrequency.choices, default=InterestFrequency.MONTHLY,
    )
    interest_compounding = models.BooleanField(
        default=False, help_text="Vrai si les intérêts sont capitalisés (intérêts composés)."
    )
    withdrawal_fee = models.BigIntegerField(default=0, help_text="Frais de retrait par opération.")
    monthly_maintenance_fee = models.BigIntegerField(default=0, help_text="Frais de tenue mensuels.")
    minimum_term_days = models.IntegerField(default=0, help_text="Durée minimale (0 = dépôt à vue).")
    penalty_rate = models.DecimalField(
        max_digits=5, decimal_places=4, default=Decimal("0"),
        help_text="Pénalité de rupture anticipée (ex: 0.0100 = 1%).",
    )
    auto_renewal = models.BooleanField(default=True, help_text="Renouvellement automatique à échéance.")

    # Contraintes opérationnelles
    daily_withdrawal_limit = models.BigIntegerField(default=0, help_text="0 = pas de limite.")
    min_withdrawal = models.BigIntegerField(default=500, help_text="Retrait minimum.")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [["tenant_id", "name", "version"]]
        indexes = [models.Index(fields=["tenant_id", "product_type", "is_active"])]

    def __str__(self):
        return f"{self.name} v{self.version} ({self.product_type})"


class SavingsAccount(models.Model):
    """Compte d'épargne rattaché à un membre et à un produit.

    Le solde n'est jamais stocké directement : il est projeté depuis le grand livre.
    """
    id = models.CharField(max_length=26, primary_key=True, default=generate_ulid, editable=False)
    tenant_id = models.CharField(max_length=26, db_index=True)
    member_id = models.CharField(max_length=26, db_index=True, help_text="ULID du membre.")
    product = models.ForeignKey(SavingsProduct, on_delete=models.PROTECT, related_name="accounts")
    account_number = models.CharField(max_length=50, unique=True, db_index=True, help_text="Numéro de compte unique.")
    status = models.CharField(max_length=20, choices=SavingsAccountStatus.choices, default=SavingsAccountStatus.DRAFT, db_index=True)

    # Dates
    opened_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    maturity_date = models.DateField(null=True, blank=True, help_text="Date d'échéance (terme / programmée).")

    # Programmée
    periodic_amount = models.BigIntegerField(default=0, help_text="Montant de versement périodique.")
    periodic_frequency = models.CharField(
        max_length=20,
        choices=[("DAILY", "Quotidien"), ("WEEKLY", "Hebdomadaire"), ("MONTHLY", "Mensuelle")],
        blank=True,
    )
    periodic_next_due = models.DateField(null=True, blank=True)

    # Nantie
    blocked_amount = models.BigIntegerField(default=0, help_text="Montant bloqué en garantie d'un prêt.")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["tenant_id", "member_id"]),
            models.Index(fields=["tenant_id", "status"]),
        ]

    def __str__(self):
        return f"Compte {self.account_number} ({self.status})"

    def activate(self) -> None:
        self.status = SavingsAccountStatus.ACTIVE
        self.opened_at = timezone.now()
        self.save(update_fields=["status", "opened_at", "updated_at"])


class InterestAccrual(models.Model):
    """Calcul quotidien d'intérêts créditeurs — fonction pure, idempotente.

    Chaque accrual est une projection rejouable : même date + même solde = même résultat.
    Traçable dans le grand livre via reference.
    """
    id = models.CharField(max_length=26, primary_key=True, default=generate_ulid, editable=False)
    tenant_id = models.CharField(max_length=26, db_index=True)
    account = models.ForeignKey(SavingsAccount, on_delete=models.CASCADE, related_name="interest_accruals")
    accrual_date = models.DateField(db_index=True, help_text="Date du calcul (un par jour max).")
    opening_balance = models.BigIntegerField(help_text="Solde en début de journée.")
    daily_rate = models.DecimalField(
        max_digits=12, decimal_places=8,
        help_text="Taux journalier (annual_rate / 360 ou 365).",
    )
    interest_amount = models.BigIntegerField(help_text="Intérêt calculé pour la journée (tronqué).")
    cumulative_interest = models.BigIntegerField(help_text="Total des intérêts accumulés depuis l'ouverture.")
    is_credited = models.BooleanField(default=False, help_text="Vrai si l'intérêt a été crédité au compte.")
    ledger_reference = models.CharField(max_length=200, blank=True, help_text="Référence de l'écriture au grand livre.")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [["account", "accrual_date"]]
        ordering = ["accrual_date"]

    def __str__(self):
        return f"Intérêt {self.accrual_date} : +{self.interest_amount} (cumul: {self.cumulative_interest})"
