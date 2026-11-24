import os
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from channels.security.websocket import AllowedHostsOriginValidator
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.prod")
django_asgi_app = get_asgi_application()
# websocket_urlpatterns = [] (Phase 01 - Purge Commerce)

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    # "websocket": ... (Désactivé temporairement en Phase 01)
})
