"""Compliance · archives 10 ans (BCEAO)."""
from django.db import models
from apps.core.models import TimeStampedModel


class ComplianceArchive(TimeStampedModel):
    name = models.CharField(max_length=200, primary_key=True)
    s3_key = models.CharField(max_length=500)
    sha256 = models.CharField(max_length=64)
    encrypted = models.BooleanField(default=True)
    retention_until = models.DateField()
