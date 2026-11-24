from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsAdmin, IsCompliance

from .models import AMLAlert


class AMLAlertsView(APIView):
    permission_classes = [IsAuthenticated, IsCompliance | IsAdmin]

    def get(self, request):
        qs = AMLAlert.objects.all()[:200]
        return Response([
            {"id": a.id, "user_id": a.user_id, "order_id": a.order_id,
             "score": a.score, "severity": a.severity, "rule_code": a.rule_code,
             "status": a.status, "sar_filed": a.sar_filed,
             "created_at": a.created_at.isoformat()}
            for a in qs
        ])
