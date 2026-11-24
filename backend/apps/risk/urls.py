from django.urls import path

from .views import AMLAlertsView

urlpatterns = [path("aml-alerts/", AMLAlertsView.as_view(), name="aml-alerts")]
