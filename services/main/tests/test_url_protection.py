"""Every route is either explicitly public or rejects anonymous requests (design §6.1).

This is the guard behind "secure by default": a route someone forgets to protect fails
here instead of shipping open. A route can only become public by being added to
``PUBLIC_ROUTES``, which makes that choice visible in code review.
"""

from collections.abc import Iterator

import pytest
from django.test import Client
from django.urls import URLPattern, URLResolver, get_resolver, reverse
from pytest_django.fixtures import Settings

# Route name → why it's public. Spec 3 adds the public API routes; spec 4 adds the pages.
PUBLIC_ROUTES: dict[str, str] = {
    "health-live": "liveness probe (Req 11.1)",
    "health-ready": "readiness probe (Req 11.1)",
}

# Sample values for path converters, so every route can be reversed and requested.
SAMPLE_KWARGS_BY_CONVERTER: dict[str, object] = {"SlugConverter": "sample-slug", "IntConverter": 1}
METHODS = ("get", "post", "put", "patch", "delete")
REJECTED = frozenset({401, 403, 405})


def _iter_patterns(
    patterns: list[URLPattern | URLResolver], namespace: str = ""
) -> Iterator[tuple[str, URLPattern]]:
    for entry in patterns:
        if isinstance(entry, URLResolver):
            ns = f"{namespace}{entry.namespace}:" if entry.namespace else namespace
            yield from _iter_patterns(entry.url_patterns, ns)
        else:
            yield namespace, entry


def unprotected_routes(urlconf: str | None, public: dict[str, str]) -> list[str]:
    """Return a description of every non-public route that answers an anonymous request
    with anything other than 401/403/405, for any HTTP method."""
    offenders: list[str] = []
    for namespace, pattern in _iter_patterns(get_resolver(urlconf).url_patterns):
        if not pattern.name:
            offenders.append(f"unnamed route {pattern.pattern} (every route must be named)")
            continue
        name = f"{namespace}{pattern.name}"
        if name in public:
            continue
        converters = getattr(pattern.pattern, "converters", {})
        kwargs = {
            arg: SAMPLE_KWARGS_BY_CONVERTER[type(conv).__name__] for arg, conv in converters.items()
        }
        url = reverse(name, urlconf=urlconf, kwargs=kwargs)
        for method in METHODS:
            status = getattr(Client(), method)(url).status_code
            if status not in REJECTED:
                offenders.append(f"{method.upper()} {url} ({name}) → {status}")
    return offenders


@pytest.mark.django_db
def test_every_route_is_public_by_choice_or_rejects_anonymous() -> None:
    offenders = unprotected_routes(None, PUBLIC_ROUTES)
    assert not offenders, (
        "Routes answered an anonymous request. Protect them, or add them to PUBLIC_ROUTES "
        "with a reason:\n  " + "\n  ".join(offenders)
    )


def test_public_route_list_has_no_stale_entries() -> None:
    names = {f"{ns}{p.name}" for ns, p in _iter_patterns(get_resolver().url_patterns) if p.name}
    stale = set(PUBLIC_ROUTES) - names
    assert not stale, f"PUBLIC_ROUTES lists routes that no longer exist: {sorted(stale)}"


@pytest.mark.django_db
def test_guard_catches_an_unprotected_route(settings: Settings) -> None:
    """The guard itself works: an AllowAny view that isn't listed is reported, while a
    view relying on the secure DRF defaults is not."""
    urlconf = "tests.urls_guard_fixture"
    settings.ROOT_URLCONF = urlconf
    offenders = unprotected_routes(urlconf, public={})
    assert any("(open-by-mistake)" in o for o in offenders), offenders
    assert not any("(protected-by-default)" in o for o in offenders), offenders
