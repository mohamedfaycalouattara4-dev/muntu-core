"""Muntu Core — Documents serializers."""
from rest_framework import serializers
from .models import Document, DocumentTemplate


class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = ["id", "tenant_id", "member_id", "document_type", "reference", "period_start", "period_end", "file_path", "file_format", "file_hash", "generated_by", "generated_at", "created_at"]
        read_only_fields = ["id", "tenant_id", "generated_by", "generated_at", "created_at"]


class DocumentTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentTemplate
        fields = ["id", "tenant_id", "document_type", "template_name", "content_html", "language", "is_active", "version", "created_at", "updated_at"]
        read_only_fields = ["id", "tenant_id", "version", "created_at", "updated_at"]
