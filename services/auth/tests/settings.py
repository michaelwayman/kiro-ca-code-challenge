"""Test settings: safe env defaults, then the real settings module.

Tests run against SQLite so they need no running Postgres. The real settings
code path, env parsing and guards all still run, because this module only
supplies environment values before importing ``config.settings``.
"""

import os

os.environ.setdefault("DJANGO_SECRET_KEY", "test-secret-not-the-dev-placeholder")
os.environ.setdefault("DJANGO_DEBUG", "0")
os.environ.setdefault("AUTH_DATABASE_URL", "sqlite:///:memory:")

from config.settings import *  # noqa: F403 — re-export the real settings unchanged
from config.settings import BASE_DIR

# Tests never run `collectstatic`: use the non-manifest storage, so `{% static %}` works without
# a manifest, and point WhiteNoise's root at a directory that exists.
STORAGES = {
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
STATIC_ROOT = BASE_DIR / "tests"
