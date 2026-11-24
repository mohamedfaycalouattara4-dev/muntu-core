from django.urls import path

from .webhooks import PaymentWebhookView, WebhookEventCatalogView

urlpatterns = [
    path("events/", WebhookEventCatalogView.as_view(), name="webhook-events"),
    path("payment/<str:aggregator>/", PaymentWebhookView.as_view(), name="payment-webhook"),
]
