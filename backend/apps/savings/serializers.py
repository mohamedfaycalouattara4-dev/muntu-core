"""Muntu Core — Savings serializers."""
from rest_framework import serializers
from .models import SavingsProduct, SavingsAccount


class SavingsProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = SavingsProduct
        fields = [
            "id", "tenant_id", "name", "product_type", "version", "is_active",
            "minimum_balance", "maximum_balance", "annual_interest_rate",
            "interest_frequency", "interest_compounding", "withdrawal_fee",
            "monthly_maintenance_fee", "minimum_term_days", "penalty_rate",
            "auto_renewal", "daily_withdrawal_limit", "min_withdrawal",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "tenant_id", "version", "created_at", "updated_at"]


class SavingsAccountSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(read_only=True, source="product.name")

    class Meta:
        model = SavingsAccount
        fields = [
            "id", "tenant_id", "member_id", "product", "product_name",
            "account_number", "status", "opened_at", "closed_at", "maturity_date",
            "periodic_amount", "periodic_frequency", "periodic_next_due",
            "blocked_amount", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "tenant_id", "account_number", "opened_at", "closed_at", "created_at", "updated_at"]
