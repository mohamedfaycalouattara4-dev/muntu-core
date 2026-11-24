"""Muntu Core — Tenancy URLs."""
from django.urls import path
from . import views

app_name = "tenancy"

urlpatterns = [
    path("institutions/", views.InstitutionListView.as_view(), name="institution-list"),
    path("institutions/<str:pk>/", views.InstitutionDetailView.as_view(), name="institution-detail"),
    path("institutions/<str:pk>/branches/", views.BranchListView.as_view(), name="branch-list"),
    path("institutions/<str:pk>/modules/", views.ModuleToggleListView.as_view(), name="module-list"),
]
