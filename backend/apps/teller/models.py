"""Muntu Core — Modèles caisse : sessions de guichet, opérations, transferts.

Trois temps : OUVERTURE → OPÉRATIONS → ARRÊTÉ (scellement).
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


class TellerSessionStatus(models.TextChoices):
    OPENING = "OPENING", "Ouverture en cours"
    OPEN = "OPEN", "Ouverte"
    CLOSING = "CLOSING", "Arrêté en cours"
    SEALED = "SEALED", "Scellée"


class TellerOperationType(models.TextChoices):
    DEPOSIT = "DEPOSIT", "Dépôt (entrée caisse)"
    WITHDRAWAL = "WITHDRAWAL", "Retrait (sortie caisse)"
    TRANSFER_IN = "TRANSFER_IN", "Transfert reçu"
    TRANSFER_OUT = "TRANSFER_OUT", "Transfert envoyé"
    OPENING = "OPENING", "Dotation d'ouverture"
    CLOSING = "CLOSING", "Remise de clôture"
    CORRECTION = "CORRECTION", "Correction d'écart"


class TellerSession(models.Model):
    """Session de caisse d'un guichetier pour une journée.

    Ouverture : dotation initiale (fonds de caisse).
    Opérations : dépôts, retraits, transferts.
    Arrêté : comptage réel + scellement Merkle.
    """
    id = models.CharField(max_length=26, primary_key=True, default=generate_ulid, editable=False)
    tenant_id = models.CharField(max_length=26, db_index=True)
    branch_code = models.CharField(max_length=20, db_index=True)
    teller_id = models.CharField(max_length=26, db_index=True, help_text="ULID du guichetier.")
    teller_name = models.CharField(max_length=255, blank=True, help_text="Nom affiché.")

    status = models.CharField(max_length=20, choices=TellerSessionStatus.choices, default=TellerSessionStatus.OPENING, db_index=True)

    # Ouverture
    opening_balance = models.BigIntegerField(default=0, help_text="Fonds de caisse initiaux (dotation).")
    opened_at = models.DateTimeField(default=timezone.now)
    business_date = models.DateField(
        db_index=True, null=True, blank=True,
        help_text="Journée comptable de la session (dérivée de opened_at).")
    opened_by = models.CharField(max_length=26, blank=True)

    # Clôture
    expected_balance = models.BigIntegerField(default=0, help_text="Solde théorique après opérations.")
    counted_balance = models.BigIntegerField(default=0, help_text="Solde compté physiquement.")
    discrepancy = models.BigIntegerField(default=0, help_text="Écart (compté - théorique).")
    closed_at = models.DateTimeField(null=True, blank=True)
    closed_by = models.CharField(max_length=26, blank=True)
    sealed_at = models.DateTimeField(null=True, blank=True)
    sealed_by = models.CharField(max_length=26, blank=True)
    merkle_root = models.CharField(max_length=64, blank=True, help_text="Condensat Merkle des opérations.")

    # Totaux
    total_deposits = models.BigIntegerField(default=0)
    total_withdrawals = models.BigIntegerField(default=0)
    total_transfers_in = models.BigIntegerField(default=0)
    total_transfers_out = models.BigIntegerField(default=0)
    operation_count = models.IntegerField(default=0)

    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            # Une seule session par guichetier, par guichet et par journée
            # comptable (`opened_at__date` n'est pas un champ : la date est
            # matérialisée dans `business_date`).
            models.UniqueConstraint(
                fields=["tenant_id", "branch_code", "teller_id", "business_date"],
                name="uniq_teller_session_per_day",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant_id", "status"]),
            models.Index(fields=["tenant_id", "branch_code"]),
        ]

    def save(self, *args, **kwargs):
        """Matérialise la journée comptable avant écriture."""
        if self.business_date is None:
            opened = self.opened_at or timezone.now()
            self.business_date = timezone.localtime(opened).date()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"Session {self.id[:8]} @ {self.branch_code} [{self.status}]"

    @property
    def current_balance(self) -> int:
        """Solde théorique courant."""
        return (
            self.opening_balance
            + self.total_deposits
            - self.total_withdrawals
            + self.total_transfers_in
            - self.total_transfers_out
        )

    def open(self, dotation: int, opened_by: str) -> None:
        """Ouverture de la session avec dotation initiale."""
        self.opening_balance = dotation
        self.status = TellerSessionStatus.OPEN
        self.opened_by = opened_by
        self.opened_at = timezone.now()
        self.save(update_fields=[
            "opening_balance", "status", "opened_by", "opened_at", "updated_at",
        ])

    def seal(self, counted: int, sealed_by: str, merkle_root: str) -> None:
        """Scellement de l'arrêté de caisse."""
        expected = self.current_balance
        self.counted_balance = counted
        self.expected_balance = expected
        self.discrepancy = counted - expected
        self.status = TellerSessionStatus.SEALED
        self.sealed_at = timezone.now()
        self.sealed_by = sealed_by
        self.merkle_root = merkle_root
        self.save(update_fields=[
            "counted_balance", "expected_balance", "discrepancy",
            "status", "sealed_at", "sealed_by", "merkle_root", "updated_at",
        ])


class TellerOperation(models.Model):
    """Opération de caisse — dépôts, retraits, transferts."""
    id = models.CharField(max_length=26, primary_key=True, default=generate_ulid, editable=False)
    session = models.ForeignKey(TellerSession, on_delete=models.CASCADE, related_name="operations")
    tenant_id = models.CharField(max_length=26, db_index=True)
    operation_type = models.CharField(max_length=20, choices=TellerOperationType.choices, db_index=True)
    amount = models.BigIntegerField()
    counterparty_member_id = models.CharField(max_length=26, blank=True, help_text="Membre concerné (si applicable).")
    counterparty_account = models.CharField(max_length=50, blank=True)
    reference = models.CharField(max_length=200, blank=True, help_text="Référence de l'opération métier.")
    proof_code = models.CharField(max_length=64, blank=True, help_text="OTP de preuve (hérité de delivery).")
    receipt_number = models.CharField(max_length=50, blank=True)
    performed_at = models.DateTimeField(default=timezone.now)
    performed_by = models.CharField(max_length=26, db_index=True)

    class Meta:
        ordering = ["performed_at"]
        indexes = [
            models.Index(fields=["tenant_id", "operation_type"]),
            models.Index(fields=["tenant_id", "counterparty_member_id"]),
        ]

    def __str__(self):
        return f"{self.operation_type} {self.amount} (session {self.session_id[:8]})"


class TellerTransfer(models.Model):
    """Transfert de fonds entre caisses ou vers le coffre.

    Réutilise le mécanisme de sceau/OTP hérité de delivery.
    Double contrôle : émetteur signe, receveur confirme avec OTP.
    """
    id = models.CharField(max_length=26, primary_key=True, default=generate_ulid, editable=False)
    tenant_id = models.CharField(max_length=26, db_index=True)
    source_session = models.ForeignKey(TellerSession, on_delete=models.CASCADE, related_name="transfers_out")
    target_session = models.ForeignKey(TellerSession, on_delete=models.CASCADE, related_name="transfers_in", null=True, blank=True)
    amount = models.BigIntegerField()
    otp_code = models.CharField(max_length=6, blank=True)
    otp_expires_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=[("INITIATED", "Initié"), ("SENT", "Envoyé"), ("RECEIVED", "Reçu"), ("CONFIRMED", "Confirmé")],
        default="INITIATED",
        db_index=True,
    )
    initiated_by = models.CharField(max_length=26)
    confirmed_by = models.CharField(max_length=26, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["tenant_id", "status"])]
