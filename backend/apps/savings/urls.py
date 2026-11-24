"""Muntu Core — Savings URLs."""
from django.urls import path
from . import views

app_name = "savings"

urlpatterns = [
    path("products/", views.SavingsProductListView.as_view(), name="product-list"),
    path("products/<str:pk>/", views.SavingsProductDetailView.as_view(), name="product-detail"),
    path("accounts/", views.SavingsAccountListView.as_view(), name="account-list"),
    path("accounts/<str:pk>/", views.SavingsAccountDetailView.as_view(), name="account-detail"),
    path("accounts/<str:pk>/operations/", views.SavingsOperationView.as_view(), name="account-operations"),
    path("accounts/<str:pk>/statement/", views.SavingsStatementView.as_view(), name="account-statement"),
]
