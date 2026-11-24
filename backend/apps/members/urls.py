"""Muntu Core — Members URLs."""
from django.urls import path
from . import views

app_name = "members"

urlpatterns = [
    path("", views.MemberListView.as_view(), name="member-list"),
    path("<str:pk>/", views.MemberDetailView.as_view(), name="member-detail"),
    path("<str:pk>/documents/", views.MemberDocumentListView.as_view(), name="member-document-list"),
    path("groups/", views.SolidarityGroupListView.as_view(), name="group-list"),
]
