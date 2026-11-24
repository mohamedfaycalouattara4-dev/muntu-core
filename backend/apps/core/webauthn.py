"""FIDO2 / WebAuthn — vérification réelle d'assertions (corrige P0-03).

Ce module remplace le « stub » historique qui se contentait de constater la
présence d'un en-tête non vide. Il implémente la vérification cryptographique
complète d'une assertion WebAuthn (`navigator.credentials.get`) :

1. décodage du `clientDataJSON` et contrôle de `type`, `challenge`, `origin` ;
2. contrôle du `rpIdHash` contenu dans `authenticatorData` ;
3. contrôle des drapeaux `UP` (user present) et, si exigé, `UV` (user verified) ;
4. contrôle du compteur anti-clonage (`signCount` strictement croissant) ;
5. vérification de la signature `authenticatorData || SHA256(clientDataJSON)`
   avec la clé publique COSE enregistrée (ES256 / RS256 / EdDSA).

Aucune dépendance supplémentaire : le décodage CBOR nécessaire aux clés COSE et
aux objets d'attestation est implémenté ici (sous-ensemble strict et borné).
"""
from __future__ import annotations

import base64
import hashlib
import json
import secrets
import struct
from dataclasses import dataclass
from typing import Any

from django.conf import settings
from django.core.cache import cache

CHALLENGE_TTL_SECONDS = 300
FLAG_USER_PRESENT = 0x01
FLAG_USER_VERIFIED = 0x04
FLAG_ATTESTED_CREDENTIAL_DATA = 0x40


class WebAuthnError(Exception):
    """Échec de vérification d'une cérémonie WebAuthn."""


# ---------------------------------------------------------------------------
# Encodage base64url
# ---------------------------------------------------------------------------
def b64url_decode(value: str | bytes) -> bytes:
    if isinstance(value, bytes):
        value = value.decode("ascii")
    padding = "=" * (-len(value) % 4)
    try:
        return base64.urlsafe_b64decode(value + padding)
    except Exception as exc:  # noqa: BLE001
        raise WebAuthnError("Encodage base64url invalide.") from exc


def b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


# ---------------------------------------------------------------------------
# Décodeur CBOR minimal (types majeurs 0-5 et 7) — suffisant pour COSE/attestation
# ---------------------------------------------------------------------------
def _cbor_load(data: bytes, offset: int = 0) -> tuple[Any, int]:
    if offset >= len(data):
        raise WebAuthnError("CBOR tronqué.")
    initial = data[offset]
    major, info = initial >> 5, initial & 0x1F
    offset += 1

    if info < 24:
        value = info
    elif info == 24:
        value, offset = data[offset], offset + 1
    elif info == 25:
        value, offset = struct.unpack_from(">H", data, offset)[0], offset + 2
    elif info == 26:
        value, offset = struct.unpack_from(">I", data, offset)[0], offset + 4
    elif info == 27:
        value, offset = struct.unpack_from(">Q", data, offset)[0], offset + 8
    else:
        raise WebAuthnError("CBOR: longueur indéterminée non supportée.")

    if major == 0:
        return value, offset
    if major == 1:
        return -1 - value, offset
    if major == 2:
        end = offset + value
        if end > len(data):
            raise WebAuthnError("CBOR tronqué (bytes).")
        return data[offset:end], end
    if major == 3:
        end = offset + value
        if end > len(data):
            raise WebAuthnError("CBOR tronqué (texte).")
        return data[offset:end].decode("utf-8", "strict"), end
    if major == 4:
        items = []
        for _ in range(value):
            item, offset = _cbor_load(data, offset)
            items.append(item)
        return items, offset
    if major == 5:
        mapping: dict[Any, Any] = {}
        for _ in range(value):
            key, offset = _cbor_load(data, offset)
            val, offset = _cbor_load(data, offset)
            mapping[key] = val
        return mapping, offset
    if major == 7:
        if info == 20:
            return False, offset
        if info == 21:
            return True, offset
        if info == 22:
            return None, offset
        raise WebAuthnError("CBOR: valeur simple non supportée.")
    raise WebAuthnError("CBOR: type majeur non supporté.")


def cbor_decode(data: bytes) -> Any:
    value, _ = _cbor_load(data, 0)
    return value


# ---------------------------------------------------------------------------
# Clés publiques COSE
# ---------------------------------------------------------------------------
COSE_KTY, COSE_ALG, COSE_CRV, COSE_X, COSE_Y, COSE_N, COSE_E = 1, 3, -1, -2, -3, -1, -2

ALG_ES256 = -7
ALG_EDDSA = -8
ALG_RS256 = -257
SUPPORTED_ALGORITHMS = (ALG_ES256, ALG_EDDSA, ALG_RS256)


def _load_cose_public_key(cose: dict[int, Any]):
    from cryptography.hazmat.primitives.asymmetric import ec, ed25519, rsa
    from cryptography.hazmat.primitives.asymmetric.utils import (  # noqa: F401
        encode_dss_signature,
    )

    kty = cose.get(COSE_KTY)
    alg = cose.get(COSE_ALG)
    if alg not in SUPPORTED_ALGORITHMS:
        raise WebAuthnError(f"Algorithme COSE non autorisé : {alg}.")

    if kty == 2:  # EC2 / P-256
        x, y = cose.get(COSE_X), cose.get(COSE_Y)
        if not isinstance(x, bytes) or not isinstance(y, bytes):
            raise WebAuthnError("Clé EC2 malformée.")
        numbers = ec.EllipticCurvePublicNumbers(
            int.from_bytes(x, "big"), int.from_bytes(y, "big"), ec.SECP256R1()
        )
        return alg, numbers.public_key()
    if kty == 3:  # RSA
        n, e = cose.get(COSE_N), cose.get(COSE_E)
        if not isinstance(n, bytes) or not isinstance(e, bytes):
            raise WebAuthnError("Clé RSA malformée.")
        numbers = rsa.RSAPublicNumbers(
            int.from_bytes(e, "big"), int.from_bytes(n, "big")
        )
        return alg, numbers.public_key()
    if kty == 1:  # OKP / Ed25519
        x = cose.get(-2)
        if not isinstance(x, bytes):
            raise WebAuthnError("Clé OKP malformée.")
        return alg, ed25519.Ed25519PublicKey.from_public_bytes(x)
    raise WebAuthnError(f"Type de clé COSE non supporté : {kty}.")


def _verify_signature(alg: int, public_key, signature: bytes, message: bytes) -> None:
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec, padding

    try:
        if alg == ALG_ES256:
            public_key.verify(signature, message, ec.ECDSA(hashes.SHA256()))
        elif alg == ALG_RS256:
            public_key.verify(signature, message, padding.PKCS1v15(), hashes.SHA256())
        elif alg == ALG_EDDSA:
            public_key.verify(signature, message)
        else:  # pragma: no cover - filtré en amont
            raise WebAuthnError("Algorithme non supporté.")
    except InvalidSignature as exc:
        raise WebAuthnError("Signature WebAuthn invalide.") from exc


# ---------------------------------------------------------------------------
# Configuration Relying Party
# ---------------------------------------------------------------------------
def rp_id() -> str:
    return getattr(settings, "WEBAUTHN_RP_ID", "localhost")


def allowed_origins() -> list[str]:
    origins = getattr(settings, "WEBAUTHN_ALLOWED_ORIGINS", None)
    if origins:
        return list(origins)
    return [f"https://{rp_id()}"]


# ---------------------------------------------------------------------------
# Défis liés à l'opération (challenge binding)
# ---------------------------------------------------------------------------
def operation_challenge_key(user_id: str, operation: str) -> str:
    return f"webauthn:challenge:{user_id}:{hashlib.sha256(operation.encode()).hexdigest()}"


def issue_challenge(*, user_id: str, operation: str) -> str:
    """Émet un défi à usage unique, lié à un utilisateur ET à une opération."""
    challenge = b64url_encode(secrets.token_bytes(32))
    cache.set(operation_challenge_key(user_id, operation), challenge,
              timeout=CHALLENGE_TTL_SECONDS)
    return challenge


def consume_challenge(*, user_id: str, operation: str) -> str:
    key = operation_challenge_key(user_id, operation)
    challenge = cache.get(key)
    if not challenge:
        raise WebAuthnError("Défi WebAuthn absent ou expiré.")
    cache.delete(key)
    return challenge


# ---------------------------------------------------------------------------
# authenticatorData
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class AuthenticatorData:
    rp_id_hash: bytes
    flags: int
    sign_count: int
    credential_id: bytes | None
    credential_public_key: dict[int, Any] | None

    @property
    def user_present(self) -> bool:
        return bool(self.flags & FLAG_USER_PRESENT)

    @property
    def user_verified(self) -> bool:
        return bool(self.flags & FLAG_USER_VERIFIED)


def parse_authenticator_data(data: bytes) -> AuthenticatorData:
    if len(data) < 37:
        raise WebAuthnError("authenticatorData trop court.")
    rp_hash, flags, sign_count = data[:32], data[32], struct.unpack(">I", data[33:37])[0]
    credential_id = None
    credential_key = None
    if flags & FLAG_ATTESTED_CREDENTIAL_DATA:
        if len(data) < 55:
            raise WebAuthnError("attestedCredentialData tronqué.")
        cred_len = struct.unpack(">H", data[53:55])[0]
        credential_id = data[55:55 + cred_len]
        if len(credential_id) != cred_len:
            raise WebAuthnError("credentialId tronqué.")
        credential_key = cbor_decode(data[55 + cred_len:])
        if not isinstance(credential_key, dict):
            raise WebAuthnError("Clé publique COSE illisible.")
    return AuthenticatorData(rp_hash, flags, sign_count, credential_id, credential_key)


def _check_client_data(raw: bytes, *, expected_type: str, expected_challenge: str) -> None:
    try:
        client_data = json.loads(raw.decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise WebAuthnError("clientDataJSON illisible.") from exc
    if client_data.get("type") != expected_type:
        raise WebAuthnError("Type de cérémonie WebAuthn inattendu.")
    challenge = client_data.get("challenge", "")
    # Comparaison en temps constant sur les octets décodés.
    if not secrets.compare_digest(b64url_decode(challenge), b64url_decode(expected_challenge)):
        raise WebAuthnError("Défi WebAuthn non concordant (rejeu ou opération différente).")
    if client_data.get("origin") not in allowed_origins():
        raise WebAuthnError("Origine WebAuthn non autorisée.")
    if client_data.get("crossOrigin") is True:
        raise WebAuthnError("Cérémonie cross-origin refusée.")


# ---------------------------------------------------------------------------
# Enregistrement (navigator.credentials.create)
# ---------------------------------------------------------------------------
#: Nombre maximal de clés FIDO2 par compte (une clé perdue ne doit pas
#: enfermer l'utilisateur dehors ; un nombre illimité rendrait la révocation
#: incontrôlable).
MAX_CREDENTIALS_PER_USER = 5


def register_credential(*, user, credential: dict[str, Any], expected_challenge: str,
                        label: str = "") -> dict:
    response = credential.get("response") or {}
    client_data_raw = b64url_decode(response.get("clientDataJSON", ""))
    _check_client_data(client_data_raw, expected_type="webauthn.create",
                       expected_challenge=expected_challenge)

    attestation = cbor_decode(b64url_decode(response.get("attestationObject", "")))
    if not isinstance(attestation, dict) or "authData" not in attestation:
        raise WebAuthnError("attestationObject invalide.")
    auth_data = parse_authenticator_data(attestation["authData"])

    if not secrets.compare_digest(auth_data.rp_id_hash, hashlib.sha256(rp_id().encode()).digest()):
        raise WebAuthnError("rpIdHash non concordant.")
    if not auth_data.user_present:
        raise WebAuthnError("Présence utilisateur non attestée.")
    if not auth_data.user_verified:
        raise WebAuthnError("Vérification utilisateur (PIN/biométrie) requise.")
    if not auth_data.credential_id or not auth_data.credential_public_key:
        raise WebAuthnError("Aucune clé publique attestée.")

    alg, _ = _load_cose_public_key(auth_data.credential_public_key)
    encoded_id = b64url_encode(auth_data.credential_id)
    existing = list(user.webauthn_credentials or [])
    known = next((c for c in existing if c.get("credential_id") == encoded_id), None)
    if known is None and len(existing) >= MAX_CREDENTIALS_PER_USER:
        raise WebAuthnError(
            f"Nombre maximal de clés atteint ({MAX_CREDENTIALS_PER_USER}). "
            "Révoquez une clé avant d'en enregistrer une nouvelle.")

    record = {
        "credential_id": encoded_id,
        "public_key_cose": b64url_encode(_reencode_cose(auth_data.credential_public_key)),
        "algorithm": alg,
        "sign_count": auth_data.sign_count,
        "label": (label or (known or {}).get("label") or "")[:60],
        "registered_at": _now_iso(),
    }
    credentials = [c for c in existing if c.get("credential_id") != encoded_id]
    credentials.append(record)
    user.webauthn_credentials = credentials
    user.save(update_fields=["webauthn_credentials", "updated_at"])
    return record


def _now_iso() -> str:
    from django.utils import timezone

    return timezone.now().isoformat()


def list_credentials(user) -> list[dict]:
    """Vue publique des clés : jamais la clé publique brute ni le compteur."""
    return [{"credential_id": c.get("credential_id"),
             "label": c.get("label", ""),
             "algorithm": c.get("algorithm"),
             "registered_at": c.get("registered_at", ""),
             "last_used_at": c.get("last_used_at", "")}
            for c in (user.webauthn_credentials or [])]


def revoke_credential(user, credential_id: str) -> bool:
    """Retire une clé. Refuse de retirer la dernière si l'utilisateur en dépend.

    Un compte back-office sans clé retomberait sur l'OTP seul pour des
    opérations financières : la révocation de la dernière clé est donc un acte
    d'administration, pas un geste de confort.
    """
    credentials = list(user.webauthn_credentials or [])
    remaining = [c for c in credentials if c.get("credential_id") != credential_id]
    if len(remaining) == len(credentials):
        return False
    if not remaining and _requires_webauthn(user):
        raise WebAuthnError(
            "Impossible de révoquer la dernière clé d'un compte à privilèges. "
            "Enregistrez une clé de remplacement d'abord.")
    user.webauthn_credentials = remaining
    user.save(update_fields=["webauthn_credentials", "updated_at"])
    return True


#: Rôles pour lesquels au moins une clé FIDO2 doit rester enregistrée.
PRIVILEGED_ROLES = frozenset({"admin", "finance", "compliance", "arbitrator", "operator"})


def _requires_webauthn(user) -> bool:
    return bool(set(getattr(user, "roles", None) or []) & PRIVILEGED_ROLES)



def _reencode_cose(cose: dict[int, Any]) -> bytes:
    """Ré-encode une clé COSE en CBOR canonique minimal (clés entières)."""
    def enc_head(major: int, length: int) -> bytes:
        if length < 24:
            return bytes([(major << 5) | length])
        if length < 256:
            return bytes([(major << 5) | 24, length])
        if length < 65536:
            return bytes([(major << 5) | 25]) + struct.pack(">H", length)
        return bytes([(major << 5) | 26]) + struct.pack(">I", length)

    def enc(value: Any) -> bytes:
        if isinstance(value, bool):
            raise WebAuthnError("Valeur COSE non supportée.")
        if isinstance(value, int):
            return enc_head(0, value) if value >= 0 else enc_head(1, -1 - value)
        if isinstance(value, bytes):
            return enc_head(2, len(value)) + value
        if isinstance(value, str):
            raw = value.encode()
            return enc_head(3, len(raw)) + raw
        raise WebAuthnError("Valeur COSE non supportée.")

    items = sorted(cose.items(), key=lambda kv: (0 if kv[0] >= 0 else 1, abs(kv[0])))
    body = b"".join(enc(k) + enc(v) for k, v in items)
    return enc_head(5, len(items)) + body


# ---------------------------------------------------------------------------
# Assertion (navigator.credentials.get)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class VerifiedAssertion:
    user_id: str
    credential_id: str
    sign_count: int
    user_verified: bool


def verify_assertion(*, user, assertion: dict[str, Any], expected_challenge: str,
                     require_user_verification: bool = True) -> VerifiedAssertion:
    """Vérifie une assertion FIDO2 et met à jour le compteur anti-clonage."""
    credential_id = assertion.get("id") or assertion.get("credential_id")
    if not credential_id:
        raise WebAuthnError("Identifiant de clé absent de l'assertion.")

    stored = next((c for c in (user.webauthn_credentials or [])
                   if c.get("credential_id") == credential_id), None)
    if stored is None:
        raise WebAuthnError("Clé WebAuthn inconnue pour cet utilisateur.")

    response = assertion.get("response") or {}
    client_data_raw = b64url_decode(response.get("clientDataJSON", ""))
    authenticator_data_raw = b64url_decode(response.get("authenticatorData", ""))
    signature = b64url_decode(response.get("signature", ""))

    _check_client_data(client_data_raw, expected_type="webauthn.get",
                       expected_challenge=expected_challenge)

    auth_data = parse_authenticator_data(authenticator_data_raw)
    if not secrets.compare_digest(auth_data.rp_id_hash, hashlib.sha256(rp_id().encode()).digest()):
        raise WebAuthnError("rpIdHash non concordant.")
    if not auth_data.user_present:
        raise WebAuthnError("Présence utilisateur non attestée.")
    if require_user_verification and not auth_data.user_verified:
        raise WebAuthnError("Vérification utilisateur (PIN/biométrie) requise.")

    cose = cbor_decode(b64url_decode(stored["public_key_cose"]))
    alg, public_key = _load_cose_public_key(cose)
    message = authenticator_data_raw + hashlib.sha256(client_data_raw).digest()
    _verify_signature(alg, public_key, signature, message)

    previous = int(stored.get("sign_count", 0))
    if auth_data.sign_count or previous:
        if auth_data.sign_count <= previous:
            raise WebAuthnError("Compteur d'authentificateur non croissant (clone suspecté).")
    stored["sign_count"] = auth_data.sign_count
    stored["last_used_at"] = _now_iso()
    user.save(update_fields=["webauthn_credentials", "updated_at"])


    return VerifiedAssertion(user_id=str(user.id), credential_id=credential_id,
                             sign_count=auth_data.sign_count,
                             user_verified=auth_data.user_verified)


def verify_assertion_for_user_id(*, user_id: str, assertion: dict[str, Any],
                                 operation: str,
                                 require_user_verification: bool = True) -> VerifiedAssertion:
    """Vérifie une assertion en résolvant l'utilisateur et son défi d'opération."""
    from django.contrib.auth import get_user_model

    user = get_user_model().objects.filter(pk=user_id, is_active=True,
                                           is_suspended=False).first()
    if user is None:
        raise WebAuthnError("Signataire inconnu ou suspendu.")
    challenge = consume_challenge(user_id=str(user.id), operation=operation)
    verified = verify_assertion(user=user, assertion=assertion,
                                expected_challenge=challenge,
                                require_user_verification=require_user_verification)
    return verified
