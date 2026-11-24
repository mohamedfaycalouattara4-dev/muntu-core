"""Muntu Core — Claims URLs."""
from django.urls import path
from . import views

app_name = "claims"

urlpatterns = [
    path("", views.ClaimListView.as_view(), name="claim-list"),
    path("<str:pk>/", views.ClaimDetailView.as_view(), name="claim-detail"),
    path("<str:pk>/vote/", views.ClaimVoteView.as_view(), name="claim-vote"),
]
