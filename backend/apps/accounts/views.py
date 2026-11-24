"""Accounts · views : OTP durci, WebAuthn multi-clés, sessions rotatives.

Étape 3 — les services d'identité (`apps.accounts.services.identity`) sont ici
branchés sur le transport HTTP : rotation de jeton, révocation de famille,
inventaire des sessions, step-up financier.
"""
from __future__ import annotations

from django.conf import settings
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import (
    STEP_UP_TTL,
    WEBAUTHN_SESSION_TTL,
    mark_webauthn_verified,
)
from apps.core.security import phone_hash
from apps.core.throttling import OtpRequestThrottle, OtpVerifyThrottle, RefreshThrottle
from apps.core.webauthn import (
    SUPPORTED_ALGORITHMS,
    WebAuthnError,
    b64url_encode,
    consume_challenge,
    issue_challenge,
    list_credentials,
    register_credential,
    revoke_credential,
    rp_id,
    verify_assertion,
)

from .models import RefreshSession, User
from .serializers import (
    OTPSerializer,
    OTPVerifySerializer,
    RefreshSerializer,
    SessionSerializer,
    UserSerializer,
)
from .services import identity, otp as otp_service

REGISTER_OPERATION = "webauthn.register"
LOGIN_OPERATION = "webauthn.stepup"
#: Opération d'élévation exigée avant tout mouvement de fonds sensible.
FINANCIAL_OPERATION = "financial.stepup"

#: Réponse unique à toute demande d'OTP — aucun oracle d'existence de compte.
OTP_GENERIC_RESPONSE = {"status": "otp-sent", "ttl_seconds": otp_service.OTP_TTL_SECONDS}
#: Message unique à tout échec de vérification.
OTP_GENERIC_FAILURE = "Code invalide ou expiré."


class OTPRequestView(APIView):
    """`POST /api/v1/auth/otp/request/` — réponse constante, débit limité."""

    permission_classes = [AllowAny]
    throttle_classes = [OtpRequestThrottle]

    def post(self, request):
        s = OTPSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        phone = s.validated_data["phone"]
        try:
            issued = otp_service.request_otp(phone)
        except otp_service.OtpError as exc:
            # Même verrouillé, le corps reste identique : seul l'en-tête
            # Retry-After trahit l'attente, et il ne dépend pas du compte.
            response = Response(OTP_GENERIC_RESPONSE, status=status.HTTP_429_TOO_MANY_REQUESTS)
            response["Retry-After"] = str(exc.retry_after)
            return response
        if issued.code and settings.DEBUG:
            from logging import getLogger

            getLogger("muntu.accounts.dev").info("OTP for %s = %s", phone, issued.code)
        return Response(OTP_GENERIC_RESPONSE)


class OTPVerifyView(APIView):
    """`POST /api/v1/auth/otp/verify/` — ouvre une session rotative."""

    permission_classes = [AllowAny]
    throttle_classes = [OtpVerifyThrottle]

    def post(self, request):
        s = OTPVerifySerializer(data=request.data)
        s.is_valid(raise_exception=True)
        phone = s.validated_data["phone"]
        try:
            otp_service.verify(phone, s.validated_data["code"])
        except otp_service.OtpLocked as exc:
            response = Response({"detail": OTP_GENERIC_FAILURE},
                                status=status.HTTP_429_TOO_MANY_REQUESTS)
            response["Retry-After"] = str(exc.retry_after)
            return response
        except otp_service.OtpError:
            return Response({"detail": OTP_GENERIC_FAILURE},
                            status=status.HTTP_401_UNAUTHORIZED)

        user, _created = User.objects.get_or_create(
            phone_hash=phone_hash(phone),
            defaults={"display_name": phone[-4:], "phone_encrypted": phone,
                      "roles": ["buyer"]},
        )
        issued = identity.issue_session(user, request)
        return Response({
            "access": issued["access"],
            "refresh": issued["refresh"],
            "roles": issued["roles"],
            "device_id": issued["device_id"],
            "user": UserSerializer(user).data,
        })


class RefreshView(APIView):
    """`POST /api/v1/auth/refresh/` — rotation stricte, détection de rejeu."""
    throttle_classes = [RefreshThrottle]

    permission_classes = [AllowAny]

    def post(self, request):
        s = RefreshSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        try:
            issued = identity.rotate_session(s.validated_data["refresh"], request)
        except identity.RefreshReuseDetected as exc:
            # 401 et non 403 : le client doit se réauthentifier intégralement.
            return Response({"detail": str(exc), "code": "refresh_reuse"},
                            status=status.HTTP_401_UNAUTHORIZED)
        except identity.RefreshRejected:
            return Response({"detail": "Session invalide.", "code": "refresh_rejected"},
                            status=status.HTTP_401_UNAUTHORIZED)
        return Response({"access": issued["access"], "refresh": issued["refresh"],
                         "roles": issued["roles"], "device_id": issued["device_id"]})


class LogoutView(APIView):
    """Déconnexion : révoque la **famille** entière, pas le seul jeton présenté."""
    throttle_classes = [RefreshThrottle]

    permission_classes = [IsAuthenticated]

    def post(self, request):
        raw = (request.data or {}).get("refresh", "")
        revoked = identity.logout(raw, user=request.user)
        return Response({"revoked_sessions": revoked}, status=status.HTTP_200_OK)


class LogoutAllView(APIView):
    throttle_classes = [RefreshThrottle]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        revoked = identity.revoke_all_sessions(request.user, reason="logout_all")
        return Response({"revoked_sessions": revoked})


class SessionListView(APIView):
    """Inventaire des sessions actives — l'utilisateur voit ce qui le suit."""
    throttle_classes = [RefreshThrottle]

    permission_classes = [IsAuthenticated]

    def get(self, request):
        sessions = (RefreshSession.objects
                    .filter(user=request.user, revoked_at__isnull=True,
                            rotated_at__isnull=True)
                    .order_by("-created_at"))
        return Response(SessionSerializer(sessions, many=True).data)


class SessionRevokeView(APIView):
    """Révoque une session (et toute sa famille) appartenant à l'appelant."""
    throttle_classes = [RefreshThrottle]

    permission_classes = [IsAuthenticated]

    def post(self, request, session_id: str):
        session = RefreshSession.objects.filter(pk=session_id, user=request.user).first()
        if session is None:
            return Response({"detail": "Session inconnue."}, status=404)
        revoked = identity.revoke_family(session.family_id, reason="revoked_by_user")
        return Response({"revoked_sessions": revoked})


class WebAuthnRegisterOptionsView(APIView):
    """Options d'enregistrement FIDO2 (`navigator.credentials.create`)."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        challenge = issue_challenge(user_id=str(request.user.id),
                                    operation=REGISTER_OPERATION)
        return Response({
            "challenge": challenge,
            "rp": {"id": rp_id(), "name": "KALYCE"},
            "user": {
                "id": b64url_encode(str(request.user.id).encode()),
                "name": request.user.display_name or str(request.user.id),
                "displayName": request.user.display_name or "KALYCE",
            },
            "pubKeyCredParams": [{"type": "public-key", "alg": alg}
                                 for alg in SUPPORTED_ALGORITHMS],
            "authenticatorSelection": {"userVerification": "required",
                                       "residentKey": "preferred"},
            "excludeCredentials": [{"type": "public-key", "id": c["credential_id"]}
                                   for c in list_credentials(request.user)],
            "attestation": "none",
            "timeout": 300_000,
        })


class WebAuthnRegisterView(APIView):
    """Enregistre une clé FIDO2 après vérification cryptographique complète."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            challenge = consume_challenge(user_id=str(request.user.id),
                                          operation=REGISTER_OPERATION)
            record = register_credential(user=request.user,
                                         credential=request.data,
                                         expected_challenge=challenge,
                                         label=str(request.data.get("label", "")))
        except WebAuthnError as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response({"credential_id": record["credential_id"],
                         "algorithm": record["algorithm"],
                         "label": record["label"]}, status=201)


class WebAuthnCredentialsView(APIView):
    """Inventaire et révocation des clés FIDO2 (multi-clés, §13)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(list_credentials(request.user))

    def delete(self, request, credential_id: str):
        try:
            removed = revoke_credential(request.user, credential_id)
        except WebAuthnError as exc:
            return Response({"detail": str(exc)}, status=409)
        if not removed:
            return Response({"detail": "Clé inconnue."}, status=404)
        return Response(status=status.HTTP_204_NO_CONTENT)


class WebAuthnChallengeView(APIView):
    """Défi d'authentification, lié à une opération (défaut : ouverture de session)."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        operation = str(request.data.get("operation") or LOGIN_OPERATION)
        challenge = issue_challenge(user_id=str(request.user.id), operation=operation)
        credentials = [{"type": "public-key", "id": c["credential_id"]}
                       for c in (request.user.webauthn_credentials or [])]
        if not credentials:
            return Response({"detail": "Aucune clé FIDO2 enregistrée."}, status=400)
        return Response({"challenge": challenge, "operation": operation,
                         "rpId": rp_id(), "allowCredentials": credentials,
                         "userVerification": "required", "timeout": 300_000})


class WebAuthnVerifyView(APIView):
    """Vérifie une assertion FIDO2 réelle et ouvre une session sensible (P0-03).

    Lorsque l'opération est financière, la vérification est enregistrée avec une
    portée dédiée et une durée courte : c'est le *step-up* exigé par le §13.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        operation = str(request.data.get("operation") or LOGIN_OPERATION)
        try:
            challenge = consume_challenge(user_id=str(request.user.id),
                                          operation=operation)
            verified = verify_assertion(user=request.user, assertion=request.data,
                                        expected_challenge=challenge)
        except WebAuthnError as exc:
            return Response({"detail": str(exc)}, status=401)
        if operation.startswith("financial."):
            mark_webauthn_verified(request.user.id, ttl=STEP_UP_TTL, operation=operation)
            expires_in = STEP_UP_TTL
        else:
            mark_webauthn_verified(request.user.id)
            expires_in = WEBAUTHN_SESSION_TTL
        return Response({"status": "verified", "operation": operation,
                         "credential_id": verified.credential_id,
                         "expires_in": expires_in})


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        data = UserSerializer(request.user).data
        data["effective_roles"] = identity.effective_roles(request.user)
        return Response(data)
