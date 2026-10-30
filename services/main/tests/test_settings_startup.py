"""Startup behavior of the real settings module, in a fresh interpreter (Req 10.3, 10.4),
and the structural service boundary (Req 1.3)."""

import os
import subprocess
import sys
from pathlib import Path

from django.conf import settings

SERVICE_DIR = Path(__file__).resolve().parent.parent

BASE_ENV = {
    "DJANGO_SETTINGS_MODULE": "config.settings",
    "MAIN_DATABASE_URL": "sqlite:///:memory:",
}


def _import_settings(extra_env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith(("DJANGO_", "MAIN_"))}
    env.update(BASE_ENV)
    env.update(extra_env)
    return subprocess.run(
        [sys.executable, "-c", "import django; django.setup()"],
        cwd=SERVICE_DIR,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_refuses_dev_secret_when_debug_off() -> None:
    result = _import_settings({"DJANGO_SECRET_KEY": "dev-insecure-change-me", "DJANGO_DEBUG": "0"})
    assert result.returncode != 0
    assert "DJANGO_SECRET_KEY is the development placeholder" in result.stderr


def test_debug_defaults_to_off_so_dev_secret_is_refused_when_unset() -> None:
    result = _import_settings({"DJANGO_SECRET_KEY": "dev-insecure-change-me"})
    assert result.returncode != 0
    assert "DJANGO_SECRET_KEY is the development placeholder" in result.stderr


def test_fails_fast_naming_a_missing_required_setting() -> None:
    result = _import_settings({"DJANGO_SECRET_KEY": "x", "MAIN_DATABASE_URL": ""})
    assert result.returncode != 0
    assert "MAIN_DATABASE_URL is required" in result.stderr


def test_starts_with_dev_secret_in_debug() -> None:
    result = _import_settings({"DJANGO_SECRET_KEY": "dev-insecure-change-me", "DJANGO_DEBUG": "1"})
    assert result.returncode == 0, result.stderr


def test_main_app_has_no_user_or_credential_storage() -> None:
    """Req 1.3 / D-005: identity comes only from verified token claims. Without
    contrib.auth there is no User, Group or Permission table to put credentials in."""
    assert "django.contrib.auth" not in settings.INSTALLED_APPS
    assert "django.contrib.sessions" not in settings.INSTALLED_APPS
    assert "django.contrib.admin" not in settings.INSTALLED_APPS
