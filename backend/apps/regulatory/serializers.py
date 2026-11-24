"""Muntu Core — Regulatory serializers."""
from rest_framework import serializers
from .models import RegulatoryReport, RiskCenterEntry, AMLAlert


class RegulatoryReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = RegulatoryReport
        fields = ["id", "tenant_id", "report_type", "period_start", "period_end", "generated_at", "generated_by", "file_path", "file_hash", "data_snapshot", "status", "submitted_at", "created_at"]
        read_only_fields = ["id", "tenant_id", "generated_at", "created_at"]


class RiskCenterEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = RiskCenterEntry
        fields = ["id", "tenant_id", "member_id", "reporting_date", "total_credit_granted", "total_credit_outstanding", "total_credit_overdue", "total_credit_defaulted", "number_of_active_loans", "number_of_overdue_loans", "risk_classification"]
        read_only_fields = ["id", "tenant_id"]


class AMLAlertSerializer(serializers.ModelSerializer):
    class Meta:
        model = AMLAlert
        fields = ["id", "tenant_id", "member_id", "alert_type", "description", "amount_xof", "severity", "status", "reviewed_by", "reviewed_at", "declared_to_authority", "declared_at", "created_at", "updated_at"]
        read_only_fields = ["id", "tenant_id", "reviewed_by", "reviewed_at", "declared_at", "created_at", "updated_at"]
