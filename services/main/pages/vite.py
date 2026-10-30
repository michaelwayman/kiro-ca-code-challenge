"""Render the <script>/<link> tags for a Vite entry point (design §7, D-034.8).

A ~small replacement for `django-vite`, covering exactly two cases:

* **Dev** (``VITE_DEV_SERVER`` set): tags pointing at the Vite dev server, including the
  React Fast Refresh preamble that `@vitejs/plugin-react` needs when the HTML page isn't
  served by Vite itself.
* **Built** (default): tags for the hashed files listed in Vite's ``manifest.json``,
  resolved through Django's static storage. That includes CSS from the entry *and* from
  every chunk it imports, plus ``modulepreload`` hints for imported chunks.

The manifest is read from disk (``FRONTEND_DIST_DIR/brandlist/.vite/manifest.json``),
because ``collectstatic`` skips dot-directories. Parsed manifests are cached per file
modification time, so a rebuild is picked up without a restart.
"""

import json
import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import TypedDict

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.templatetags.static import static
from django.utils.html import format_html, format_html_join
from django.utils.safestring import SafeString

logger = logging.getLogger(__name__)

# The bundle's directory inside FRONTEND_DIST_DIR, and its URL prefix under STATIC_URL.
# Vite's `base` must be `${STATIC_URL}brandlist/` for this to line up (task 5).
BUNDLE_DIR = "brandlist"


class ManifestChunk(TypedDict, total=False):
    """One entry in Vite's manifest.json (only the keys we read)."""

    file: str
    css: list[str]
    imports: list[str]
    isEntry: bool


Manifest = dict[str, ManifestChunk]


@dataclass(frozen=True, slots=True)
class EntryAssets:
    script: str
    stylesheets: tuple[str, ...]
    preloads: tuple[str, ...]


def manifest_path() -> Path:
    return Path(settings.FRONTEND_DIST_DIR) / BUNDLE_DIR / ".vite" / "manifest.json"


@lru_cache(maxsize=4)
def _load_manifest(path: Path, mtime_ns: int) -> Manifest:
    """Parse once per (path, mtime). The mtime is part of the cache key on purpose."""
    with path.open(encoding="utf-8") as fh:
        data: Manifest = json.load(fh)
    return data


def load_manifest() -> Manifest:
    path = manifest_path()
    try:
        mtime_ns = path.stat().st_mtime_ns
    except FileNotFoundError:
        raise ImproperlyConfigured(
            f"Vite manifest not found at {path}. Build the frontend (`npm run build` in "
            f"frontend/brandlist/), or set VITE_DEV_SERVER to use the dev server."
        ) from None
    return _load_manifest(path, mtime_ns)


def resolve_entry(manifest: Manifest, entry: str) -> EntryAssets:
    """Collect the entry's script, all CSS it needs, and the chunks worth preloading."""
    if entry not in manifest or "file" not in manifest[entry]:
        raise ImproperlyConfigured(f"Vite entry {entry!r} is not in the manifest.")

    stylesheets: list[str] = []
    preloads: list[str] = []
    seen: set[str] = set()

    def visit(key: str, *, is_root: bool) -> None:
        if key in seen:
            return
        seen.add(key)
        chunk = manifest[key]
        for css in chunk.get("css", []):
            if css not in stylesheets:
                stylesheets.append(css)
        if not is_root and "file" in chunk:
            preloads.append(chunk["file"])
        for imported in chunk.get("imports", []):
            visit(imported, is_root=False)

    visit(entry, is_root=True)
    return EntryAssets(
        script=manifest[entry]["file"],
        stylesheets=tuple(stylesheets),
        preloads=tuple(preloads),
    )


def _static_url(file: str) -> str:
    return static(f"{BUNDLE_DIR}/{file}")


def _dev_tags(dev_server: str, entry: str) -> SafeString:
    base = dev_server.rstrip("/")
    return format_html(
        '<script type="module">'
        'import RefreshRuntime from "{base}/@react-refresh";'
        "RefreshRuntime.injectIntoGlobalHook(window);"
        "window.$RefreshReg$ = () => {{}};"
        "window.$RefreshSig$ = () => (type) => type;"
        "window.__vite_plugin_react_preamble_installed__ = true;"
        "</script>"
        '<script type="module" src="{base}/@vite/client"></script>'
        '<script type="module" src="{base}/{entry}"></script>',
        base=base,
        entry=entry,
    )


def _built_tags(assets: EntryAssets) -> SafeString:
    links = format_html_join(
        "", '<link rel="stylesheet" href="{}">', ((_static_url(c),) for c in assets.stylesheets)
    )
    preloads = format_html_join(
        "", '<link rel="modulepreload" href="{}">', ((_static_url(p),) for p in assets.preloads)
    )
    script = format_html('<script type="module" src="{}"></script>', _static_url(assets.script))
    return format_html("{}{}{}", links, preloads, script)


def render_entry(entry: str) -> SafeString:
    """Tags for ``entry``. A misconfiguration raises in DEBUG; in production it's logged
    and renders nothing, so one broken bundle can't take the whole page down."""
    if settings.VITE_DEV_SERVER:
        return _dev_tags(settings.VITE_DEV_SERVER, entry)
    try:
        return _built_tags(resolve_entry(load_manifest(), entry))
    except ImproperlyConfigured:
        if settings.DEBUG:
            raise
        logger.exception("could not render Vite entry %r", entry)
        return SafeString("")
