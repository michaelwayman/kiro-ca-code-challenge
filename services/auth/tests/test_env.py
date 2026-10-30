"""config.env: typed, fail-fast parsing (Req 10.1, 10.3) and the dev-secret guard (Req 10.4)."""

from pathlib import Path

import pytest
from django.core.exceptions import ImproperlyConfigured

from config import env


def test_env_str_returns_value_default_or_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("X_STR", " value ")
    assert env.env_str("X_STR") == "value"
    monkeypatch.delenv("X_STR")
    assert env.env_str("X_STR", default="fallback") == "fallback"
    with pytest.raises(ImproperlyConfigured, match="X_STR is required"):
        env.env_str("X_STR")


def test_empty_string_counts_as_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("X_EMPTY", "  ")
    assert env.env_str("X_EMPTY", default="fallback") == "fallback"
    with pytest.raises(ImproperlyConfigured, match="X_EMPTY is required"):
        env.env_str("X_EMPTY")


def test_env_int_parses_and_names_bad_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("X_INT", "42")
    assert env.env_int("X_INT") == 42
    monkeypatch.setenv("X_INT", "forty-two")
    with pytest.raises(ImproperlyConfigured, match="X_INT must be an integer"):
        env.env_int("X_INT")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("1", True),
        ("true", True),
        ("YES", True),
        ("on", True),
        ("0", False),
        ("False", False),
        ("no", False),
        ("off", False),
    ],
)
def test_env_bool_accepts_common_spellings(
    monkeypatch: pytest.MonkeyPatch, raw: str, expected: bool
) -> None:
    monkeypatch.setenv("X_BOOL", raw)
    assert env.env_bool("X_BOOL") is expected


def test_env_bool_rejects_garbage(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("X_BOOL", "maybe")
    with pytest.raises(ImproperlyConfigured, match="X_BOOL must be a boolean"):
        env.env_bool("X_BOOL")


def test_env_list_splits_and_trims(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("X_LIST", " a, b ,,c ")
    assert env.env_list("X_LIST") == ["a", "b", "c"]


def test_env_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("X_PATH", "/run/keys/signing.pem")
    assert env.env_path("X_PATH") == Path("/run/keys/signing.pem")


def test_dev_secret_refused_when_debug_off() -> None:
    with pytest.raises(ImproperlyConfigured, match="DJANGO_SECRET_KEY is the development"):
        env.require_safe_secret(env.DEV_SECRET_KEY, debug=False)


def test_dev_secret_allowed_in_debug_and_real_secret_allowed_always() -> None:
    env.require_safe_secret(env.DEV_SECRET_KEY, debug=True)
    env.require_safe_secret("a-real-secret", debug=False)
