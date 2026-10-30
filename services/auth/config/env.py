"""Typed, fail-fast environment parsing (Req 10.1, 10.3; D-028, D-034).

Every setting is read through these helpers exactly once, in ``settings.py``.
A missing or invalid value raises ``ImproperlyConfigured`` naming the variable,
so the process fails at startup instead of misbehaving later.

An empty string counts as "not set", so ``VAR=`` in ``.env`` means "use the default".
"""

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

# The placeholder secret shipped in .env.example. Refused whenever DEBUG is off (Req 10.4).
DEV_SECRET_KEY = "dev-insecure-change-me"

_TRUE = frozenset({"1", "true", "yes", "on"})
_FALSE = frozenset({"0", "false", "no", "off"})


def _raw(name: str) -> str | None:
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return None
    return value.strip()


def env_str(name: str, default: str | None = None) -> str:
    value = _raw(name)
    if value is not None:
        return value
    if default is not None:
        return default
    raise ImproperlyConfigured(f"{name} is required but not set.")


def env_int(name: str, default: int | None = None) -> int:
    value = _raw(name)
    if value is None:
        if default is not None:
            return default
        raise ImproperlyConfigured(f"{name} is required but not set.")
    try:
        return int(value)
    except ValueError:
        raise ImproperlyConfigured(f"{name} must be an integer, got {value!r}.") from None


def env_bool(name: str, default: bool | None = None) -> bool:
    value = _raw(name)
    if value is None:
        if default is not None:
            return default
        raise ImproperlyConfigured(f"{name} is required but not set.")
    lowered = value.lower()
    if lowered in _TRUE:
        return True
    if lowered in _FALSE:
        return False
    raise ImproperlyConfigured(
        f"{name} must be a boolean (one of {sorted(_TRUE | _FALSE)}), got {value!r}."
    )


def env_list(name: str, default: list[str] | None = None) -> list[str]:
    """Comma-separated list; surrounding whitespace and empty items are dropped."""
    value = _raw(name)
    if value is None:
        if default is not None:
            return list(default)
        raise ImproperlyConfigured(f"{name} is required but not set.")
    return [item.strip() for item in value.split(",") if item.strip()]


def env_path(name: str, default: Path | None = None) -> Path:
    value = _raw(name)
    if value is not None:
        return Path(value)
    if default is not None:
        return default
    raise ImproperlyConfigured(f"{name} is required but not set.")


def require_safe_secret(secret_key: str, *, debug: bool) -> None:
    """Refuse the known development secret outside DEBUG (Req 10.4)."""
    if not debug and secret_key == DEV_SECRET_KEY:
        raise ImproperlyConfigured(
            "DJANGO_SECRET_KEY is the development placeholder, which is refused when "
            "DJANGO_DEBUG is off. Set a real secret (e.g. `openssl rand -hex 32`)."
        )
