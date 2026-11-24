"""Muntu Core — Teller views."""
from apps.core.tenant_context import get_tenant_id
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import TellerSession, TellerOperation
from .serializers import TellerSessionSerializer, TellerOperationSerializer


class TellerSessionListView(generics.ListAPIView):
    serializer_class = TellerSessionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        tenant_id = get_tenant_id()
        return TellerSession.objects.filter(tenant_id=tenant_id)


class TellerSessionDetailView(generics.RetrieveAPIView):
    serializer_class = TellerSessionSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = TellerSession.objects.all()


class SessionOpenView(APIView):
    """Ouverture d'une session de caisse."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        session = TellerSession.objects.get(id=pk)
        dotation = int(request.data.get("dotation", 0))
        if dotation < 0:
            return Response({"error": "Dotation invalide"}, status=400)
        session.open(dotation=dotation, opened_by=str(request.user.id))
        return Response({"status": "OPEN", "opening_balance": dotation})


class TellerOperationView(APIView):
    """Dépôt / retrait de caisse."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        from .services.operations import process_teller_operation
        data = request.data
        result = process_teller_operation(
            session_id=pk,
            operation_type=data["type"],
            amount=int(data["amount"]),
            counterparty_member_id=data.get("counterparty_member_id", ""),
            performed_by=str(request.user.id),
        )
        return Response(result, status=status.HTTP_201_CREATED)


class SessionSealView(APIView):
    """Scellement de l'arrêté de caisse."""
    permission_classes = [permissions.IsAdminUser]

    def post(self, request, pk):
        session = TellerSession.objects.get(id=pk)
        counted = int(request.data.get("counted_balance", session.current_balance))
        import hashlib
        import json
        # TODO: Vrai calcul Merkle — ici placeholder
        merkle_root = hashlib.sha256(json.dumps({"session": pk}).encode()).hexdigest()
        session.seal(counted=counted, sealed_by=str(request.user.id), merkle_root=merkle_root)
        return Response({"status": "SEALED", "discrepancy": session.discrepancy})


class TellerTransferView(APIView):
    """Transfert entre caisses."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        return Response({"status": "TODO"}, status=202)
