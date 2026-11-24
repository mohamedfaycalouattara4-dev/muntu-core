"""Muntu Core — Throttles différenciés par rôle et domaine métier."""
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle, ScopedRateThrottle


class OtpRequestThrottle(AnonRateThrottle):
    """3 / min — protection contre le brute-force OTP."""
    scope = "otp_request"
    rate = "3/min"


class OtpVerifyThrottle(AnonRateThrottle):
    """10 / min — le verrouillage progressif fait le reste du travail."""
    scope = "otp_verify"
    rate = "10/min"


class FinancialOperationThrottle(UserRateThrottle):
    """20 / heure — opérations financières sensibles (dépôts, retraits, virements)."""
    scope = "financial_operation"
    rate = "20/hour"


class TellerOperationThrottle(UserRateThrottle):
    """60 / min — opérations de caisse (haute fréquence en journée)."""
    scope = "teller_operation"
    rate = "60/min"


class AdminThrottle(UserRateThrottle):
    """1000 / min — back-office sans restriction sévère."""
    scope = "admin"
    rate = "1000/min"


class RefreshThrottle(AnonRateThrottle):
    """30 / min — la rotation JWT est fréquente et légitime."""
    scope = "refresh"
    rate = "30/min"
