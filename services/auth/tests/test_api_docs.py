"""OpenAPI endpoints exist only in DEBUG (D-034.9); the schema is always generatable (Req 9.6)."""

import importlib
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from django.core.management import call_command
from django.test import Client
from django.urls import clear_url_caches
from pytest_django.fixtures import Settings

import config.urls


@pytest.fixture
def set_debug(settings: Settings) -> Iterator[Callable[[bool], None]]:
    """Set DEBUG and re-import the URLconf, since urls.py reads DEBUG at import time."""

    def _apply(debug: bool) -> None:
        settings.DEBUG = debug
        importlib.reload(config.urls)
        clear_url_caches()

    yield _apply
    _apply(False)  # leave the default (DEBUG off) URLconf for other tests


def test_docs_absent_when_debug_off(set_debug: Callable[[bool], None]) -> None:
    set_debug(False)
    client = Client()
    assert client.get("/api/docs/").status_code == 404
    assert client.get("/api/schema/").status_code == 404


def test_docs_served_when_debug_on(set_debug: Callable[[bool], None]) -> None:
    set_debug(True)
    client = Client()
    assert client.get("/api/schema/").status_code == 200
    assert client.get("/api/docs/").status_code == 200


def test_schema_generatable_via_management_command(tmp_path: Path) -> None:
    out = tmp_path / "schema.yaml"
    call_command("spectacular", "--file", str(out), "--validate")
    assert out.read_text().startswith("openapi:")
