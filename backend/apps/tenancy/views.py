"""Muntu Core — Tenancy views (CRUD Institution, Branch, ModuleToggle)."""
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from .models import Institution, Branch, ModuleToggle
from .serializers import InstitutionSerializer, BranchSerializer, ModuleToggleSerializer


class InstitutionListView(generics.ListCreateAPIView):
    serializer_class = InstitutionSerializer
    permission_classes = [permissions.IsAdminUser]
    queryset = Institution.objects.all()


class InstitutionDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = InstitutionSerializer
    permission_classes = [permissions.IsAdminUser]
    queryset = Institution.objects.all()
    lookup_field = "pk"


class BranchListView(generics.ListCreateAPIView):
    serializer_class = BranchSerializer
    permission_classes = [permissions.IsAdminUser]

    def get_queryset(self):
        return Branch.objects.filter(institution_id=self.kwargs["pk"])


class ModuleToggleListView(generics.ListAPIView):
    serializer_class = ModuleToggleSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return ModuleToggle.objects.filter(institution_id=self.kwargs["pk"])
