"""Muntu Core — Tenancy serializers."""
from rest_framework import serializers
from .models import Institution, Branch, ModuleToggle


class InstitutionSerializer(serializers.ModelSerializer):
    is_active = serializers.BooleanField(read_only=True, source="is_active")

    class Meta:
        model = Institution
        fields = [
            "id", "name", "slug", "status", "country_code", "registration_number",
            "currency", "currency_minor_unit", "timezone", "config",
            "onboarded_at", "suspended_at", "suspended_reason",
            "is_active", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "onboarded_at", "suspended_at", "created_at", "updated_at"]


class BranchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Branch
        fields = ["id", "institution", "name", "code", "address", "phone", "is_hq", "is_active", "created_at"]
        read_only_fields = ["id", "created_at"]


class ModuleToggleSerializer(serializers.ModelSerializer):
    class Meta:
        model = ModuleToggle
        fields = ["id", "institution", "module_name", "is_enabled", "enabled_at", "created_at"]
        read_only_fields = ["id", "enabled_at", "created_at"]
