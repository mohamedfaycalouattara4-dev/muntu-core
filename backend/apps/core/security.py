"""Sécurité bas niveau : Fernet 256-bit, hashed OTP, HMAC, masking phone."""
from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import os
import secrets


_INSECURE_DEV_KEYS_FLAG = "KALYCE_ALLOW_INSECURE_DEV_KEYS"


def _insecure_dev_keys_allowed() -> bool:
    """Autorisation EXPLICITE et bruyante de clés dérivées (dev/tests seulement).

    P0-05 : aucune clé de repli n'est plus dérivée silencieusement. L'absence de
    `FIELD_ENCRYPTION_KEY` en production est une erreur de configuration fatale,
    pas un mode dégradé.
    """
    if os.getenv(_INSECURE_DEV_KEYS_FLAG, "").lower() in {"1", "true", "yes"}:
        return True
    # Les suites de tests s'exécutent sur le settings module dédié.
    return os.getenv("DJANGO_SETTINGS_MODULE", "").endswith(".test")


def _misconfigured(message: str):
    try:
        from django.core.exceptions import ImproperlyConfigured
    except Exception:  # pragma: no cover - Django toujours présent en runtime
        return RuntimeError(message)
    return ImproperlyConfigured(message)


def _derived_dev_key(label: str) -> bytes:
    """Clé dérivée par instance : jamais partagée, jamais publique.

    La graine provient de `KALYCE_DEV_KEY_SEED` si fournie, sinon d'une graine
    aléatoire propre au processus (les données chiffrées ne survivent donc pas
    au redémarrage, ce qui est le comportement attendu en développement).
    """
    global _DEV_KEY_SEED
    if _DEV_KEY_SEED is None:
        _DEV_KEY_SEED = os.getenv("KALYCE_DEV_KEY_SEED") or secrets.token_hex(32)
        logging.getLogger("muntu.security").critical(
            "Clés cryptographiques DEV dérivées en mémoire (%s activé). "
            "Configuration interdite hors développement.", _INSECURE_DEV_KEYS_FLAG)
    return hashlib.sha256(f"{_DEV_KEY_SEED}|{label}".encode()).digest()


_DEV_KEY_SEED: str | None = None


def _fernet_key() -> bytes:
    """Clé de chiffrement des PII — 32 octets, obligatoire hors développement."""
    raw = os.getenv("FIELD_ENCRYPTION_KEY")
    if raw:
        key = _decode_key_material(raw, "FIELD_ENCRYPTION_KEY")
        if len(key) != 32:
            raise _misconfigured(
                "FIELD_ENCRYPTION_KEY doit encoder exactement 32 octets "
                "(base64url ou hexadécimal).")
        return key
    if _insecure_dev_keys_allowed():
        return _derived_dev_key("field-encryption")
    raise _misconfigured(
        "FIELD_ENCRYPTION_KEY est absente. Le chiffrement des données "
        "personnelles ne peut pas reposer sur une clé de repli publique.")


def _decode_key_material(raw: str, name: str) -> bytes:
    raw = raw.strip()
    try:
        return bytes.fromhex(raw)
    except ValueError:
        pass
    try:
        return base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))
    except (ValueError, TypeError) as exc:
        raise _misconfigured(f"{name} n'est ni hexadécimale ni base64url.") from exc


def _signing_key(name: str) -> bytes:
    """Clé HMAC (FSM, sceau de livraison, ledger, webhooks)."""
    value = os.getenv(name)
    if value:
        key = _decode_key_material(value, name)
        if len(key) < 32:
            raise _misconfigured(f"{name} doit faire au moins 32 octets.")
        return key
    if _insecure_dev_keys_allowed():
        return _derived_dev_key(name)
    raise _misconfigured(
        f"{name} est absente : les signatures HMAC ne peuvent pas être "
        "produites avec une clé de repli déterministe et publique.")


def encrypt_value(value: str) -> str:  # AES-GCM (Fernet-like)
    if not value:
        return ""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    nonce = secrets.token_bytes(12)
    cipher = AESGCM(_fernet_key()).encrypt(nonce, value.encode("utf-8"), None)
    return base64.urlsafe_b64encode(nonce + cipher).decode("ascii")


def decrypt_value(token: str) -> str:
    if not token:
        return ""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    payload = base64.urlsafe_b64decode(token.encode("ascii"))
    nonce, cipher = payload[:12], payload[12:]
    return AESGCM(_fernet_key()).decrypt(nonce, cipher, None).decode("utf-8")


def phone_hash(value: str) -> str:
    salt = os.getenv("OTP_SALT_KEY", "kalyce-otp-default-salt")
    return hashlib.sha256(f"{salt}|{value}".encode()).hexdigest()


# ---------------------------------------------------------------------------
# OTP hashing — Argon2id (KDF résistant GPU/ASIC), sel par commande.
#
# Un OTP est un secret à très faible entropie (10^6 combinaisons) : un simple
# SHA-256 est brute-forçable en une fraction de seconde. On utilise donc
# Argon2id (déjà dépendance du projet via `argon2-cffi`) avec :
#   * un sel unique par commande (`DeliveryOtp.otp_salt`, ou le sel fourni),
#   * un poivre global tiré de `OTP_SALT_KEY` (hors base de données),
#   * une sortie 32 octets → 64 caractères hex (compatible `max_length=64`).
# ---------------------------------------------------------------------------

OTP_HASH_ALGORITHM = "argon2id"
_OTP_HASH_LEN = 32  # 32 octets -> 64 chars hex


def _argon2_params() -> tuple[int, int, int]:
    """(time_cost, memory_cost KiB, parallelism) — surchargeable par env.

    Défauts alignés sur les recommandations OWASP (19 MiB / t=2 / p=1).
    Les suites de tests abaissent ces coûts via variables d'environnement.
    """
    return (
        int(os.getenv("OTP_ARGON2_TIME_COST", "2")),
        int(os.getenv("OTP_ARGON2_MEMORY_COST", "19456")),
        int(os.getenv("OTP_ARGON2_PARALLELISM", "1")),
    )


def _otp_pepper() -> str:
    return os.getenv("OTP_SALT_KEY", "kalyce-otp-default-salt")


def generate_otp_salt() -> str:
    """Sel par commande — 32 caractères hex (`DeliveryOtp.otp_salt`)."""
    return secrets.token_hex(16)


def _otp_salt_bytes(salt: str | None) -> bytes:
    """Dérive un sel Argon2 de 16 octets à partir du sel métier + poivre."""
    material = f"{_otp_pepper()}|{salt or 'global'}"
    return hashlib.sha256(material.encode("utf-8")).digest()[:16]


def hash_otp(code: str, salt: str | None = None) -> str:
    """Hash Argon2id d'un code OTP — déterministe pour un couple (code, sel)."""
    from argon2.low_level import Type, hash_secret_raw  # noqa: PLC0415

    time_cost, memory_cost, parallelism = _argon2_params()
    raw = hash_secret_raw(
        secret=str(code).encode("utf-8"),
        salt=_otp_salt_bytes(salt),
        time_cost=time_cost,
        memory_cost=memory_cost,
        parallelism=parallelism,
        hash_len=_OTP_HASH_LEN,
        type=Type.ID,
    )
    return raw.hex()


def verify_otp(code: str, expected_hash: str, salt: str | None = None) -> bool:
    """Comparaison en temps constant d'un OTP contre son hash Argon2id."""
    if not code or not expected_hash:
        return False
    return hmac.compare_digest(hash_otp(code, salt), expected_hash)


def mask_phone(phone: str) -> str:
    if not phone or len(phone) < 4:
        return "***"
    return "*" * (len(phone) - 4) + phone[-4:]


def chain_hash(previous_hash: str, payload: str) -> str:
    """Hash chaîné SHA-256 (ledger append-only, journal d\'audit)."""
    return hashlib.sha256(f"{previous_hash}|{payload}".encode()).hexdigest()


def sign_hmac(message: str, key_name: str = "HSZ_SIGNING_KEY") -> str:
    """HMAC-SHA256 hex — utilisé pour FSM, seal, ledger, webhooks."""
    return hmac.new(_signing_key(key_name), message.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_hmac(message: str, signature: str, key_name: str = "HSZ_SIGNING_KEY") -> bool:
    expected = sign_hmac(message, key_name)
    return hmac.compare_digest(expected, signature or "")


def short_oral_code(length: int = 6) -> str:
    """Code oral court — exclut I, O, 0, 1 (ambigu)."""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def sign_delivery_seal(otp_hash: str, photo_hash: str, gps_hash: str) -> str:
    payload = f"{otp_hash}|{photo_hash}|{gps_hash}"
    return sign_hmac(payload, "HSZ_SIGNING_KEY")


def generate_xof_compatible_token() -> str:
    """Jeton idempotency-friendly (≥ 32 chars random hex)."""
    return secrets.token_hex(16)
