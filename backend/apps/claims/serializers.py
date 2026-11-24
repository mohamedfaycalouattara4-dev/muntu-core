"""Muntu Core — Claims serializers."""
from rest_framework import serializers
from .models import Claim, ClaimResolution


class ClaimSerializer(serializers.ModelSerializer):
    class Meta:
        model = Claim
        fields = [
            "id", "tenant_id", "reference", "member_id", "category",
            "description", "amount_xof", "status", "priority",
            "assigned_to", "requires_quorum", "quorum_votes_yes",
            "quorum_votes_no", "quorum_required", "resolution",
            "resolved_by", "resolved_at", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "tenant_id", "reference", "quorum_votes_yes", "quorum_votes_no", "resolved_by", "resolved_at", "created_at", "updated_at"]


class ClaimResolutionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClaimResolution
        fields = ["id", "claim", "voter_id", "vote", "reasoning", "voted_at"]
        read_only_fields = ["id", "voted_at"]
