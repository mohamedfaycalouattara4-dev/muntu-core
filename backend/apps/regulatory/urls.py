"""Muntu Core — Regulatory URLs."""
from django.urls import path
from . import views

app_name = "regulatory"

urlpatterns = [
    path("reports/", views.RegulatoryReportListView.as_view(), name="report-list"),
    path("reports/generate/", views.ReportGenerateView.as_view(), name="report-generate"),
    path("risk-center/", views.RiskCenterView.as_view(), name="risk-center"),
    path("aml-alerts/", views.AMLAlertListView.as_view(), name="aml-list"),
    path("aml-alerts/<str:pk>/review/", views.AMLAlertReviewView.as_view(), name="aml-review"),
]
