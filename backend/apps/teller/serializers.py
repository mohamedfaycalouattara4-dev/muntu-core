"""Muntu Core — Teller serializers."""
from rest_framework import serializers
from .models import TellerSession, TellerOperation


class TellerSessionSerializer(serializers.ModelSerializer):
    current_balance = serializers.IntegerField(read_only=True)

    class Meta:
        model = TellerSession
        fields = [
            "id", "tenant_id", "branch_code", "teller_id", "teller_name",
            "status", "opening_balance", "current_balance",
            "expected_balance", "counted_balance", "discrepancy",
            "total_deposits", "total_withdrawals", "total_transfers_in", "total_transfers_out",
            "operation_count", "opened_at", "closed_at", "sealed_at", "sealed_by",
            "merkle_root", "created_at",
        ]
        read_only_fields = ["id", "tenant_id", "current_balance", "created_at"]


class TellerOperationSerializer(serializers.ModelSerializer):
    class Meta:
        model = TellerOperation
        fields = [
            "id", "session", "tenant_id", "operation_type", "amount",
            "counterparty_member_id", "counterparty_account", "reference",
            "proof_code", "receipt_number", "performed_at", "performed_by",
        ]
        read_only_fields = ["id", "tenant_id", "performed_at"]
