# Tech stack

> Status: **Accepted**. Rationale and alternatives live in `decisions.md`. Framework per D-001, SCSS conventions per D-019.

## Existing (do not change)

- Source WP stack in `docker-compose.yml`: `db` (MariaDB 11), `wordpress` (8080), `phpmyadmin` (8081), `wpcli` (tools profile).
- Source data: `db/dump.sql`, schema in `wp-content/mu-plugins/cpt.php` and `acf-fields.php`.
- New services are **added** to the existing `docker-compose.yml`. Don't edit the WP services except to share the network.

## Backend (main app and auth service)

| Concern | Choice |
|---|---|
| Language | Python 3.12 |
| Framework | Django 5.2 LTS |
| API | Django REST Framework 3.x. `drf-spectacular` for OpenAPI (`/api/schema/`, Swagger at `/api/docs/`). `django-filter` for filtering. **Not** Django Ninja or `djangorestframework-simplejwt` (D-001) |
| Databases | PostgreSQL 16, **one container per service** (`main-db`, `auth-db`) |
| Tokens | JWT, RS256. Auth service signs; main app verifies locally via JWKS (see D-004) |
| JWT lib | PyJWT (with `cryptography`) |
| App DB driver | `psycopg[binary]` 3 (Postgres) |
| Source DB driver (import only) | `PyMySQL` (pure Python), used as a plain DB-API connection outside Django `DATABASES`, in both services' importers (D-034) |
| Process server | gunicorn (production-like mode); `runserver` in dev mode (D-033) |
| Static files | WhiteNoise, including `whitenoise.runserver_nostatic` in dev (D-033, D-034) |
| Settings | small typed `config/env.py` per service + `dj-database-url`. **Not** `django-environ` (D-034) |
| WP password verification | `bcrypt` (auth service only) + stdlib phpass in a custom hasher (D-007). **Not** `passlib` |
| HTML sanitizing | `nh3` (main app only), allow-list sanitizer applied at import (D-030). **Not** `bleach` (deprecated) |
| Tests | pytest + pytest-django; API tests via DRF's `APIClient` |
| Lint/format | ruff (lint + format; includes `ANN` annotation rules) |
| Type checking | mypy, `strict = true`, with `django-stubs` + `djangorestframework-stubs` and their mypy plugins. Migrations excluded. `django-stubs-ext` (small runtime dependency) for `WithAnnotations` and `monkeypatch()` of generic classes (D-028) |
| Packaging | `uv` for envs/locking. Each service has its own `pyproject.toml` + lockfile |

## Shared library

- Lives at `packages/auth_common/`, distribution name `auth-common`, import name `auth_common`.
- Pure-Python core (claims parsing, JWT verification, role/permission checks) with **no Django import at module top level**.
- DRF integration in `auth_common.drf`, behind an optional extra `auth-common[drf]`. It contains `JWTAuthentication(BaseAuthentication)` (implements `authenticate_header()` so failures are 401, not 403), a non-model `TokenUser`, and `HasPermissions(BasePermission)`, which reads `view.required_permissions`.
- Semantic versioning. Released with `make release-auth-common` as immutable wheels into `packages/wheelhouse/` (committed). Each service pins one wheel via `[tool.uv.sources] auth-common = { path = "../../packages/wheelhouse/auth_common-X.Y.Z-py3-none-any.whl" }`. **Never** point a service at the library's source directory: uv would ignore the version pin (D-003 amendment 2, D-016).
- Typed package: ships `py.typed` (PEP 561) and passes `mypy --strict` with no exceptions (D-028).
- Tests: pytest. Core tests need no Django. DRF adapter tests use `settings.configure()` in a conftest and DRF's `APIRequestFactory`, not either service's settings.

## Frontend

| Concern | Choice |
|---|---|
| Component | React 19.3 + TypeScript (strict) |
| Build/dev | Vite. Dev server proxies `/api` to the main app |
| Styling | SCSS with BEM naming in ITCSS layers (D-019). Global tree in `frontend/scss/`. `<BrandList />` reuses the global BEM classes for shared UI (`.grid`, `.card` + elements, `.stars`, `.badge`, `.pagination`). CSS Modules (`*.module.scss`) only for BrandList-only pieces, `@use`-ing the shared tokens |
| SCSS compiler | Dart Sass (`sass` npm package), module system only (`@use`/`@forward`, never `@import`) |
| Data fetching | Small typed `fetch` hook with `AbortController` (no data-fetching library unless a decision says otherwise) |
| API types | `openapi-typescript` (dev), generated from the `drf-spectacular` schema into `src/api/schema.gen.ts`, committed, diff-checked (D-023) |
| Tests | Vitest + React Testing Library + `@testing-library/user-event`; `vitest-axe` for a11y checks; MSW for API mocking (D-024) |
| E2E / visual | Playwright + `@axe-core/playwright`, ≈5 specs against the running stack, screenshots at 360 / 768 / 1280 px (D-025) |
| Lint/format | ESLint (incl. `jsx-a11y`) + Prettier; Stylelint (`stylelint-config-standard-scss`, with its default kebab-case `selector-class-pattern` overridden by the BEM pattern and limits in D-019) |

## Ports (local)

| Service | Port |
|---|---|
| WordPress (existing) | 8080 |
| phpMyAdmin (existing) | 8081 |
| Main Django app | 8000 |
| Auth service | 8001 |
| Vite dev server | 5173 |

## Conventions

- Pin dependency versions exactly in services, dev tools and the frontend. No open ranges. The one exception is `auth_common`'s published metadata, which uses bounded ranges (`>=tested,<next-major`); its `uv.lock` pins exact versions (D-003 amendment).
- Config via environment variables (12-factor). Defaults go in `.env.example`. Never commit secrets or private keys.
- Run tests in single-run mode (`pytest`, `vitest --run`), never watch mode.
- **Backend definition of done:** `ruff check`, `ruff format --check`, `mypy` and `pytest` all pass, for each service and for `auth_common`. Frontend: see `frontend.md` §7.
