"""Muntu Core — Documents views."""
from apps.core.tenant_context import get_tenant_id
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import Document, DocumentTemplate
from .serializers import DocumentSerializer, DocumentTemplateSerializer


class DocumentListView(generics.ListAPIView):
    serializer_class = DocumentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = Document.objects.filter(tenant_id=get_tenant_id())
        member = self.request.query_params.get("member")
        if member:
            qs = qs.filter(member_id=member)
        doc_type = self.request.query_params.get("type")
        if doc_type:
            qs = qs.filter(document_type=doc_type)
        return qs


class DocumentGenerateView(APIView):
    """Génération d'un document."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        data = request.data
        doc = Document.objects.create(
            tenant_id=get_tenant_id(),
            member_id=data.get("member_id", ""),
            document_type=data["document_type"],
            reference=data.get("reference", ""),
            period_start=data.get("period_start"),
            period_end=data.get("period_end"),
            generated_by=str(request.user.id),
        )
        return Response(DocumentSerializer(doc).data, status=status.HTTP_201_CREATED)


class DocumentDownloadView(APIView):
    """Téléchargement d'un document généré."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        doc = Document.objects.get(id=pk)
        # TODO: Retourner le fichier depuis le stockage objet
        return Response({"status": "TODO", "document_id": pk})


class DocumentTemplateListView(generics.ListAPIView):
    serializer_class = DocumentTemplateSerializer
    permission_classes = [permissions.IsAdminUser]

    def get_queryset(self):
        return DocumentTemplate.objects.filter(tenant_id=get_tenant_id())
