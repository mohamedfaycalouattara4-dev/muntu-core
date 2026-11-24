"""Muntu Core — Regulatory views."""
from apps.core.tenant_context import get_tenant_id
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import RegulatoryReport, RiskCenterEntry, AMLAlert
from .serializers import RegulatoryReportSerializer, RiskCenterEntrySerializer, AMLAlertSerializer


class RegulatoryReportListView(generics.ListAPIView):
    serializer_class = RegulatoryReportSerializer
    permission_classes = [permissions.IsAdminUser]

    def get_queryset(self):
        return RegulatoryReport.objects.filter(tenant_id=get_tenant_id())


class ReportGenerateView(APIView):
    """Génération d'un état réglementaire."""
    permission_classes = [permissions.IsAdminUser]

    def post(self, request):
        data = request.data
        report = RegulatoryReport.objects.create(
            tenant_id=get_tenant_id(),
            report_type=data["report_type"],
            period_start=data["period_start"],
            period_end=data["period_end"],
            generated_by=str(request.user.id),
            status="GENERATED",
        )
        return Response(RegulatoryReportSerializer(report).data, status=status.HTTP_201_CREATED)


class RiskCenterView(APIView):
    """Centrale des risques."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        qs = RiskCenterEntry.objects.filter(tenant_id=get_tenant_id())
        date = request.query_params.get("date")
        if date:
            qs = qs.filter(reporting_date=date)
        return Response(RiskCenterEntrySerializer(qs, many=True).data)


class AMLAlertListView(generics.ListCreateAPIView):
    serializer_class = AMLAlertSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return AMLAlert.objects.filter(tenant_id=get_tenant_id())


class AMLAlertReviewView(APIView):
    """Révision d'une alerte AML."""
    permission_classes = [permissions.IsAdminUser]

    def post(self, request, pk):
        alert = AMLAlert.objects.get(id=pk)
        alert.status = request.data.get("status", "UNDER_REVIEW")
        alert.reviewed_by = str(request.user.id)
        from django.utils import timezone
        alert.reviewed_at = timezone.now()
        alert.save()
        return Response(AMLAlertSerializer(alert).data)
