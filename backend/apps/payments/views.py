"""Views finance (lecture seule du grand livre, cycle de vie d'un paiement)."""
from __future__ import annotations

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsAdmin, IsFinance
from apps.core.tenant_context import get_tenant_id
from apps.core.throttling import FinancialOpThrottle

from .models import LedgerEntry
from .services.payments import (
    PaymentError,
    complete_payment,
    initiate_payment,
    refund_payment,
)


class LedgerReadOnlyView(APIView):
    """`GET /api/v1/admin/finance/ledger/` — finance/admin, isolé par tenant."""

    permission_classes = [IsAuthenticated, IsFinance | IsAdmin]

    def get(self, request):
        qs = LedgerEntry.objects.filter(tenant_id=get_tenant_id()).order_by("-id")[:500]
        return Response([
            {"id": e.id, "tenant_id": e.tenant_id, "account": e.account,
             "direction": e.direction, "amount_xof": e.amount_xof,
             "reference": e.reference, "prev": e.previous_hash,
             "hash": e.entry_hash, "at": e.created_at.isoformat()}
            for e in qs
        ])


class InitiatePaymentView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [FinancialOpThrottle]

    def post(self, request):
        try:
            payment = initiate_payment(
                tenant_id=get_tenant_id(),
                amount_xof=int(request.data["amount_xof"]),
                aggregator=request.data["aggregator"],
                purpose=request.data["purpose"],
                member_id=request.data.get("member_id", ""),
                loan_id=request.data.get("loan_id", ""),
                savings_account_id=request.data.get("savings_account_id", ""),
                teller_session_id=request.data.get("teller_session_id", ""),
                idempotency_key=request.headers["Idempotency-Key"],
                performed_by=str(request.user.id),
            )
        except (PaymentError, KeyError, ValueError) as exc:
            return Response({"error": str(exc)}, status=400)
        return Response({"payment_id": payment.id, "ref": payment.aggregator_ref,
                         "state": payment.state}, status=201)


class CompletePaymentView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [FinancialOpThrottle]

    def post(self, request, payment_id: str):
        try:
            result = complete_payment(
                tenant_id=get_tenant_id(),
                payment_id=payment_id,
                purpose=request.data["purpose"],
                recorded_by=str(request.user.id),
                day_id=request.data.get("day_id", ""),
            )
        except (PaymentError, KeyError) as exc:
            return Response({"error": str(exc)}, status=400)
        return Response({"status": result})


class RefundPaymentView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [FinancialOpThrottle]

    def post(self, request, payment_id: str):
        try:
            result = refund_payment(
                tenant_id=get_tenant_id(),
                payment_id=payment_id,
                reason=request.data.get("reason", "manual"),
                recorded_by=str(request.user.id),
            )
        except PaymentError as exc:
            return Response({"error": str(exc)}, status=400)
        return Response({"status": result})
