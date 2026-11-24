"""Muntu Core — Lending serializers."""
from rest_framework import serializers
from .models import LoanProduct, Loan, LoanInstallment


class LoanProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = LoanProduct
        fields = [
            "id", "tenant_id", "name", "version", "is_active",
            "minimum_amount", "maximum_amount", "minimum_term_months", "maximum_term_months",
            "annual_interest_rate", "late_fee_rate", "grace_period_days",
            "repayment_frequency", "amortization_method",
            "requires_guarantor", "requires_collateral", "min_guarantor_count",
            "committee_threshold", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "tenant_id", "version", "created_at", "updated_at"]


class LoanSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(read_only=True, source="product.name")

    class Meta:
        model = Loan
        fields = [
            "id", "tenant_id", "loan_number", "product", "product_name",
            "member_id", "group_id", "requested_amount", "approved_amount",
            "disbursement_amount", "outstanding_principal", "outstanding_interest",
            "total_repaid", "interest_rate", "term_months", "repayment_frequency",
            "requested_at", "approved_at", "disbursed_at", "first_due_date", "maturity_date",
            "repaid_at", "status", "approved_by", "disbursed_by",
            "agent_id", "branch_code", "fsm_state", "fsm_signature",
            "risk_class", "impairment_provision", "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "tenant_id", "loan_number", "requested_at", "created_at", "updated_at",
        ]


class LoanInstallmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = LoanInstallment
        fields = [
            "id", "loan", "installment_number", "due_date",
            "principal_amount", "interest_amount", "total_amount",
            "paid_amount", "paid_at", "is_paid", "late_fee", "days_late",
        ]
        read_only_fields = ["id", "loan"]
