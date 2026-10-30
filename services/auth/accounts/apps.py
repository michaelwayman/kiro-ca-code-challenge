from django.apps import AppConfig


class AccountsConfig(AppConfig):
    """Users, credentials, roles/permissions and token issuing. Models are added in spec 2."""

    name = "accounts"
    default_auto_field = "django.db.models.BigAutoField"
