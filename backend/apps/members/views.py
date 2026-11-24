"""Muntu Core — Members views."""
from apps.core.tenant_context import get_tenant_id
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from .models import Member, MemberDocument, SolidarityGroup
from .serializers import MemberSerializer, MemberDocumentSerializer, SolidarityGroupSerializer


class MemberListView(generics.ListCreateAPIView):
    serializer_class = MemberSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        tenant_id = get_tenant_id()
        return Member.objects.filter(tenant_id=tenant_id)

    def perform_create(self, serializer):
        serializer.save(tenant_id=get_tenant_id())


class MemberDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = MemberSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Member.objects.all()


class MemberDocumentListView(generics.ListCreateAPIView):
    serializer_class = MemberDocumentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return MemberDocument.objects.filter(member_id=self.kwargs["pk"])


class SolidarityGroupListView(generics.ListCreateAPIView):
    serializer_class = SolidarityGroupSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        tenant_id = get_tenant_id()
        return SolidarityGroup.objects.filter(tenant_id=tenant_id)

    def perform_create(self, serializer):
        serializer.save(tenant_id=get_tenant_id())
