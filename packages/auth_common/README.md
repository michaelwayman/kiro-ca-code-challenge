# auth-common

The shared library for the main app and the auth service (Pillar 6). It holds **only** code both services use (D-006):

- the claims model and the role/permission vocabulary;
- the deterministic WP-user → UUID mapping (D-021);
- JWT verification behind a `KeyProvider` seam;
- an optional DRF adapter (`auth-common[drf]`).

The core modules never import Django and need no network. Token issuing, password hashing and JWKS-over-HTTP fetching deliberately live in the services, not here (D-006, D-034).

## Development

```bash
uv sync                 # core + dev tools
uv run pytest
uv run mypy
uv run ruff check && uv run ruff format --check
```

## Versioning

SemVer, with changes recorded in `CHANGELOG.md` (D-016).

**Releasing:** bump `version` here, add a `## X.Y.Z` entry to `CHANGELOG.md`, then run `make release-auth-common` from the repo root. It runs this package's quality gate and builds an immutable wheel into `packages/wheelhouse/`. It refuses to overwrite a version that's already released.

**Consuming:** each service pins **one released wheel**:

```toml
[tool.uv.sources]
auth-common = { path = "../../packages/wheelhouse/auth_common-X.Y.Z-py3-none-any.whl" }
```

To upgrade a service, change its path and run `uv lock`. Older wheels stay in the wheelhouse, so another service can stay on its version (D-003 amendment 2). Services never point at this source directory: uv ignores version pins for source paths, so every service would silently run whatever is checked out here.
