"""Muntu Core — URLs principales."""
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path("admin/", admin.site.urls),
    # Core
    path("api/v1/", include("apps.core.urls")),
    # Auth & comptes
    path("api/v1/auth/", include("apps.accounts.urls_auth")),
    path("api/v1/users/", include("apps.accounts.urls_users")),
    # Tenancy
    path("api/v1/tenancy/", include("apps.tenancy.urls")),
    # Métier
    path("api/v1/members/", include("apps.members.urls")),
    path("api/v1/savings/", include("apps.savings.urls")),
    path("api/v1/lending/", include("apps.lending.urls")),
    path("api/v1/teller/", include("apps.teller.urls")),
    path("api/v1/accounting/", include("apps.accounting.urls")),
    path("api/v1/regulatory/", include("apps.regulatory.urls")),
    path("api/v1/claims/", include("apps.claims.urls")),
    path("api/v1/documents/", include("apps.documents.urls")),
    # Hérité
    path("api/v1/webhooks/", include("apps.payments.urls_webhooks")),
    path("api/v1/risk/", include("apps.risk.urls")),
    path("api/v1/audit/", include("apps.audit.urls")),
    # Docs
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
]
