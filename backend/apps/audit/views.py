from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsAdmin, IsCompliance, IsFinance

from .models import AuditEvent, MerkleAnchor
from .services import verify_chain


class AuditLogView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = []  # lecture

    def get(self, request):
        if not any(r in (request.user.roles or []) for r in
                   ("admin", "compliance", "finance", "auditor")):
            return Response({"detail": "Lecture audit restreinte"}, status=403)
        qs = AuditEvent.objects.all()[:200]
        return Response([
            {"id": e.id, "entity_type": e.entity_type, "entity_id": e.entity_id,
             "action": e.action, "actor_id": e.actor_id, "actor_ip": e.actor_ip,
             "current_hash": e.current_hash,
             "at": e.created_at.isoformat()}
            for e in qs
        ])


class AuditChainVerifyView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        broken = verify_chain()
        return Response({"broken": broken})


class MerkleAnchorsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if "compliance" not in (request.user.roles or []) and "admin" not in (request.user.roles or []):
            return Response({"detail": "Compliance requise"}, status=403)
        qs = MerkleAnchor.objects.all()[:30]
        return Response([
            {"day": str(a.day), "root": a.root, "entries_count": a.entries_count}
            for a in qs
        ])
