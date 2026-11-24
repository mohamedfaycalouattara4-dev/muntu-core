"""Muntu Core — Members serializers."""
from rest_framework import serializers
from .models import Member, MemberDocument, SolidarityGroup


class MemberSerializer(serializers.ModelSerializer):
    class Meta:
        model = Member
        fields = [
            "id", "tenant_id", "member_number", "member_type", "status",
            "first_name", "last_name", "date_of_birth", "gender",
            "legal_name", "registration_number",
            "phone", "email", "address", "city", "country",
            "id_document_type", "id_document_number",
            "id_document_issued_at", "id_document_expires_at",
            "shares_count", "share_value", "referred_by", "branch_code",
            "onboarded_at", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "tenant_id", "onboarded_at", "created_at", "updated_at"]


class MemberDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = MemberDocument
        fields = ["id", "member", "document_type", "file_path", "file_hash", "uploaded_by", "is_verified", "created_at"]
        read_only_fields = ["id", "file_hash", "created_at"]


class SolidarityGroupSerializer(serializers.ModelSerializer):
    member_count = serializers.IntegerField(read_only=True, source="members.count")

    class Meta:
        model = SolidarityGroup
        fields = ["id", "tenant_id", "name", "leader_member_id", "meeting_day", "meeting_frequency", "is_active", "member_count", "created_at"]
        read_only_fields = ["id", "tenant_id", "member_count", "created_at"]
