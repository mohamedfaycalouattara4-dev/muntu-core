"""Muntu Core — Teller URLs."""
from django.urls import path
from . import views

app_name = "teller"

urlpatterns = [
    path("sessions/", views.TellerSessionListView.as_view(), name="session-list"),
    path("sessions/<str:pk>/", views.TellerSessionDetailView.as_view(), name="session-detail"),
    path("sessions/<str:pk>/open/", views.SessionOpenView.as_view(), name="session-open"),
    path("sessions/<str:pk>/operations/", views.TellerOperationView.as_view(), name="session-operations"),
    path("sessions/<str:pk>/seal/", views.SessionSealView.as_view(), name="session-seal"),
    path("transfers/", views.TellerTransferView.as_view(), name="transfer"),
]
