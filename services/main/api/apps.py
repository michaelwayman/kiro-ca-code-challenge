from django.apps import AppConfig


class ApiConfig(AppConfig):
    """DRF serializers, views, filters and pagination for /api/. Filled in by spec 3."""

    name = "api"
    default_auto_field = "django.db.models.BigAutoField"
