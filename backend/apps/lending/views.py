"""Muntu Core — Lending views."""
from datetime import date, timedelta

from django.utils import timezone

from apps.core.tenant_context import get_tenant_id
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import LoanProduct, Loan, LoanInstallment
from .serializers import LoanProductSerializer, LoanSerializer, LoanInstallmentSerializer


class LoanProductListView(generics.ListCreateAPIView):
    serializer_class = LoanProductSerializer
    permission_classes = [permissions.IsAdminUser]

    def get_queryset(self):
        return LoanProduct.objects.filter(tenant_id=get_tenant_id(), is_active=True)

    def perform_create(self, serializer):
        serializer.save(tenant_id=get_tenant_id())


class LoanProductDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = LoanProductSerializer
    permission_classes = [permissions.IsAdminUser]
    queryset = LoanProduct.objects.all()


class LoanListView(generics.ListCreateAPIView):
    serializer_class = LoanSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Loan.objects.filter(tenant_id=get_tenant_id())

    def perform_create(self, serializer):
        tenant_id = get_tenant_id()
        loan = serializer.save(tenant_id=tenant_id)
        # Générer l'échéancier si le prêt est approuvé
        if loan.approved_amount > 0:
            from .services.schedule import compute_schedule
            product = loan.product
            freq_map = {"MONTHLY": 1, "BIWEEKLY": 0.5, "WEEKLY": 0.25}
            freq_months = freq_map.get(product.repayment_frequency, 1)
            schedule = compute_schedule(
                principal=loan.approved_amount,
                annual_rate=loan.interest_rate,
                term_months=loan.term_months,
                frequency_months=int(freq_months),
                method=product.amortization_method,
            )
            for line in schedule:
                LoanInstallment.objects.create(
                    loan=loan,
                    installment_number=line.number,
                    due_date=_day_to_date(line.due_date),
                    principal_amount=line.principal,
                    interest_amount=line.interest,
                    total_amount=line.total,
                )


class LoanDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = LoanSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Loan.objects.all()


class LoanInstallmentListView(generics.ListAPIView):
    serializer_class = LoanInstallmentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return LoanInstallment.objects.filter(loan_id=self.kwargs["pk"])


class LoanPaymentView(APIView):
    """Règlement d'une échéance de prêt."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        from .services.payment import process_payment
        data = request.data
        result = process_payment(
            loan_id=pk,
            installment_id=data.get("installment_id"),
            amount=int(data.get("amount", 0)),
            payment_method=data.get("payment_method", "CASH"),
            performed_by=str(request.user.id),
        )
        return Response(result, status=status.HTTP_201_CREATED)


class LoanApproveView(APIView):
    """Approbation d'un prêt (avec machine à états signée)."""
    permission_classes = [permissions.IsAdminUser]

    def post(self, request, pk):
        loan = Loan.objects.get(id=pk)
        if loan.status != "UNDER_REVIEW":
            return Response({"error": "Seuls les prêts en examen peuvent être approuvés."}, status=400)
        amount = int(request.data.get("approved_amount", loan.requested_amount))
        loan.approved_amount = amount
        loan.status = "APPROVED"
        loan.approved_at = timezone.now()
        loan.approved_by = str(request.user.id)
        loan.save()
        return Response({"status": "APPROVED", "approved_amount": amount})


class LoanDisburseView(APIView):
    """Décaissement d'un prêt."""
    permission_classes = [permissions.IsAdminUser]

    def post(self, request, pk):
        loan = Loan.objects.get(id=pk)
        if loan.status != "APPROVED":
            return Response({"error": "Seuls les prêts approuvés peuvent être décaissés."}, status=400)
        loan.status = "DISBURSED"
        loan.disbursed_amount = loan.approved_amount
        loan.outstanding_principal = loan.approved_amount
        loan.disbursed_at = timezone.now()
        loan.disbursed_by = str(request.user.id)
        loan.save()
        return Response({"status": "DISBURSED", "amount": loan.disbursed_amount})


def _day_to_date(days: int) -> date:
    """Convertit un décalage en jours depuis aujourd'hui."""
    return (timezone.now() + timedelta(days=days)).date()
