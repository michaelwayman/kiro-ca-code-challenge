# Requirements: System Architecture (spec 0)

## Introduction

This spec defines the system-level architecture of the WordPress → Django migration:

- which services exist and what each owns;
- how they're deployed with Docker Compose;
- how authentication tokens flow between them;
- the shared library's public contract;
- how the system behaves when a dependency fails;
- how the system is configured, started and operated locally.

It is the contract later specs build on:

| Spec | Covers |
|---|---|
| 1 `domain-model-and-migration` | models and the WP import |
| 2 `auth-service-and-shared-lib` | auth service and `auth_common` |
| 3 `brands-api` | the brands and industries API |
| 4 `server-rendered-pages-and-scss` | server-rendered pages and the SCSS tree |
| 5 `brandlist-component` | `<BrandList />` |

Those specs reference this one instead of restating it. Internal details (model fields, serializers, component internals) belong to them, not here.

Sources of truth:

- `CHALLENGE.md`
- `.kiro/steering/decisions.md` (cited as D-NNN)
- `.kiro/steering/{product,tech,structure,frontend}.md`
- the discovery report `.agents/tasks/wp-discovery.md`

## Glossary

| Term | Meaning |
|---|---|
| **Main app** | The Django project in `services/main/` that replaces the WP site: content models, WP content import, server-rendered pages, `/api/brands/`, `/api/industries/`, and the protected `PATCH` endpoint. |
| **Auth service** | The Django project in `services/auth/` that owns users, credentials, roles/permissions, and token issuing (D-004, D-005, D-007). |
| **`auth_common`** | The shared, installable Python package in `packages/auth_common/` used by both services (D-006). |
| **WP source** | The existing, unchanged WordPress stack (`db` MariaDB, `wordpress`, `phpmyadmin`, `wpcli`) in `docker-compose.yml`. It's read-only input for the importers. |
| **Access token** | A short-lived RS256 JWT issued by the auth service and verified locally by consumers (D-004). |
| **Refresh token** | A longer-lived opaque token stored server-side in the auth DB, exchanged for new access tokens (D-004). |
| **JWKS** | The JSON Web Key Set the auth service publishes with its public signing key(s). |
| **Consumer** | Any service that verifies access tokens. Today that's the main app (and the auth service for its own protected endpoints). |
| **Stack** | All services defined in `docker-compose.yml`. |

## Requirements

### Requirement 1: Service inventory and ownership

**User story:** As a reviewer, I want each service's responsibilities to be explicit and non-overlapping, so that I can evaluate the service boundary and see that no data has two owners.

#### Acceptance criteria

1. THE system SHALL consist of exactly these application services:
   - the main app;
   - the auth service;
   - one PostgreSQL database per service (`main-db`, `auth-db`; D-002);
   - plus the unchanged WP source services.
2. THE auth service SHALL be the only component that stores user credentials, password hashes, roles, role→permission mappings or refresh tokens, and the only one that issues access tokens (D-004, D-005, D-007).
3. THE main app SHALL own brands, industries, reviews and reviewer profiles. It SHALL NOT store passwords, password hashes, roles or permission assignments (D-005, D-009).
4. THE main app SHALL identify users only by the auth-service user UUID (the token `sub`), via `Reviewer.auth_user_id` (D-009, D-021).
5. THE main app SHALL NOT connect to `auth-db`, and THE auth service SHALL NOT connect to `main-db` (D-002).
6. THE main app and the auth service SHALL NOT import Python code from each other. Code they share SHALL come only from the installed `auth_common` package (structure.md).
7. WHERE a capability is needed by both services, THE system SHALL place it in `auth_common` only if both services actually use it (D-006).

### Requirement 2: Container topology and local deployment

**User story:** As a developer, I want the whole system to start with one command from a clean checkout, so that reviewers can run it without extra setup.

#### Acceptance criteria

1. THE stack SHALL be defined in the existing `docker-compose.yml` (production-like base), plus a `docker-compose.override.yml` holding only dev-mode differences (D-033). New services are added without changing the WP source services' definitions except to join a shared network (tech.md).
2. WHEN a developer runs `docker compose up` (or `make up`), THE stack SHALL start in dev mode (`DEBUG=1`, runserver, live-reloading bind mounts). WHEN the developer runs `make up-prod`, THE stack SHALL start from the base file alone (`DEBUG=0`, gunicorn, code baked into images) (D-033).
3. WHEN a developer runs the documented start command from a clean checkout with Docker as the only prerequisite, THE stack SHALL build and start the main app, auth service, `main-db`, `auth-db` and the WP source, with no manual steps beyond copying `.env.example` to `.env`.
4. THE main app SHALL be reachable from the host at `http://localhost:8000`, and THE auth service at `http://localhost:8001` (tech.md ports).
5. THE main app SHALL reach the auth service over the Compose network by service name (e.g. `http://auth:8000`), never via `localhost`.
6. THE main app and auth service containers SHALL each wait for their own database to be healthy before starting, and SHALL apply their Django migrations on start.
7. THE main app SHALL NOT need the auth service to be running in order to start (Requirement 6.1).
8. THE `main-db` data, `auth-db` data and the auth signing key (`auth_keys`, D-031) SHALL persist in named volumes across `docker compose down` / `up`. The documented reset command SHALL remove them.
9. EACH service image SHALL install `auth_common` from the specific released wheel in `packages/wheelhouse/` that the service pins, verified by the sha256 in that service's lockfile (D-003 amendment 2).

### Requirement 3: Data migration orchestration

**User story:** As an operator, I want to populate both services from WordPress with documented, re-runnable commands, so that migration is safe to repeat.

#### Acceptance criteria

1. THE main app SHALL provide `manage.py import_wp`, and THE auth service SHALL provide `manage.py import_wp_users`. Each reads the WP source MariaDB directly (D-007, D-011).
2. THE importers SHALL run their source reads inside a read-only transaction (`START TRANSACTION READ ONLY`), so that they cannot modify WP data even though the WP DB credentials allow writes.
3. THE two importers SHALL be runnable in either order, and SHALL produce the same linked result. User identity is derived independently by both via `auth_common.identity.wp_user_uuid()` (D-021).
4. WHEN an importer is run again against unchanged WP data, THE importer SHALL produce no duplicate rows and SHALL report zero created rows (D-011).
5. IF source data violates an import invariant (D-011 validation: zero or several industries per brand, or a review with no valid brand), THEN THE importer SHALL abort without writing anything and report the offending WP ids.
6. THE system SHALL provide one documented convenience command (a Make target) that runs both importers in sequence.
7. THE importers SHALL NOT run automatically on container start. Migration is an explicit operator action.

### Requirement 4: Authentication flow

**User story:** As an API client, I want to exchange credentials for a token and use it against the main app, so that I can call protected endpoints without a login UI.

#### Acceptance criteria

1. THE auth service SHALL expose an endpoint that exchanges a username and password for an access token and a refresh token (D-004).
2. THE auth service SHALL expose an endpoint that exchanges a valid refresh token for a new access token, re-reading the user's **current** roles and permissions at that moment (D-004).
3. THE auth service SHALL expose an endpoint that revokes a refresh token (logout). WHEN a revoked refresh token is presented, THE auth service SHALL reject it.
4. THE auth service SHALL publish its public signing key(s) as a JWKS at `/.well-known/jwks.json`, each key identified by a `kid` (D-004).
5. THE access token SHALL be an RS256 JWT carrying at least `iss`, `aud`, `sub` (user UUID), `roles`, `perms`, `iat`, `exp`, `jti` and `ver` (D-004, D-016).
6. THE access token lifetime SHALL be short (5–10 minutes; exact value set in spec 2) (D-004).
7. WHEN a request to a protected main-app endpoint carries a valid access token with the required permission, THE main app SHALL authorize it **without a network call** to the auth service, using a cached JWKS (D-004).
8. IF a request to a protected endpoint has a missing, malformed, expired or wrongly signed token, or a wrong `iss`/`aud`, THEN THE main app SHALL respond `401` with a `WWW-Authenticate: Bearer` header (D-001).
9. IF a request carries a valid token that lacks the required permission, THEN THE main app SHALL respond `403` (D-015).
10. THE main app SHALL authorize by **permission strings** (e.g. `brands.change_description`), never by role names (D-005).
11. THE public main-app routes (server-rendered pages, `GET /api/brands/`, `GET /api/industries/`) SHALL NOT require a token, and SHALL ignore an invalid one rather than rejecting the request.
12. THE system SHALL allow a reviewer to obtain a token with `curl` and through Swagger UI or the DRF browsable API, without a login UI (product.md).

### Requirement 5: Signing keys

**User story:** As an operator, I want signing keys handled safely and rotatably, so that a leaked repository never leaks the ability to mint tokens.

#### Acceptance criteria

1. THE RSA private signing key SHALL NOT be committed to the repository, written into an image, or logged (D-031).
2. THE auth service SHALL load exactly one private key from the PEM file at `AUTH_SIGNING_KEY_PATH` (default `/run/keys/signing.pem`, on the `auth_keys` named volume) (D-031).
3. WHEN the auth service container starts WHILE `DEBUG` is enabled AND no key file exists, THE entrypoint SHALL run `manage.py ensure_signing_key` **before** starting the server. It generates a 2048-bit RSA key and writes it atomically with `0600` permissions, so that tokens survive restarts and parallel server workers never generate competing keys (D-031).
4. IF `DEBUG` is disabled AND the key file is missing or unreadable, THEN THE auth service SHALL refuse to start with an error naming `AUTH_SIGNING_KEY_PATH`. It SHALL NOT generate a key (D-031).
5. THE key's `kid` SHALL be derived from the public key's RFC 7638 JWK thumbprint, not configured separately. THE access token header and the JWKS entry SHALL carry the same `kid` (D-031).
6. THE JWKS SHALL publish exactly one public key. Key rotation is out of scope and is documented in the README as a "with more time" item (D-031).
7. THE main app SHALL never hold the private key. It only verifies (D-004).

### Requirement 6: Behavior when a dependency is unavailable

**User story:** As a site visitor or editor, I want the main site to keep working when the auth service is down, so that an auth outage doesn't become a site outage.

#### Acceptance criteria

1. WHILE the auth service is unavailable, THE main app SHALL continue serving all public pages and public API endpoints normally.
2. WHILE the auth service is unavailable AND the main app holds a cached JWKS that hasn't expired, THE main app SHALL continue to accept valid unexpired access tokens on protected endpoints (D-004).
3. WHILE the auth service is unavailable, login and refresh SHALL fail. Already-issued access tokens SHALL keep working until `exp`.
4. IF a token's `kid` is not in the cached JWKS, THEN THE main app SHALL refetch the JWKS, rate-limited so that a flood of bad tokens can't amplify into a flood of JWKS requests. IF the `kid` is still unknown, THEN it SHALL respond `401`.
5. IF the main app has no usable JWKS (never fetched, or expired, and the auth service is unreachable), THEN protected endpoints SHALL respond `503` with a clear error body rather than `401`, so that clients can tell "auth unavailable" from "bad credentials".
6. THE main app SHALL bound JWKS cache staleness with a configured maximum age (value set in spec 2).

### Requirement 7: Revocation and role changes

**User story:** As an administrator, I want role changes and revocations to take effect within a known, documented time, so that I can reason about access after I change it.

#### Acceptance criteria

1. WHEN a user's roles change in the auth service, THE change SHALL take effect for that user no later than their next token refresh, and at most one access-token lifetime later (D-004).
2. WHEN a refresh token is revoked, THE auth service SHALL refuse to issue new access tokens with it. Existing access tokens SHALL remain valid until `exp` (documented trade-off, D-004).
3. THE README SHALL state the maximum access window after a role change or revocation (equal to the access-token lifetime) and how immediate revocation would be added (D-004).

### Requirement 8: Shared library contract (`auth_common`)

**User story:** As a maintainer of either service, I want a small, versioned, typed shared library with a stable public API, so that I can upgrade it in one service without breaking the other.

#### Acceptance criteria

1. THE `auth_common` package SHALL have its own `pyproject.toml`, a semantic version, a CHANGELOG, a `py.typed` marker, and tests that run without either Django project (D-006, D-016, D-028).
2. THE `auth_common` public API SHALL be limited to:
   - the claims model and role/permission constants;
   - `identity.wp_user_uuid`;
   - JWT/JWKS verification;
   - an optional DRF adapter (authentication class, non-model token user, permission class) (D-006, D-001, D-021).
3. THE `auth_common` core (everything except the DRF adapter) SHALL be importable and testable without Django installed (tech.md).
4. THE `auth_common` package SHALL NOT contain token issuing, password hashing, user models, HTTP clients or service settings (D-006, D-007).
5. WHEN the token claim format changes incompatibly, THE system SHALL follow expand → migrate → contract using the `ver` claim, so that the two services are never required to deploy at the same moment (D-016).
6. EACH service SHALL pin one released `auth_common` wheel and SHALL be upgradable independently: two services SHALL be able to run different released versions at the same time (D-003, D-016).
7. A released `auth_common` version SHALL be immutable: the release command SHALL refuse to rebuild or overwrite an existing version (D-003 amendment 2).

### Requirement 9: Request routing and frontend delivery

**User story:** As a visitor, I want the site, its API and the React component served from one origin, so that there's no CORS configuration or cross-origin auth to get wrong.

#### Acceptance criteria

1. THE main app SHALL serve server-rendered pages, its JSON API under `/api/`, its static assets (compiled SCSS, built `<BrandList />` bundle), and its OpenAPI schema and docs from a single origin (`localhost:8000`).
2. THE browser SHALL never call the auth service directly. Only API clients (curl, Swagger) do. Therefore THE main app SHALL NOT need CORS for its own pages.
3. THE main app image SHALL contain the compiled CSS and the production build of `<BrandList />`, so that the container works without Node on the host (D-020).
4. WHERE a developer runs the Vite dev server, THE Vite dev server SHALL proxy `/api` to the main app, so that the component works in isolation with no CORS (D-020).
5. THE `/brand/` page SHALL work without JavaScript and SHALL be progressively enhanced by `<BrandList />` (D-022).
6. EACH service SHALL publish an OpenAPI schema generated by `drf-spectacular` (D-001). The main app's schema SHALL be the input for generated frontend types (D-023).

### Requirement 10: Configuration and secrets

**User story:** As an operator, I want all configuration in environment variables with safe local defaults, so that the same images run anywhere and no secret is committed.

#### Acceptance criteria

1. EACH service SHALL read all deployment-specific configuration from environment variables, parsed once into typed settings (tech.md, D-028).
2. THE `.env.example` file SHALL contain working local defaults for every variable the stack needs, with no real secrets.
3. IF a required setting is missing or invalid at startup, THEN THE service SHALL fail fast with an error naming the setting.
4. THE services SHALL refuse to start with `DEBUG` disabled while using a known development secret.
5. Development-only conveniences (e.g. `set_dev_password`, D-007) SHALL refuse to run unless `DEBUG` is enabled.

### Requirement 11: Health and observability

**User story:** As an operator, I want health endpoints and safe logs, so that I can tell what's running and diagnose problems without leaking secrets.

#### Acceptance criteria

1. EACH service SHALL expose an unauthenticated liveness endpoint that returns `200` when the process is up, and a readiness check that includes its own database. Compose healthchecks SHALL use them.
2. THE main app's readiness SHALL NOT depend on the auth service being available (Requirement 6.1).
3. EACH service SHALL log to stdout/stderr.
4. THE services SHALL NOT log passwords, password hashes, access tokens, refresh tokens or private keys, including in error output and in the importers' reports.
5. WHEN an authentication or authorization check fails, THE main app SHALL log the reason category (expired, bad signature, unknown `kid`, missing permission, JWKS unavailable) without the token value.

### Requirement 12: Quality gates (system level)

**User story:** As a reviewer, I want every component to meet the same automated quality bar, so that "done" means the same thing across the repo.

#### Acceptance criteria

1. EACH Python component (main app, auth service, `auth_common`) SHALL pass `ruff check`, `ruff format --check`, `mypy` (strict, D-028) and `pytest` (tech.md).
2. THE frontend SHALL pass the `frontend.md` §7 definition of done.
3. THE repository SHALL provide one documented command per component to run its checks, and one command that runs all of them.
4. THE system SHALL include an end-to-end check against the running stack covering: login → token → `PATCH /api/brands/<slug>/` succeeds for an editor, returns `403` for a reader and `401` without a token, and public endpoints work with the auth service stopped.

## Out of scope for this spec

- Model fields, the import mapping and the `with_stats()` internals (spec 1).
- Endpoint paths and payloads of the auth service beyond the capabilities above, plus token TTL values, JWKS cache values and the hasher internals (spec 2).
- Brand and industry API payloads, filters and pagination (spec 3, already fixed by D-013, D-027).
- Page templates and the SCSS tree (spec 4). `<BrandList />` internals (spec 5).
- Production deployment (TLS, reverse proxy, secret managers, horizontal scaling). This is local Docker Compose only. Production notes may appear in the README's "with more time" section.
- Immediate token revocation (denylist). Documented only, per D-004.
- Signing-key rotation (multiple keys in the JWKS). Documented only, per D-031.

## Choices in this draft that weren't explicit decisions yet

All accepted by the owner on 2026-10-29: item 3 as D-031, the rest as D-032.

1. **Importers read inside `START TRANSACTION READ ONLY`** (Req 3.2), instead of creating a separate read-only MariaDB user. The WP services stay untouched, as tech.md requires.
2. **Importers never run on container start** (Req 3.7). They're explicit operator commands, plus one Make target that runs both.
3. ~~Dev signing key handling~~: **decided** as D-031 (single key file, dev-only generation in the entrypoint, thumbprint `kid`, no rotation) (Req 5).
4. **`503` (not `401`) when the main app has no usable JWKS** (Req 6.5), so clients can tell an auth outage from bad credentials.
5. **Public endpoints ignore invalid tokens** instead of rejecting them (Req 4.11).
6. **Browser never talks to the auth service; one origin for the site** (Req 9.1–9.2), so no CORS configuration is needed.
7. **Main app image builds the frontend** (Node build stage) so the container is self-contained (Req 9.3).
8. **Containers apply migrations on start** (Req 2.6).
9. **Fail-fast typed settings, and refusing to run with a dev secret when `DEBUG` is off** (Req 10.3–10.4).
10. **A system-level end-to-end auth check**, including "public endpoints work with the auth service stopped" (Req 12.4).
