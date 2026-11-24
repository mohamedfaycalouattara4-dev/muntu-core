"""MUNTU CORE · Modèles Multi-tenant (Phase 00).

Modèle Institution (Tenant) et gestion du cycle de vie des institutions clientes.
Chaque Institution est une SFD/IMF qui utilise la plateforme Muntu Core en tant que
système de core banking SaaS.
"""
from __future__ import annotations

from django.db import models
from django.utils import timezone

from apps.core.models import TimeStampedModel, generate_ulid


class InstitutionStatus(models.TextChoices):
    """Statut d'une institution dans le cycle de vie de la plateforme."""
    PENDING = "pending", "En attente d'onboarding"
    ACTIVE = "active", "Active et opérationnelle"
    SUSPENDED = "suspended", "Suspendue (violation de conformité)"
    ARCHIVED = "archived", "Archivée (fin de contrat)"


class Institution(TimeStampedModel):
    """Représentation d'une institution cliente (SFD/IMF) — le tenant root.

    Chaque institution est une entité juridique distincte avec ses propres données,
    utilisateurs, comptes financiers, et configuration. L'isolation des données est
    garantie par Row Level Security (RLS) au niveau PostgreSQL, utilisant le
    tenant_id comme clé de partitionnement.

    Attributs :
        id : Identifiant unique (ULID) de l'institution.
        name : Nom légal de l'institution (ex: "Coopérative d'Épargne Bamako").
        slug : Identifiant lisible pour les URLs et sous-domaines (ex: "coop-bamako").
        status : Statut opérationnel (PENDING, ACTIVE, SUSPENDED, ARCHIVED).
        country_code : Code ISO 3166-1 alpha-2 (ex: "ML" pour Mali).
        registration_number : Numéro d'immatriculation auprès du régulateur (BCEAO).
        config : Configuration JSON spécifique à l'institution (paramètres métier).
        onboarded_at : Timestamp du premier déploiement productif.
        suspended_at : Timestamp de la suspension (si applicable).
        suspended_reason : Motif de la suspension (si applicable).
    """

    id = models.CharField(
        max_length=26,
        primary_key=True,
        default=generate_ulid,
        editable=False,
        help_text="Identifiant unique ULID de l'institution (tenant_id)."
    )
    name = models.CharField(
        max_length=255,
        db_index=True,
        help_text="Nom légal de l'institution SFD/IMF."
    )
    slug = models.SlugField(
        max_length=100,
        unique=True,
        db_index=True,
        help_text="Identifiant lisible pour les URLs et sous-domaines (ex: 'coop-bamako')."
    )
    status = models.CharField(
        max_length=20,
        choices=InstitutionStatus.choices,
        default=InstitutionStatus.PENDING,
        db_index=True,
        help_text="Statut opérationnel de l'institution."
    )
    country_code = models.CharField(
        max_length=2,
        db_index=True,
        help_text="Code ISO 3166-1 alpha-2 (ex: 'ML' pour Mali)."
    )
    registration_number = models.CharField(
        max_length=100,
        blank=True,
        db_index=True,
        help_text="Numéro d'immatriculation auprès du régulateur (BCEAO)."
    )
    config = models.JSONField(
        default=dict,
        blank=True,
        help_text="Configuration JSON spécifique à l'institution (paramètres métier, limites, etc.)."
    )
    onboarded_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp du premier déploiement productif."
    )
    suspended_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp de la suspension (si applicable)."
    )
    suspended_reason = models.TextField(
        blank=True,
        help_text="Motif de la suspension (si applicable)."
    )

    class Meta:
        verbose_name = "Institution (Tenant)"
        verbose_name_plural = "Institutions (Tenants)"
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["country_code", "status"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.id})"

    def is_active(self) -> bool:
        """Vrai si l'institution est opérationnelle."""
        return self.status == InstitutionStatus.ACTIVE

    def suspend(self, reason: str) -> None:
        """Suspend l'institution avec un motif."""
        self.status = InstitutionStatus.SUSPENDED
        self.suspended_at = timezone.now()
        self.suspended_reason = reason
        self.save(update_fields=["status", "suspended_at", "suspended_reason", "updated_at"])

    def activate(self) -> None:
        """Active l'institution après onboarding."""
        self.status = InstitutionStatus.ACTIVE
        if not self.onboarded_at:
            self.onboarded_at = timezone.now()
        self.save(update_fields=["status", "onboarded_at", "updated_at"])

    def archive(self) -> None:
        """Archive l'institution (fin de contrat)."""
        self.status = InstitutionStatus.ARCHIVED
        self.save(update_fields=["status", "updated_at"])


class InstitutionUser(TimeStampedModel):
    """Relation many-to-many entre User et Institution avec rôle spécifique.

    Permet à un utilisateur d'avoir des rôles différents dans plusieurs institutions.
    Par exemple, un administrateur système peut avoir le rôle ADMIN dans l'institution A
    et FINANCE dans l'institution B.
    """

    ROLE_CHOICES = [
        ("admin", "Administrateur institution"),
        ("finance", "Responsable finance"),
        ("compliance", "Responsable conformité"),
        ("operator", "Opérateur guichet"),
        ("field_agent", "Agent terrain"),
        ("auditor", "Auditeur"),
    ]

    id = models.CharField(
        max_length=26,
        primary_key=True,
        default=generate_ulid,
        editable=False
    )
    institution = models.ForeignKey(
        Institution,
        on_delete=models.CASCADE,
        related_name="institution_users"
    )
    user_id = models.CharField(max_length=26, db_index=True)  # Référence à apps.accounts.User
    institution_role = models.CharField(
        max_length=50,
        choices=ROLE_CHOICES,
        help_text="Rôle de l'utilisateur au sein de cette institution."
    )
    is_primary_contact = models.BooleanField(
        default=False,
        help_text="Vrai si cet utilisateur est le contact principal de l'institution."
    )

    class Meta:
        unique_together = [["institution", "user_id"]]
        indexes = [
            models.Index(fields=["institution", "user_id"]),
            models.Index(fields=["user_id", "institution"]),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} @ {self.institution.name} ({self.institution_role})"
