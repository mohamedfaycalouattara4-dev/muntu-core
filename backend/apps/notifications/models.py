"""Notifications · multi-canal (Push/SMS/USSD/WhatsApp/Email/Voice)."""
from django.db import models
from apps.core.models import TimeStampedModel, generate_ulid


class NotificationChannel(models.TextChoices):
    PUSH = "push"
    SMS = "sms"
    USSD = "ussd"
    WHATSAPP = "whatsapp"
    EMAIL = "email"
    VOICE = "voice"


class NotificationState(models.TextChoices):
    PENDING = "pending"
    SENT = "sent"
    READ = "read"
    ERROR = "error"


class Notification(TimeStampedModel):
    id = models.CharField(max_length=26, primary_key=True, default=generate_ulid, editable=False)
    recipient_id = models.CharField(max_length=26, db_index=True)
    channel = models.CharField(max_length=20, choices=NotificationChannel.choices)
    template_key = models.CharField(max_length=80)
    payload = models.JSONField(default=dict)
    state = models.CharField(max_length=20, choices=NotificationState.choices, default="pending", db_index=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    error_log = models.TextField(blank=True)
