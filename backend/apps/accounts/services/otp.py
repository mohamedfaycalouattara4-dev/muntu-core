"""Étape 3 · OTP durci : anti-énumération et verrouillage progressif.

Deux propriétés sont recherchées, et elles sont contradictoires si l'on n'y
prend pas garde :

* **Anti-énumération** — la réponse à une demande de code ne doit jamais
  révéler si un compte existe. Le service renvoie donc toujours la même charge
  utile, la même durée de validité et, autant que possible, le même temps de
  traitement. La verbosité (« numéro inconnu ») serait un oracle d'inventaire
  du fichier client.
* **Résistance au bourrinage** — six chiffres, c'est un million de
  combinaisons : un attaquant qui peut essayer sans limite gagne. Le
  verrouillage est donc *progressif* (par paliers croissants) et porte sur le
  couple numéro + tentative, pas sur la session.

Le compteur d'échecs survit à l'expiration du code : sinon il suffirait
d'attendre cinq minutes pour repartir de zéro.
"""
from __future__ import annotations

import secrets
from dataclasses import dataclass

from django.core.cache import cache

from apps.core.security import generate_otp_salt, hash_otp, phone_hash, verify_otp

#: Durée de validité d'un code.
OTP_TTL_SECONDS = 300
#: Nombre d'essais tolérés sur un même code avant invalidation.
MAX_VERIFY_ATTEMPTS = 3
#: Intervalle minimal entre deux envois pour un même numéro.
RESEND_INTERVAL_SECONDS = 30
#: Mémoire des échecs : bien plus longue que la vie d'un code.
FAILURE_WINDOW_SECONDS = 3600
#: Paliers de verrouillage, indexés par nombre d'échecs consécutifs.
LOCK_LADDER_SECONDS: tuple[int, ...] = (0, 0, 0, 30, 120, 600, 1800, 3600)


class OtpError(Exception):
    """Erreur OTP générique — le message est volontairement indifférencié."""

    #: Code interne (journalisation/métriques), jamais renvoyé au client.
    code = "otp_invalid"
    retry_after = 0

    def __init__(self, message: str = "Code invalide ou expiré.", *,
                 code: str | None = None, retry_after: int = 0):
        super().__init__(message)
        if code:
            self.code = code
        self.retry_after = retry_after


class OtpLocked(OtpError):
    code = "otp_locked"


@dataclass(frozen=True)
class OtpIssued:
    """Résultat d'une demande de code.

    `code` vaut None lorsqu'aucun nouvel envoi n'a eu lieu (anti-flood) : la
    vue renvoie malgré tout la même réponse au client.
    """

    code: str | None
    ttl_seconds: int = OTP_TTL_SECONDS


def _pending_key(phone: str) -> str:
    return f"otp:pending:{phone_hash(phone)}"


def _failures_key(phone: str) -> str:
    return f"otp:failures:{phone_hash(phone)}"


def _lock_key(phone: str) -> str:
    return f"otp:lock:{phone_hash(phone)}"


def lock_seconds_for(failures: int) -> int:
    if failures < len(LOCK_LADDER_SECONDS):
        return LOCK_LADDER_SECONDS[failures]
    return LOCK_LADDER_SECONDS[-1]


def remaining_lock(phone: str) -> int:
    """Secondes de verrouillage restantes (0 si le numéro n'est pas verrouillé)."""
    ttl = cache.ttl(_lock_key(phone)) if hasattr(cache, "ttl") else None
    if ttl is None:
        return int(cache.get(_lock_key(phone)) or 0)
    return int(ttl or 0)


def _assert_not_locked(phone: str) -> None:
    locked_for = int(cache.get(_lock_key(phone)) or 0)
    if locked_for:
        raise OtpLocked("Trop de tentatives. Réessayez plus tard.",
                        code="otp_locked", retry_after=locked_for)


def _register_failure(phone: str) -> int:
    failures = int(cache.get(_failures_key(phone)) or 0) + 1
    cache.set(_failures_key(phone), failures, timeout=FAILURE_WINDOW_SECONDS)
    delay = lock_seconds_for(failures)
    if delay:
        cache.set(_lock_key(phone), delay, timeout=delay)
    return failures


def reset_failures(phone: str) -> None:
    cache.delete(_failures_key(phone))
    cache.delete(_lock_key(phone))


def request_otp(phone: str) -> OtpIssued:
    """Génère (ou non) un code. La réponse visible est toujours identique."""
    _assert_not_locked(phone)
    pending = cache.get(_pending_key(phone))
    if pending and pending.get("sends", 0) >= 1 and cache.get(_pending_key(phone) + ":cooldown"):
        # Renvoi trop rapproché : aucun nouveau code, mais réponse inchangée.
        return OtpIssued(code=None)

    code = f"{secrets.randbelow(1_000_000):06d}"
    salt = generate_otp_salt()
    cache.set(_pending_key(phone),
              {"code": hash_otp(code, salt), "salt": salt, "tries": 0,
               "sends": (pending or {}).get("sends", 0) + 1},
              timeout=OTP_TTL_SECONDS)
    cache.set(_pending_key(phone) + ":cooldown", 1, timeout=RESEND_INTERVAL_SECONDS)
    return OtpIssued(code=code)


def verify(phone: str, code: str) -> None:
    """Vérifie un code. Lève `OtpError` (message unique) en cas d'échec."""
    _assert_not_locked(phone)
    stored = cache.get(_pending_key(phone))
    if not stored:
        _register_failure(phone)
        raise OtpError(code="otp_missing")
    if stored["tries"] >= MAX_VERIFY_ATTEMPTS:
        cache.delete(_pending_key(phone))
        failures = _register_failure(phone)
        raise OtpLocked("Trop de tentatives. Réessayez plus tard.",
                        code="otp_locked", retry_after=lock_seconds_for(failures))
    if not verify_otp(code, stored["code"], stored.get("salt")):
        stored["tries"] += 1
        cache.set(_pending_key(phone), stored, timeout=OTP_TTL_SECONDS)
        failures = _register_failure(phone)
        delay = lock_seconds_for(failures)
        if delay:
            raise OtpLocked("Trop de tentatives. Réessayez plus tard.",
                            code="otp_locked", retry_after=delay)
        raise OtpError(code="otp_mismatch")
    cache.delete(_pending_key(phone))
    reset_failures(phone)
