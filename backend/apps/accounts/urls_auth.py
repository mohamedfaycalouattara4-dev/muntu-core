from django.urls import path

from .views import (
    LogoutAllView,
    LogoutView,
    MeView,
    OTPRequestView,
    OTPVerifyView,
    RefreshView,
    SessionListView,
    SessionRevokeView,
    WebAuthnChallengeView,
    WebAuthnCredentialsView,
    WebAuthnRegisterOptionsView,
    WebAuthnRegisterView,
    WebAuthnVerifyView,
)

urlpatterns = [
    path("otp/request/", OTPRequestView.as_view(), name="otp-request"),
    path("otp/verify/", OTPVerifyView.as_view(), name="otp-verify"),
    path("refresh/", RefreshView.as_view(), name="auth-refresh"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("logout/all/", LogoutAllView.as_view(), name="logout-all"),
    path("sessions/", SessionListView.as_view(), name="session-list"),
    path("sessions/<str:session_id>/revoke/", SessionRevokeView.as_view(),
         name="session-revoke"),
    path("me/", MeView.as_view(), name="auth-me"),
    path("webauthn/register/options/", WebAuthnRegisterOptionsView.as_view(),
         name="webauthn-register-options"),
    path("webauthn/register/", WebAuthnRegisterView.as_view(), name="webauthn-register"),
    path("webauthn/credentials/", WebAuthnCredentialsView.as_view(),
         name="webauthn-credentials"),
    path("webauthn/credentials/<str:credential_id>/", WebAuthnCredentialsView.as_view(),
         name="webauthn-credential-detail"),
    path("webauthn/challenge/", WebAuthnChallengeView.as_view(), name="webauthn-challenge"),
    path("webauthn/verify/", WebAuthnVerifyView.as_view(), name="webauthn-verify"),
]
