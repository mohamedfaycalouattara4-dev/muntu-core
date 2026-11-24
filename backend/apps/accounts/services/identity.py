"""Étape 3 · Services d'identité : rôles effectifs, appareils, sessions rotatives.

Règles appliquées :
  * un jeton de rafraîchissement n'est jamais stocké en clair (SHA-256) ;
  * chaque rafraîchissement tourne le jeton et invalide le précédent ;
  * rejouer un jeton déjà tourné révoque toute la famille et écrit une trace
    d'audit de sécurité (signal de compromission, pas simple erreur) ;
  * la déconnexion révoque la famille entière, pas seulement un jeton.
"""
from __future__ import annotations

import hashlib

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import AuthDevice, RefreshSession, RoleAssignment, User
from apps.core.models import generate_ulid
from apps.core.services.audit import emit

REUSE_REASON = "refresh_reuse_detected"


def sha256(value: str) -> str:
    return hashlib.sha256((value or "").encode("utf-8")).hexdigest()


def client_fingerprint(request) -> tuple[str, str, str]:
    """Retourne (empreinte appareil, hash IP, hash user-agent) — sans PII brute."""
    user_agent = request.META.get("HTTP_USER_AGENT", "")
    hint = request.headers.get("X-Device-Id", "")
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    ip = (forwarded.split(",")[0].strip() if forwarded
          else request.META.get("REMOTE_ADDR", ""))
    return sha256(f"{user_agent}|{hint}"), sha256(ip), sha256(user_agent)


def effective_roles(user: User) -> list[str]:
    """Rôles réellement actifs = attributions non révoquées et non expirées.

    En l'absence d'attribution (comptes historiques), on retombe sur le tableau
    `roles` afin de ne jamais retirer un accès par effet de bord de migration.
    """
    now = timezone.now()
    assigned = {
        a.role for a in user.role_assignments.filter(revoked_at__isnull=True)
        if a.expires_at is None or a.expires_at > now
    }
    return sorted(assigned) if assigned else sorted(set(user.roles or []))


def grant_role(user: User, role: str, *, granted_by_id: str = "", reason: str = "",
               expires_at=None) -> RoleAssignment:
    with transaction.atomic():
        assignment, _ = RoleAssignment.objects.update_or_create(
            user=user, role=role, revoked_at=None,
            defaults={"granted_by_id": granted_by_id, "reason": reason,
                      "expires_at": expires_at})
        user.roles = sorted(set(user.roles or []) | {role})
        user.save(update_fields=["roles"])
    emit("user", str(user.id), "role_granted",
         {"role": role, "granted_by": granted_by_id, "reason": reason})
    return assignment


def revoke_role(user: User, role: str, *, revoked_by_id: str = "") -> int:
    now = timezone.now()
    with transaction.atomic():
        count = RoleAssignment.objects.filter(
            user=user, role=role, revoked_at__isnull=True
        ).update(revoked_at=now, revoked_by_id=revoked_by_id)
        user.roles = sorted(set(user.roles or []) - {role})
        user.save(update_fields=["roles"])
    emit("user", str(user.id), "role_revoked",
         {"role": role, "revoked_by": revoked_by_id})
    return count


def _register_device(user: User, fingerprint: str, ip_hash: str, request) -> AuthDevice:
    device, _ = AuthDevice.objects.update_or_create(
        user=user, fingerprint=fingerprint,
        defaults={"last_ip_hash": ip_hash, "last_seen_at": timezone.now(),
                  "label": (request.META.get("HTTP_USER_AGENT", "")[:120] or "inconnu")})
    return device


def issue_session(user: User, request, *, family_id: str | None = None,
                  device: AuthDevice | None = None) -> dict:
    """Émet un couple access/refresh et enregistre la session correspondante."""
    fingerprint, ip_hash, ua_hash = client_fingerprint(request)
    device = device or _register_device(user, fingerprint, ip_hash, request)
    refresh = RefreshToken.for_user(user)
    roles = effective_roles(user)
    family = family_id or generate_ulid()
    refresh["roles"] = roles
    refresh["family"] = family
    refresh["device"] = device.id
    access = refresh.access_token
    access["roles"] = roles
    access["family"] = family
    access["device"] = device.id

    RefreshSession.objects.create(
        user=user, family_id=family, token_hash=sha256(str(refresh)), device=device,
        ip_hash=ip_hash, user_agent_hash=ua_hash,
        expires_at=timezone.now() + settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"])
    user.last_login_at = timezone.now()
    user.save(update_fields=["last_login_at"])
    return {"access": str(access), "refresh": str(refresh),
            "roles": roles, "device_id": device.id, "family_id": family}


class RefreshReuseDetected(Exception):
    """Un jeton déjà tourné a été rejoué : la famille est compromise."""


class RefreshRejected(Exception):
    """Jeton inconnu, expiré ou révoqué."""


def revoke_family(family_id: str, *, reason: str) -> int:
    return RefreshSession.objects.filter(
        family_id=family_id, revoked_at__isnull=True
    ).update(revoked_at=timezone.now(), revoked_reason=reason)


def revoke_all_sessions(user: User, *, reason: str = "logout_all") -> int:
    return RefreshSession.objects.filter(
        user=user, revoked_at__isnull=True
    ).update(revoked_at=timezone.now(), revoked_reason=reason)


def rotate_session(raw_refresh: str, request) -> dict:
    """Valide, tourne et ré-émet une session. Détecte le rejeu."""
    token_hash = sha256(raw_refresh)
    # Le rejeu est traité AVANT et HORS de la transaction de rotation : une
    # révocation décidée puis annulée par le rollback de l'exception laisserait
    # vivre la famille compromise — exactement ce que l'on veut empêcher.
    compromised = (RefreshSession.objects
                   .filter(token_hash=token_hash)
                   .exclude(rotated_at__isnull=True, revoked_at__isnull=True)
                   .first())
    if compromised is not None:
        revoke_family(compromised.family_id, reason=REUSE_REASON)
        emit("security", str(compromised.user_id), "refresh_token_reuse",
             {"family_id": compromised.family_id, "session_id": compromised.id})
        raise RefreshReuseDetected(
            "Jeton déjà utilisé : toutes les sessions liées ont été révoquées.")

    with transaction.atomic():
        session = (RefreshSession.objects.select_for_update()
                   .filter(token_hash=token_hash).first())
        if session is None:
            raise RefreshRejected("Jeton de rafraîchissement inconnu.")
        if session.rotated_at is not None or session.revoked_at is not None:
            raise RefreshReuseDetected(
                "Jeton déjà utilisé : toutes les sessions liées ont été révoquées.")
        if session.expires_at <= timezone.now():
            raise RefreshRejected("Session expirée.")

        try:
            token = RefreshToken(raw_refresh)
            token.blacklist()
        except Exception as exc:  # noqa: BLE001 - jeton cryptographiquement invalide
            raise RefreshRejected("Jeton invalide.") from exc

        issued = issue_session(session.user, request, family_id=session.family_id,
                               device=session.device)
        session.rotated_at = timezone.now()
        session.replaced_by_hash = sha256(issued["refresh"])
        session.save(update_fields=["rotated_at", "replaced_by_hash"])
    return issued


def logout(raw_refresh: str, *, user: User | None = None) -> int:
    """Déconnexion : révoque la famille du jeton présenté.

    Si le jeton est absent ou inconnu (client qui l'a déjà perdu), on révoque
    toutes les sessions de l'utilisateur authentifié : mieux vaut déconnecter
    trop que laisser vivre un jeton dont l'utilisateur pense s'être défait.
    """
    session = None
    if raw_refresh:
        session = RefreshSession.objects.filter(token_hash=sha256(raw_refresh)).first()
    if session is None:
        return revoke_all_sessions(user, reason="logout") if user is not None else 0
    if user is not None and str(session.user_id) != str(user.id):
        # Un jeton d'autrui : on ne révoque rien, mais on trace.
        emit("security", str(user.id), "logout_foreign_token",
             {"family_id": session.family_id})
        return 0
    revoked = revoke_family(session.family_id, reason="logout")
    emit("user", str(session.user_id), "logout", {"family_id": session.family_id})
    return revoked
