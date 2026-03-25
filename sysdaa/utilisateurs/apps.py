from django.apps import AppConfig


class UtilisateursConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "utilisateurs"
    verbose_name = "Utilisateurs"

    def ready(self):
        from . import signals  # noqa: F401