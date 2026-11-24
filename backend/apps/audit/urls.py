from django.urls import path

from .views import AuditChainVerifyView, AuditLogView, MerkleAnchorsView

urlpatterns = [
    path("log/", AuditLogView.as_view(), name="audit-log"),
    path("verify/", AuditChainVerifyView.as_view(), name="audit-verify"),
    path("merkle/", MerkleAnchorsView.as_view(), name="audit-merkle"),
]
