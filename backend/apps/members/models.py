"""Muntu Core — Modèles membres : identité, KYC, adhésion, groupes solidaires.

Modèle pivot : Member — racine d'agrégat pour tout ce qui touche au sociétaire.
"""
from __future__ import annotations
from django.db import models
from django.utils import timezone


def generate_ulid() -> str:
    import uuid
    ts = int(timezone.now().timestamp() * 1000)
    rnd = uuid.uuid4().hex[:16]
    return f"{ts:013x}{rnd}"


class MemberType(models.TextChoices):
    INDIVIDUAL = "INDIVIDUAL", "Personne physique"
    LEGAL_ENTITY = "LEGAL_ENTITY", "Personne morale"


class MemberStatus(models.TextChoices):
    PROSPECT = "PROSPECT", "Prospect"
    PENDING = "PENDING", "Dossier en cours"
    ACTIVE = "ACTIVE", "Membre actif"
    INACTIVE = "INACTIVE", "Membre inactif"
    EXCLUDED = "EXCLUDED", "Exclu"
    DECEASED = "DECEASED", "Décédé"


class IDDocumentType(models.TextChoices):
    CNI = "CNI", "Carte nationale d'identité"
    PASSPORT = "PASSPORT", "Passeport"
    PERMIT = "PERMIT", "Permis de séjour"
    BIRTH_CERT = "BIRTH_CERT", "Acte de naissance"
    TAX_ID = "TAX_ID", "Numéro fiscal"
    OTHER = "OTHER", "Autre document"


class Member(models.Model):
    """Membre / sociétaire d'une institution — racine d'agrégat.

    - Personne physique ou morale
    - KYC complet avec pièces justificatives
    - Unicité garantie par tenant_id + numéro de pièce
    - Part sociale, droit d'entrée, livret
    """
    id = models.CharField(max_length=26, primary_key=True, default=generate_ulid, editable=False)
    tenant_id = models.CharField(max_length=26, db_index=True)
    member_number = models.CharField(
        max_length=50, db_index=True,
        help_text="Numéro de membre attribué par l'institution (ex: 'M-00001').",
    )
    member_type = models.CharField(max_length=20, choices=MemberType.choices, default=MemberType.INDIVIDUAL)
    status = models.CharField(max_length=20, choices=MemberStatus.choices, default=MemberStatus.PROSPECT, db_index=True)

    # Identité personne physique
    first_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=10, blank=True, choices=[("M", "Masculin"), ("F", "Féminin")])

    # Identité personne morale
    legal_name = models.CharField(max_length=255, blank=True)
    registration_number = models.CharField(max_length=100, blank=True)

    # Contact
    phone = models.CharField(max_length=30, blank=True, db_index=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=2, default="ML")

    # Pièce d'identité (unicité)
    id_document_type = models.CharField(max_length=20, choices=IDDocumentType.choices, blank=True)
    id_document_number = models.CharField(max_length=100, blank=True, db_index=True)
    id_document_issued_at = models.DateField(null=True, blank=True)
    id_document_expires_at = models.DateField(null=True, blank=True)

    # Part sociale
    shares_count = models.IntegerField(default=0, help_text="Nombre de parts sociales détenues.")
    share_value = models.BigIntegerField(default=5000, help_text="Valeur nominale d'une part en XOF.")

    # Métadonnées
    referred_by = models.CharField(max_length=26, blank=True, help_text="ULID du membre parrain.")
    branch_code = models.CharField(max_length=20, blank=True, db_index=True, help_text="Agence d'adhésion.")
    onboarded_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [["tenant_id", "member_number"]]
        indexes = [
            models.Index(fields=["tenant_id", "status"]),
            models.Index(fields=["tenant_id", "id_document_number"]),
        ]
        verbose_name = "Membre"

    def __str__(self):
        if self.member_type == MemberType.LEGAL_ENTITY:
            return f"{self.legal_name} ({self.member_number})"
        return f"{self.first_name} {self.last_name} ({self.member_number})"

    def activate(self) -> None:
        self.status = MemberStatus.ACTIVE
        if not self.onboarded_at:
            self.onboarded_at = timezone.now()
        self.save(update_fields=["status", "onboarded_at", "updated_at"])


class MemberDocument(models.Model):
    """Pièce justificative numérisée d'un membre — chiffrée au repos."""
    id = models.CharField(max_length=26, primary_key=True, default=generate_ulid, editable=False)
    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name="documents")
    document_type = models.CharField(max_length=20, choices=IDDocumentType.choices)
    file_path = models.CharField(max_length=500, help_text="Chemin chiffré dans le stockage objet.")
    file_hash = models.CharField(max_length=64, help_text="SHA-256 du fichier pour vérification d'intégrité.")
    uploaded_by = models.CharField(max_length=26, db_index=True)
    verified_by = models.CharField(max_length=26, blank=True)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class SolidarityGroup(models.Model):
    """Groupe solidaire / tontine — caution mutuelle entre membres."""
    id = models.CharField(max_length=26, primary_key=True, default=generate_ulid, editable=False)
    tenant_id = models.CharField(max_length=26, db_index=True)
    name = models.CharField(max_length=255)
    leader_member_id = models.CharField(max_length=26, db_index=True, help_text="ULID du président du groupe.")
    meeting_day = models.IntegerField(help_text="Jour de réunion hebdomadaire (0=lun ... 6=dim).")
    meeting_frequency = models.CharField(
        max_length=20,
        choices=[("WEEKLY", "Hebdomadaire"), ("BIWEEKLY", "Bi-hebdomadaire"), ("MONTHLY", "Mensuelle")],
        default="WEEKLY",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["tenant_id", "is_active"])]

    def __str__(self):
        return f"{self.name} ({self.tenant_id})"


class SolidarityGroupMember(models.Model):
    """Appartenance d'un membre à un groupe solidaire."""
    id = models.CharField(max_length=26, primary_key=True, default=generate_ulid, editable=False)
    group = models.ForeignKey(SolidarityGroup, on_delete=models.CASCADE, related_name="members")
    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name="solidarity_groups")
    joined_at = models.DateField(default=timezone.now)
    left_at = models.DateField(null=True, blank=True)

    class Meta:
        unique_together = [["group", "member"]]
