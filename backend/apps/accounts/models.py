"""KALYCE · User + VendorProfile + CourierProfile + Operator (KYC / KYB).

- ULID primary key (non-guessable, time-sortable)
- Phone & email chiffrés au repos (AES-GCM via Fernet — `apps.core.security`)
- Champs de hash (phone_hash, withdrawal_phone_hash) indexés pour la recherche Idempotent
- Rôles multiples via ArrayField ; KYC status enum
"""
from __future__ import annotations

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.contrib.postgres.fields import ArrayField
from django.db import models

from apps.core.models import SoftDeleteModel, TimeStampedModel, generate_ulid
from apps.core.security import decrypt_value, encrypt_value, phone_hash


class KYCStatus(models.TextChoices):
    PENDING = "pending", "En attente"
    APPROVED = "approved", "Approuvé"
    REJECTED = "rejected", "Rejeté"
    EXPIRED = "expired", "Expiré"


class UserRole(models.TextChoices):
    BUYER = "buyer", "Acheteur"
    SELLER = "seller", "Vendeur"
    COURIER = "courier", "Livreur"
    OPERATOR = "operator", "Opérateur support"
    FINANCE = "finance", "Finance"
    COMPLIANCE = "compliance", "Compliance"
    ARBITRATOR = "arbitrator", "Arbitre litiges"
    ADMIN = "admin", "Administrateur"
    AUDITOR = "auditor", "Auditeur (lecture seule)"


class UserManager(BaseUserManager):
    def create_user(self, *, email, phone="", password=None, roles=None, **kwargs):
        if not email and not phone:
            raise ValueError("Email ou téléphone obligatoire (KYC BCEAO).")
        user = self.model(
            id=generate_ulid(),
            # `email` n'est pas une colonne : seuls email_hash / email_encrypted
            # existent en base (chiffrement au repos, recherche par hash).
            phone_hash=phone_hash(phone) if phone else "",
            phone_encrypted=encrypt_value(phone) if phone else "",
            email_hash=phone_hash(email) if email else "",
            email_encrypted=encrypt_value(email) if email else "",
            roles=roles or [UserRole.BUYER],
            **kwargs,
        )
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, *, email, password=None, **kwargs):
        kwargs.setdefault("is_staff", True)
        kwargs.setdefault("is_superuser", True)
        kwargs.setdefault("roles", [UserRole.ADMIN])
        return self.create_user(email=email, password=password, **kwargs)


class User(TimeStampedModel, AbstractBaseUser, PermissionsMixin, SoftDeleteModel):
    id = models.CharField(max_length=26, primary_key=True, default=generate_ulid, editable=False)
    email_hash = models.CharField(max_length=64, unique=True, db_index=True)
    email_encrypted = models.TextField(blank=True)
    phone_hash = models.CharField(max_length=64, blank=True, db_index=True)
    phone_encrypted = models.TextField(blank=True)
    display_name = models.CharField(max_length=100)
    roles = ArrayField(models.CharField(max_length=20, choices=UserRole.choices), default=list)
    kyc_status = models.CharField(max_length=20, choices=KYCStatus.choices, default=KYCStatus.PENDING)
    trust_score = models.SmallIntegerField(default=50)  # 0-100
    is_active = models.BooleanField(default=True)
    is_suspended = models.BooleanField(default=False)
    suspension_reason = models.TextField(blank=True)
    webauthn_credentials = models.JSONField(default=list, blank=True)
    preferred_language = models.CharField(max_length=10, default="fr")
    notification_prefs = models.JSONField(default=dict, blank=True)
    last_login_at = models.DateTimeField(null=True, blank=True)
    version = models.IntegerField(default=0)  # optimistic lock
    is_staff = models.BooleanField(default=False)

    USERNAME_FIELD = "email_hash"
    REQUIRED_FIELDS = ["display_name"]

    objects = UserManager()

    class Meta:
        indexes = [models.Index(fields=["kyc_status"])]

    def __str__(self) -> str:
        return f"{self.display_name} <{self.id}>"

    # Properties — décryptage on-demand
    @property
    def email(self) -> str:
        return decrypt_value(self.email_encrypted) if self.email_encrypted else ""

    @property
    def phone(self) -> str:
        return decrypt_value(self.phone_encrypted) if self.phone_encrypted else ""

    def has_role(self, role: str) -> bool:
        return role in (self.roles or [])

    def is_webauthn_enabled(self) -> bool:
        return bool(self.webauthn_credentials)


class VendorProfile(TimeStampedModel):
    id = models.CharField(max_length=26, primary_key=True, default=generate_ulid, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="vendor_profile")
    business_name = models.CharField(max_length=200)
    rccm_number = models.CharField(max_length=50, blank=True)
    kyb_status = models.CharField(max_length=20, choices=KYCStatus.choices, default=KYCStatus.PENDING)
    kyb_documents = models.JSONField(default=list, blank=True)
    withdrawal_phone_hash = models.CharField(max_length=64, blank=True, db_index=True)
    withdrawal_phone_encrypted = models.TextField(blank=True)
    withdrawal_aggregator = models.CharField(max_length=50, blank=True)
    trust_badge = models.BooleanField(default=False)
    reliability_score = models.DecimalField(max_digits=4, decimal_places=2, default=0)
    total_sales_count = models.IntegerField(default=0)
    total_sales_xof = models.BigIntegerField(default=0)
    dispute_rate = models.DecimalField(max_digits=5, decimal_places=4, default=0)
    available_balance_xof = models.BigIntegerField(default=0)
    held_balance_xof = models.BigIntegerField(default=0)
    commission_rate = models.DecimalField(max_digits=4, decimal_places=3, default=0.05)  # 5%
    delivery_delay_hours = models.IntegerField(default=24)
    zones = models.JSONField(default=list, blank=True)
    version = models.IntegerField(default=0)

    def __str__(self) -> str:
        return f"Vendor<{self.business_name}>"


class CourierProfile(TimeStampedModel):
    id = models.CharField(max_length=26, primary_key=True, default=generate_ulid, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="courier_profile")
    kyc_status = models.CharField(max_length=20, choices=KYCStatus.choices, default=KYCStatus.PENDING)
    vehicle_type = models.CharField(max_length=50, blank=True)
    vehicle_plate = models.CharField(max_length=20, blank=True)
    insurance_ref = models.CharField(max_length=50, blank=True)
    is_available = models.BooleanField(default=True)
    coverage_zones = models.JSONField(default=list, blank=True)
    delivery_score = models.DecimalField(max_digits=4, decimal_places=2, default=0)
    total_deliveries = models.IntegerField(default=0)
    success_rate = models.DecimalField(max_digits=5, decimal_places=4, default=0)
    available_balance_xof = models.BigIntegerField(default=0)
    withdrawal_phone_hash = models.CharField(max_length=64, blank=True, db_index=True)
    withdrawal_phone_encrypted = models.TextField(blank=True)
    current_location = models.JSONField(default=dict, blank=True)  # {lat, lng}
    version = models.IntegerField(default=0)


# ---------------------------------------------------------------------------
# Étape 3 · Identité : rôles attribués, appareils connus, sessions de rafraîchissement
# ---------------------------------------------------------------------------
class RoleAssignment(TimeStampedModel):
    """Attribution de rôle traçable, révocable et à durée limitée.

    Le tableau `User.roles` reste la vue matérialisée utilisée par les
    politiques RLS ; c'est cette table qui en est la source de vérité et qui
    répond aux questions d'audit : qui a donné ce rôle, quand, pourquoi,
    jusqu'à quand. Une élévation de privilège devient donc reconstituable.
    """

    id = models.CharField(max_length=26, primary_key=True, default=generate_ulid, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="role_assignments")
    role = models.CharField(max_length=20, choices=UserRole.choices, db_index=True)
    granted_by_id = models.CharField(max_length=26, blank=True)
    reason = models.TextField(blank=True)
    expires_at = models.DateTimeField(null=True, blank=True, db_index=True)
    revoked_at = models.DateTimeField(null=True, blank=True, db_index=True)
    revoked_by_id = models.CharField(max_length=26, blank=True)

    class Meta:
        indexes = [models.Index(fields=["user", "role"])]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "role"], condition=models.Q(revoked_at__isnull=True),
                name="uniq_active_role_per_user"),
        ]

    @property
    def is_active(self) -> bool:
        from django.utils import timezone

        if self.revoked_at is not None:
            return False
        return self.expires_at is None or self.expires_at > timezone.now()


class AuthDevice(TimeStampedModel):
    """Appareil connu d'un utilisateur (liaison de session)."""

    id = models.CharField(max_length=26, primary_key=True, default=generate_ulid, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="devices")
    #: empreinte SHA-256 (user-agent + indices client) — aucune donnée brute stockée.
    fingerprint = models.CharField(max_length=64, db_index=True)
    label = models.CharField(max_length=120, blank=True)
    last_ip_hash = models.CharField(max_length=64, blank=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)
    is_trusted = models.BooleanField(default=False)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "fingerprint"], name="uniq_device_per_user"),
        ]


class RefreshSession(TimeStampedModel):
    """Session de rafraîchissement rotative, avec détection de rejeu.

    Un jeton de rafraîchissement volé est indétectable tant qu'on se contente de
    le blacklister : le voleur l'utilise avant la victime. En chaînant les
    rotations dans une même « famille », la réutilisation d'un jeton déjà tourné
    prouve la compromission et déclenche la révocation de toute la famille.
    """

    id = models.CharField(max_length=26, primary_key=True, default=generate_ulid, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="refresh_sessions")
    family_id = models.CharField(max_length=26, db_index=True)
    #: SHA-256 du jeton : la base ne contient jamais de jeton utilisable.
    token_hash = models.CharField(max_length=64, unique=True, db_index=True)
    device = models.ForeignKey(AuthDevice, null=True, blank=True,
                               on_delete=models.SET_NULL, related_name="sessions")
    ip_hash = models.CharField(max_length=64, blank=True)
    user_agent_hash = models.CharField(max_length=64, blank=True)
    expires_at = models.DateTimeField(db_index=True)
    rotated_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True, db_index=True)
    revoked_reason = models.CharField(max_length=60, blank=True)
    replaced_by_hash = models.CharField(max_length=64, blank=True)

    class Meta:
        indexes = [models.Index(fields=["user", "revoked_at"])]

    @property
    def is_usable(self) -> bool:
        from django.utils import timezone

        return (self.revoked_at is None and self.rotated_at is None
                and self.expires_at > timezone.now())
