from rest_framework import serializers

from .models import CourierProfile, RefreshSession, User, VendorProfile


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "display_name", "roles", "kyc_status", "trust_score",
                  "preferred_language", "is_webauthn_enabled"]
        read_only_fields = ["id", "trust_score"]


class OTPSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=20)


class OTPVerifySerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=20)
    code = serializers.CharField(max_length=8)


class RefreshSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class SessionSerializer(serializers.ModelSerializer):
    """Vue utilisateur d'une session : aucun jeton, aucune IP en clair."""

    device_label = serializers.CharField(source="device.label", default="", read_only=True)

    class Meta:
        model = RefreshSession
        fields = ["id", "family_id", "device_label", "created_at", "expires_at"]


class VendorProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = VendorProfile
        fields = ["business_name", "rccm_number", "kyb_status", "commission_rate",
                  "available_balance_xof", "held_balance_xof", "delivery_delay_hours"]


class CourierProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = CourierProfile
        fields = ["vehicle_type", "vehicle_plate", "is_available", "delivery_score",
                  "available_balance_xof", "coverage_zones"]
