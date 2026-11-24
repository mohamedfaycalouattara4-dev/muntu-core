"""Muntu Core — Accounting serializers."""
from rest_framework import serializers
from .models import ChartAccount, JournalEntry, AccountingDay


class ChartAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChartAccount
        fields = ["id", "tenant_id", "code", "name", "category", "parent_code", "description", "is_active", "created_at"]
        read_only_fields = ["id", "tenant_id", "created_at"]


class JournalEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = JournalEntry
        fields = [
            "id", "tenant_id", "accounting_day_id", "account_code",
            "direction", "amount_xof", "description", "reference",
            "original_entry_id", "recorded_by", "recorded_at",
            "previous_hash", "entry_hash", "signature",
        ]
        read_only_fields = ["id", "tenant_id", "recorded_at", "entry_hash", "signature"]


class AccountingDaySerializer(serializers.ModelSerializer):
    class Meta:
        model = AccountingDay
        fields = [
            "id", "tenant_id", "day_date", "branch_code", "status",
            "opened_at", "sealed_at", "sealed_by", "merkle_root",
            "total_debit", "total_credit", "entry_count", "is_balanced", "notes",
        ]
        read_only_fields = ["id", "tenant_id", "opened_at", "sealed_at", "created_at"]
