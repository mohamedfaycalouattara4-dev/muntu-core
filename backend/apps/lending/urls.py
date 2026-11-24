"""Muntu Core — Lending URLs."""
from django.urls import path
from . import views

app_name = "lending"

urlpatterns = [
    path("products/", views.LoanProductListView.as_view(), name="product-list"),
    path("products/<str:pk>/", views.LoanProductDetailView.as_view(), name="product-detail"),
    path("loans/", views.LoanListView.as_view(), name="loan-list"),
    path("loans/<str:pk>/", views.LoanDetailView.as_view(), name="loan-detail"),
    path("loans/<str:pk>/installments/", views.LoanInstallmentListView.as_view(), name="loan-installments"),
    path("loans/<str:pk>/payments/", views.LoanPaymentView.as_view(), name="loan-payments"),
    path("loans/<str:pk>/approve/", views.LoanApproveView.as_view(), name="loan-approve"),
    path("loans/<str:pk>/disburse/", views.LoanDisburseView.as_view(), name="loan-disburse"),
]
