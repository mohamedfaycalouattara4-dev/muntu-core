"""Muntu Core — Accounting views."""
from apps.core.tenant_context import get_tenant_id
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import ChartAccount, JournalEntry, AccountingDay
from .serializers import ChartAccountSerializer, JournalEntrySerializer, AccountingDaySerializer


class ChartAccountListView(generics.ListCreateAPIView):
    serializer_class = ChartAccountSerializer
    permission_classes = [permissions.IsAdminUser]

    def get_queryset(self):
        return ChartAccount.objects.filter(tenant_id=get_tenant_id())


class ChartAccountDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = ChartAccountSerializer
    permission_classes = [permissions.IsAdminUser]
    queryset = ChartAccount.objects.all()


class JournalEntryListView(generics.ListAPIView):
    serializer_class = JournalEntrySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = JournalEntry.objects.filter(tenant_id=get_tenant_id())
        account = self.request.query_params.get("account")
        if account:
            qs = qs.filter(account_code=account)
        return qs.order_by("-recorded_at")


class JournalEntryDetailView(generics.RetrieveAPIView):
    serializer_class = JournalEntrySerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = JournalEntry.objects.all()


class AccountingDayListView(generics.ListAPIView):
    serializer_class = AccountingDaySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return AccountingDay.objects.filter(tenant_id=get_tenant_id())


class DaySealView(APIView):
    """Scellement d'une journée comptable."""
    permission_classes = [permissions.IsAdminUser]

    def post(self, request, pk):
        day = AccountingDay.objects.get(id=pk)
        if day.status != "OPEN":
            return Response({"error": "Journée non ouverte"}, status=400)
        import hashlib, json
        merkle_root = hashlib.sha256(json.dumps({"day": pk}).encode()).hexdigest()
        day.seal(sealed_by=str(request.user.id), merkle_root=merkle_root)
        return Response({"status": "SEALED", "merkle_root": merkle_root})


class BalanceView(APIView):
    """Balance générale — projection depuis le grand livre."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        tenant_id = get_tenant_id()
        accounts = ChartAccount.objects.filter(tenant_id=tenant_id, is_active=True)
        balance = []
        for acct in accounts:
            entries = JournalEntry.objects.filter(tenant_id=tenant_id, account_code=acct.code)
            total_debit = sum(e.amount_xof for e in entries if e.direction == "DEBIT")
            total_credit = sum(e.amount_xof for e in entries if e.direction == "CREDIT")
            balance.append({
                "code": acct.code,
                "name": acct.name,
                "category": acct.category,
                "debit": total_debit,
                "credit": total_credit,
                "net": total_debit - total_credit if acct.category == "ASSET" else total_credit - total_debit,
            })
        return Response(balance)
