"""Muntu Core — Savings views."""
from apps.core.tenant_context import get_tenant_id
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import SavingsProduct, SavingsAccount
from .serializers import SavingsProductSerializer, SavingsAccountSerializer


class SavingsProductListView(generics.ListCreateAPIView):
    serializer_class = SavingsProductSerializer
    permission_classes = [permissions.IsAdminUser]

    def get_queryset(self):
        tenant_id = get_tenant_id()
        return SavingsProduct.objects.filter(tenant_id=tenant_id, is_active=True)

    def perform_create(self, serializer):
        serializer.save(tenant_id=get_tenant_id())


class SavingsProductDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = SavingsProductSerializer
    permission_classes = [permissions.IsAdminUser]
    queryset = SavingsProduct.objects.all()


class SavingsAccountListView(generics.ListCreateAPIView):
    serializer_class = SavingsAccountSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        tenant_id = get_tenant_id()
        return SavingsAccount.objects.filter(tenant_id=tenant_id)

    def perform_create(self, serializer):
        serializer.save(tenant_id=get_tenant_id())


class SavingsAccountDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = SavingsAccountSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = SavingsAccount.objects.all()


class SavingsOperationView(APIView):
    """Dépôt / retrait sur un compte d'épargne."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        from .services.operations import deposit, withdraw
        data = request.data
        op_type = data.get("type")
        amount = int(data.get("amount", 0))
        performed_by = request.user.id

        if op_type == "DEPOSIT":
            result = deposit(account_id=pk, amount=amount, performed_by=str(performed_by))
        elif op_type == "WITHDRAWAL":
            result = withdraw(account_id=pk, amount=amount, performed_by=str(performed_by))
        else:
            return Response({"error": "Type invalide"}, status=status.HTTP_400_BAD_REQUEST)

        return Response(result, status=status.HTTP_201_CREATED)


class SavingsStatementView(APIView):
    """Relevé d'épargne — projeté depuis le grand livre."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        from .services.statement import compute_statement
        period_start = request.query_params.get("start")
        period_end = request.query_params.get("end")
        statement = compute_statement(account_id=pk, period_start=period_start, period_end=period_end)
        return Response(statement)
