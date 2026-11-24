"""Muntu Core — Claims views."""
from apps.core.tenant_context import get_tenant_id
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import Claim, ClaimResolution
from .serializers import ClaimSerializer, ClaimResolutionSerializer


class ClaimListView(generics.ListCreateAPIView):
    serializer_class = ClaimSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Claim.objects.filter(tenant_id=get_tenant_id())

    def perform_create(self, serializer):
        from apps.members.models import Member
        tenant_id = get_tenant_id()
        claim = serializer.save(tenant_id=tenant_id)
        # Auto-générer la référence
        claim.reference = f"CL-{tenant_id[:6]}-{claim.pk[:6].upper()}"
        claim.save(update_fields=["reference"])


class ClaimDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = ClaimSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Claim.objects.all()


class ClaimVoteView(APIView):
    """Vote d'arbitrage (quorum)."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        claim = Claim.objects.get(id=pk)
        vote = request.data.get("vote", "YES")
        reasoning = request.data.get("reasoning", "")

        resolution, created = ClaimResolution.objects.get_or_create(
            claim=claim,
            voter_id=str(request.user.id),
            defaults={"vote": vote, "reasoning": reasoning},
        )
        if not created:
            resolution.vote = vote
            resolution.reasoning = reasoning
            resolution.save()

        # Recalculer le quorum
        yes = ClaimResolution.objects.filter(claim=claim, vote="YES").count()
        no = ClaimResolution.objects.filter(claim=claim, vote="NO").count()
        claim.quorum_votes_yes = yes
        claim.quorum_votes_no = no
        if yes >= claim.quorum_required:
            claim.status = "RESOLVED"
        elif no >= claim.quorum_required:
            claim.status = "CLOSED"
        else:
            claim.status = "ARBITRATION"
        claim.save()

        return Response({"vote": vote, "quorum": {"yes": yes, "no": no, "required": claim.quorum_required}})
