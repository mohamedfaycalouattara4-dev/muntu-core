"""Muntu Core — Documents URLs."""
from django.urls import path
from . import views

app_name = "documents"

urlpatterns = [
    path("", views.DocumentListView.as_view(), name="document-list"),
    path("generate/", views.DocumentGenerateView.as_view(), name="document-generate"),
    path("<str:pk>/download/", views.DocumentDownloadView.as_view(), name="document-download"),
    path("templates/", views.DocumentTemplateListView.as_view(), name="template-list"),
]
