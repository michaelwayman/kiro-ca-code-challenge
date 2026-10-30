"""The vite_asset tag: built manifest, dev server, and failure modes (design §7)."""

import json
import os
from pathlib import Path

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.template import Context, Template
from pytest_django.fixtures import Settings

MANIFEST = {
    "src/main.tsx": {
        "file": "assets/main-AbC123.js",
        "src": "src/main.tsx",
        "isEntry": True,
        "css": ["assets/main-Def456.css"],
        "imports": ["_vendor-Ghi789.js"],
    },
    "_vendor-Ghi789.js": {
        "file": "assets/vendor-Ghi789.js",
        "css": ["assets/vendor-Jkl012.css"],
    },
}


def _render(entry: str = "src/main.tsx") -> str:
    return Template('{% load vite %}{% vite_asset "' + entry + '" %}').render(Context())


@pytest.fixture
def built(settings: Settings, tmp_path: Path) -> Path:
    manifest = tmp_path / "brandlist" / ".vite" / "manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps(MANIFEST))
    settings.FRONTEND_DIST_DIR = tmp_path
    settings.VITE_DEV_SERVER = ""
    return manifest


@pytest.mark.usefixtures("built")
def test_built_mode_emits_css_preload_and_script_through_static() -> None:
    html = _render()
    assert '<link rel="stylesheet" href="/static/brandlist/assets/main-Def456.css">' in html
    # CSS from imported chunks is included too, or code-split styles would go missing.
    assert '<link rel="stylesheet" href="/static/brandlist/assets/vendor-Jkl012.css">' in html
    assert '<link rel="modulepreload" href="/static/brandlist/assets/vendor-Ghi789.js">' in html
    assert '<script type="module" src="/static/brandlist/assets/main-AbC123.js"></script>' in html


def test_rebuilt_manifest_is_picked_up_without_restart(built: Path) -> None:
    assert "main-AbC123.js" in _render()
    rebuilt = json.loads(built.read_text())
    rebuilt["src/main.tsx"]["file"] = "assets/main-NeW999.js"
    built.write_text(json.dumps(rebuilt))
    # Bump the mtime explicitly: two writes within the filesystem's timestamp resolution
    # would otherwise look unchanged.
    stat = built.stat()
    os.utime(built, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000))
    assert "main-NeW999.js" in _render()


def test_dev_server_mode_emits_refresh_preamble_client_and_entry(settings: Settings) -> None:
    settings.VITE_DEV_SERVER = "http://localhost:5173/"
    html = _render()
    assert 'import RefreshRuntime from "http://localhost:5173/@react-refresh"' in html
    assert '<script type="module" src="http://localhost:5173/@vite/client"></script>' in html
    assert '<script type="module" src="http://localhost:5173/src/main.tsx"></script>' in html


def test_missing_manifest_raises_in_debug(settings: Settings, tmp_path: Path) -> None:
    settings.FRONTEND_DIST_DIR = tmp_path
    settings.VITE_DEV_SERVER = ""
    settings.DEBUG = True
    with pytest.raises(ImproperlyConfigured, match="Vite manifest not found"):
        _render()


def test_missing_manifest_renders_nothing_and_logs_in_production(
    settings: Settings, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    settings.FRONTEND_DIST_DIR = tmp_path
    settings.VITE_DEV_SERVER = ""
    settings.DEBUG = False
    assert _render() == ""
    assert "could not render Vite entry" in caplog.text


@pytest.mark.usefixtures("built")
def test_unknown_entry_raises_in_debug(settings: Settings) -> None:
    settings.DEBUG = True
    with pytest.raises(ImproperlyConfigured, match="not in the manifest"):
        _render("src/missing.tsx")
