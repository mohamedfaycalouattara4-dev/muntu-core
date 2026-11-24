"""Muntu Core — Modèles tenancy : Institution, Branch, ModuleToggle.
Isolation logique forte : un seul schéma, tenant_id partout.
"""
from __future__ import annotations
import uuid
from django.db import models
from django.utils import timezone


def generate_ulid() -> str:
    """ULID-like : timestamp millisecondes hex + random 16 chars."""
    ts = int(timezone.now().timestamp() * 1000)
    rnd = uuid.uuid4().hex[:16]
    return f"{ts:013x}{rnd}"


class InstitutionStatus(models.TextChoices):
    PENDING = "PENDING", "En cours d'onboarding"
    ACTIVE = "ACTIVE", "Opérationnelle"
    SUSPENDED = "SUSPENDED", "Suspendue"
    ARCHIVED = "ARCHIVED", "Archivée (fin de contrat)"


class CurrencyCode(models.TextChoices):
    XOF = "XOF", "Franc CFA BCEAO"
    XAF = "XAF", "Franc CFA BEAC"
    GNF = "GNF", "Franc guinéen"


class Institution(models.Model):
    """Institution financière (tenant) — racine de l'isolation multi-tenant.

    Chaque Institution possède :
    - son propre tenant_id (ULID)
    - son plan comptable
    - ses agences (Branch)
    - ses modules activés/désactivés (ModuleToggle)
    - sa configuration métier (JSONField)
    """
    id = models.CharField(max_length=26, primary_key=True, default=generate_ulid, editable=False)
    name = models.CharField(max_length=255, db_index=True)
    slug = models.SlugField(max_length=100, unique=True, db_index=True)
    status = models.CharField(
        max_length=20, choices=InstitutionStatus.choices,
        default=InstitutionStatus.PENDING, db_index=True,
    )
    country_code = models.CharField(max_length=2, db_index=True)
    registration_number = models.CharField(max_length=100, blank=True, db_index=True)
    currency = models.CharField(
        max_length=3, choices=CurrencyCode.choices,
        default=CurrencyCode.XOF, db_index=True,
        help_text="Devise principale de l'institution.",
    )
    currency_minor_unit = models.IntegerField(
        default=0,
        help_text="Nombre de décimales de la devise (0 = XOF, 2 = GNF).",
    )
    timezone = models.CharField(
        max_length=50, default="Africa/Ouagadougou",
        help_text="Fuseau horaire de l'institution.",
    )
    config = models.JSONField(default=dict, blank=True)
    onboarded_at = models.DateTimeField(null=True, blank=True)
    suspended_at = models.DateTimeField(null=True, blank=True)
    suspended_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Institution"
        verbose_name_plural = "Institutions"
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["country_code", "status"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.id})"

    def is_active(self) -> bool:
        return self.status == InstitutionStatus.ACTIVE

    def suspend(self, reason: str) -> None:
        self.status = InstitutionStatus.SUSPENDED
        self.suspended_at = timezone.now()
        self.suspended_reason = reason
        self.save(update_fields=["status", "suspended_at", "suspended_reason", "updated_at"])

    def activate(self) -> None:
        self.status = InstitutionStatus.ACTIVE
        if not self.onboarded_at:
            self.onboarded_at = timezone.now()
        self.save(update_fields=["status", "onboarded_at", "updated_at"])

    def archive(self) -> None:
        self.status = InstitutionStatus.ARCHIVED
        self.save(update_fields=["status", "updated_at"])


class Branch(models.Model):
    """Agence physique d'une institution."""
    id = models.CharField(max_length=26, primary_key=True, default=generate_ulid, editable=False)
    institution = models.ForeignKey(
        Institution, on_delete=models.CASCADE, related_name="branches",
    )
    name = models.CharField(max_length=255)
    code = models.CharField(
        max_length=20,
        help_text="Code agence (ex: 'AG01' pour l'agence principale).",
    )
    address = models.TextField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    is_hq = models.BooleanField(default=False, help_text="Agence principale (siège).")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [["institution", "code"]]
        indexes = [models.Index(fields=["institution", "is_active"])]

    def __str__(self) -> str:
        return f"{self.code} — {self.name} ({self.institution.slug})"


class ModuleToggle(models.Model):
    """Bascule d'activation d'un module par institution.

    Modules possibles :
    - savings, lending, teller, accounting, regulatory,
      claims, documents, channels, risk, compliance, audit, notifications
    """
    id = models.CharField(max_length=26, primary_key=True, default=generate_ulid, editable=False)
    institution = models.ForeignKey(
        Institution, on_delete=models.CASCADE, related_name="module_toggles",
    )
    module_name = models.CharField(max_length=50, db_index=True)
    is_enabled = models.BooleanField(default=False)
    enabled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [["institution", "module_name"]]
        ordering = ["module_name"]

    def __str__(self) -> str:
        status = "ON" if self.is_enabled else "OFF"
        return f"{self.module_name} [{status}] @ {self.institution.slug}"

    def enable(self) -> None:
        self.is_enabled = True
        self.enabled_at = timezone.now()
        self.save(update_fields=["is_enabled", "enabled_at", "updated_at"])

    def disable(self) -> None:
        self.is_enabled = False
        self.save(update_fields=["is_enabled", "updated_at"])
