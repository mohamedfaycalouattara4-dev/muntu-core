"""Muntu Core — Accounting URLs."""
from django.urls import path
from . import views

app_name = "accounting"

urlpatterns = [
    path("accounts/", views.ChartAccountListView.as_view(), name="chart-list"),
    path("accounts/<str:pk>/", views.ChartAccountDetailView.as_view(), name="chart-detail"),
    path("entries/", views.JournalEntryListView.as_view(), name="entry-list"),
    path("entries/<str:pk>/", views.JournalEntryDetailView.as_view(), name="entry-detail"),
    path("days/", views.AccountingDayListView.as_view(), name="day-list"),
    path("days/<str:pk>/seal/", views.DaySealView.as_view(), name="day-seal"),
    path("balance/", views.BalanceView.as_view(), name="balance"),
]
