from django.apps import AppConfig


class PagesConfig(AppConfig):
    """Server-rendered pages and frontend asset loading. Pages are filled in by spec 4."""

    name = "pages"
    default_auto_field = "django.db.models.BigAutoField"
