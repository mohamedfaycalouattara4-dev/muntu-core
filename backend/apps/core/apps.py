from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"
    label = "core"

    def ready(self) -> None:  # noqa: D401
        # Import side-effects : middleware is auto-loaded; here we just ensure
        # the audit context processor is registered.
        from . import checks  # noqa: F401  contrôles de sécurité au démarrage
        from . import signals  # noqa: F401  pylint: disable=import-outside-toplevel
