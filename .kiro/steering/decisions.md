---
inclusion: always
---

# Decision log

The single source of truth for architectural choices in this WordPress → Django migration. Specs cite decisions by ID (e.g. "per D-004"). The README's "modeling decisions / AI defaults" section is generated from this file.

## How to use this file (AI assistant rules)

- Follow every `Accepted` decision when writing specs, code, or docs. Cite the ID when a choice depends on it.
- Do not change an `Accepted` decision on your own. If work conflicts with one, stop and flag it. Propose a new or amended entry with `Status: Proposed`.
- New decisions use the template below, get the next free `D-NNN` ID, start as `Proposed`, and go in the matching section.
- Never fill in `_[owner to fill in]_` or `_[reason]_` placeholders. Those are the owner's words.
- WP data facts live in the discovery report at `.agents/tasks/wp-discovery.md`. Read it before writing a spec or importer code that depends on the source data. Use it, not assumptions, when a spec or the importer depends on what the source data looks like. If code meets data that contradicts the report, stop and flag it.
- When an AI suggestion is kept or overridden, log it in the README sections at the bottom.

**Statuses:** `Proposed` (AI-drafted, not yet reviewed) → `Accepted` (owner reviewed and agrees) / `Rejected` / `Superseded by D-xxx`.
**Origin:** `Owner` (owner's call) · `AI default accepted` (AI suggested, owner kept it, with reason) · `AI overridden` (AI suggested X, owner chose Y).

> D-001…D-034 were drafted on 2026-10-29 and are all `Accepted`. D-001, D-007, D-008, D-021, D-027, D-028, D-029, D-030, D-031 and D-033 are owner decisions; the rest are AI defaults the owner accepted. D-003 has two owner amendments. Each entry's `Origin` is authoritative.

## Hard rules (quick reference)

- Django 5.2 LTS + Django REST Framework in both services, with `drf-spectacular` (OpenAPI) and `django-filter`. Not Django Ninja, not `djangorestframework-simplejwt` (D-001).
- Main app and auth service have separate Postgres 16 containers. No cross-DB access (D-002).
- Services get `auth-common` only from one released wheel in `packages/wheelhouse/`, pinned by its path in `[tool.uv.sources]`. Never from the library's source directory. Released wheels are never rebuilt or overwritten (D-003 amendment 2).
- `uv` + `uv.lock` per service, exact version pins for every service and dev/tool dependency. **Exception:** `auth_common`'s published metadata uses bounded ranges; its lockfile is exact (D-003 amendment).
- All Python is fully annotated and passes `mypy --strict` (with `django-stubs` / `djangorestframework-stubs`). Migrations are the only exception. No bare `Any`. Every `cast` / `# type: ignore[code]` has a reason comment (D-028).
- Main app never mints tokens, stores credentials, or owns roles. It checks **permissions**, never role names (D-004, D-005, D-009).
- Token issuing and password hashing live only in the auth service, never in `auth_common` (D-006, D-007).
- One signing key, from the file at `AUTH_SIGNING_KEY_PATH`. It's auto-generated only by `ensure_signing_key` when `DEBUG` is on. `kid` = RFC 7638 thumbprint. No rotation (D-031).
- Never store `average_rating`, `review_count`, or `top_review` on `Brand`. Always calculate them via `Brand.objects.with_stats()`. Don't duplicate the annotations elsewhere or compute them in Python (D-008).
- WP user ids map to UUIDs only via `auth_common.identity.wp_user_uuid()`. Never reimplement it, and never change its namespace or input format. Auth user PK = `Reviewer.auth_user_id` = token `sub` (D-021).
- Bodies are stored sanitized via `catalog.html.sanitize_body()` (nh3 allow-list). `|safe` is allowed only on those sanitized body fields, never on anything else (D-030).
- `short_description` is plain text, seeded with `catalog.text.trim_words(body, 22)` (D-029).
- The import fails loudly, with nothing written, on a brand with zero or several industries, or a review with no valid brand (D-011).
- Migrated rows keep a unique `wp_id`. Imports are idempotent upserts (D-010, D-011).
- No `passlib` (D-007).
- SCSS: BEM (`.block__element--modifier`), one block per component partial. Style by class only: no descendant selectors between classes and no tag selectors inside components, except for CMS-rendered HTML (e.g. `.brand-body__content p`). A block never styles another block's classes; use a mix instead. Max 3 nesting levels, no raw hex outside `settings/`, Dart Sass `@use`/`@forward` only (D-019).
- `.container` and `.grid` are the only layout objects; `.section` is a component (D-019).
- Industry filter options come only from `GET /api/industries/` (D-027), never from brand responses or hard-coded lists.
- Pagination is DRF's stock `PageNumberPagination`, `{count, next, previous, results}`, with no custom shape. Clients compute total pages (D-013).
- API numbers are JSON numbers, never strings: `average_rating` is `float | null` (2 dp), counts and ratings are `int` (D-013).
- React `<BrandList />`: state in the URL (`pushState` + `popstate`), no global store, native form controls only (D-017, D-018).
- `/brand/` works without JS: server-rendered page 1, GET form filters, `<a href>` pagination. React hydrates from `json_script` initial data with no duplicate first fetch (D-022).
- Frontend API types come only from `src/api/schema.gen.ts` (generated, never hand-edited). Tests mock with MSW. Numbered pagination (D-023, D-024, D-026).
- Frontend done = `frontend.md` §7 definition of done, including the Playwright suite (D-025).

## Template

```
### D-NNN: Title
- Status: Proposed | Accepted | Rejected | Superseded by D-xxx
- Origin: Owner | AI default accepted | AI overridden
- Challenge question: #N (if applicable)
- Decision:
- Why:
- Alternatives considered:
- Consequences / revisit when:
```

---

## Stack & infrastructure

### D-001: Django + Django REST Framework for both services
- Status: Accepted · Origin: Owner (returned to the original AI default after trying Django Ninja)
- Decision: Django 5.2 LTS + DRF in both the main app and the auth service. Serializers define request/response contracts. Supporting packages, each pinned:
  - `drf-spectacular`: generates the OpenAPI schema at `/api/schema/` and Swagger UI at `/api/docs/`. Needed for D-023 generated types.
  - `django-filter`: the `industry` filter (D-013).
- Why: the owner knows DRF better than Django Ninja and can defend its auth, permission, validation, and pagination internals from memory. That matters for the live walkthrough and the live requirement. _[owner may expand in own words]_. Also in favor: DRF's `BaseAuthentication` / `BasePermission` are exactly the shape CHALLENGE.md's Pillar 6 example names. Built-in pagination and ordering. The browsable API and Swagger cover "no login UI".
- Consequences:
  - Auth in `auth_common.drf`: `JWTAuthentication(BaseAuthentication)` returns `(TokenUser, claims)`, where `TokenUser` is a lightweight, non-model user built from claims (no DB lookup in the main app). It **must implement `authenticate_header()`** (returning `Bearer realm="api"`). Otherwise DRF downgrades unauthenticated responses from 401 to 403.
  - Permissions: `HasPermissions(BasePermission)` reads `required_permissions` from the view (e.g. `required_permissions = ["brands.change_description"]`) and checks them against the token's `perms` claim (D-005).
  - OpenAPI comes from `drf-spectacular`, not the framework. Annotated fields (`with_stats()`, D-008) need explicit serializer field types, plus `@extend_schema` where inference falls short, so D-023's generated types stay accurate.
  - Validation errors are DRF's standard 400 `{field: [messages]}` shape.
  - No `djangorestframework-simplejwt`: token issuing/verification is owned by the auth service + `auth_common` (D-004, D-006). simplejwt would duplicate it and assumes a shared user table.
- Alternatives: Django Ninja (typed Pydantic contracts and built-in OpenAPI, but the owner is less fluent in it); plain JSON views (hand-rolled validation/pagination).

### D-002: PostgreSQL, one container per service
- Status: Accepted · Origin: AI default accepted
- Decision: `main-db` and `auth-db` are separate Postgres 16 containers.
- Why: The challenge requires the auth service to have "its own database". Separate containers make the boundary physical (no accidental cross-DB joins, independent lifecycle). Postgres provides `ON CONFLICT` upserts for the re-runnable import and solid aggregate queries.
- Alternatives: one Postgres server with two databases (cheaper, still logically separate); SQLite (simplest, but weaker for the "100x data" story and concurrent writes).

### D-003: `uv` + exact pins; the shared lib comes from a local wheelhouse
- Status: Accepted (amended twice, see below) · Origin: AI default accepted, amended by owner
- Decision: Each service has its own `pyproject.toml` + `uv.lock`. `auth-common` is released as immutable wheels into `packages/wheelhouse/` (committed), and each service pins **one specific wheel**.
- **Amendment 2 (owner, 2026-10-29): wheelhouse instead of a source path.** Verified during spec 0 task 3: with `[tool.uv.sources] auth-common = { path = "../../packages/auth_common" }`, uv **ignores** the `==X.Y.Z` specifier, and both services always run the current library source, so they could never be on different versions (contradicting D-016 / Req 8.6).
  - **Release:** `make release-auth-common` (`scripts/release-auth-common.sh`) runs the library's quality gate, then builds `auth_common-X.Y.Z-py3-none-any.whl` into `packages/wheelhouse/`. It **refuses** to overwrite an existing version (released versions are immutable) and requires a matching `CHANGELOG.md` entry.
  - **Pin:** each service declares `auth-common[drf]` in `[project].dependencies`, and `[tool.uv.sources] auth-common = { path = "../../packages/wheelhouse/auth_common-X.Y.Z-py3-none-any.whl" }`. The **wheel filename is the pin**. There's no separate `==` specifier, because uv ignores it for path sources and two sources of truth could disagree. `uv.lock` records the wheel by relative path with its sha256, so a changed wheel fails `uv sync --locked`.
  - **Upgrade:** change one service's wheel path, then `uv lock`. Other services keep their older wheel, since the old file stays in the wheelhouse.
  - **Why not an explicit flat `[[tool.uv.index]]`?** It does honor `==` pins, but uv writes the index location into `uv.lock` as an **absolute** path, so the lock fails `--locked` on any other machine and in Docker (verified). A wheel-file path is stored relative.
  - **Dependency confusion:** a path source is never looked up on any index, so a public `auth-common` (none exists on PyPI today) can't be substituted.
  - **Production path (README "with more time"):** publish the same wheels to a private index (e.g. CodeArtifact, Artifactory, GitHub Packages) and switch `[tool.uv.sources]` to that index. Pins and the release process stay the same.
- Why: Reproducible builds. Each service upgrades the library independently (D-016).
- **Amendment (owner, 2026-10-29): libraries declare bounded ranges.** `auth_common`'s published metadata (`[project].dependencies` and extras) uses bounded ranges, e.g. `django>=5.2.18,<5.3`, not exact pins. Its own `uv.lock` pins exact versions for its tests. Services (and every dev/tool dependency group) keep exact pins. Why: exact pins in a library force every consumer onto the same patch versions, so one service couldn't take a Django security patch without a new library release. That defeats D-016's independent upgrades. Lower bounds are the versions the library is tested against. Upper bounds stop at the next major (or minor, for Django's LTS line).

### D-028: Static typing across the Python backend
- Status: Accepted · Origin: Owner (tooling choices are AI defaults within it)
- Decision: All Python code (both services and `auth_common`) is fully type-annotated and checked with **mypy** in CI and the definition of done.
  - **Checker:** mypy + `django-stubs` (with its mypy plugin) in both services, and `djangorestframework-stubs` (with its plugin) wherever DRF is imported, including `auth_common`'s dev deps. All pinned. The Django/DRF plugins are mypy-only, which is why it's mypy and not pyright.
  - **Strictness:**
    - `auth_common`: `strict = true`, no exceptions. It's small, pure Python, and other code depends on it.
    - Services: `strict = true`, with `disallow_untyped_defs`. Relaxed only for generated code (`*/migrations/*`: `ignore_errors = true`). `settings.py` is typed like everything else.
  - **Annotations:** every function and method signature, including return types (`-> None`). Enforced by ruff's `ANN` rules plus mypy. Modern 3.12 syntax: `list[str]`, `X | None`, `type` aliases, `typing.Self`.
  - **Shapes:**
    - JWT claims: a frozen `@dataclass(slots=True)` (D-006).
    - Raw WP rows from MariaDB in the importers: `TypedDict`s, so SQL → model mapping is checked.
    - Querysets: the custom `BrandQuerySet` is typed so `with_stats()` returns a queryset whose items expose the annotated attributes (via a `Protocol` / `django-stubs` `WithAnnotations`).
    - Settings read from env: parsed once into typed values.
  - **Escape hatches:** no bare `Any` in our signatures. `cast()` and `# type: ignore[code]` are allowed only with the specific error code and a one-line reason comment. `warn_unused_ignores = true` removes stale ones.
  - **Packaging:** `auth_common` ships a `py.typed` marker (PEP 561), so both services type-check against it.
- Why: _[owner to fill in]_. Points in favor: the service boundary is a contract (claims, permissions, API rows), and types make it checkable rather than conventional. It catches the annotation/serializer mismatches D-013 and D-023 depend on. It also helps the reviewers read the code.
- Trade-off to defend: Django's dynamic parts (annotations, `request.user` as a `TokenUser`, reverse relations) need the stubs and a few explicit types. Some honest `cast()`s are expected at the ORM boundary.
- Alternatives: pyright/basedpyright (faster, better editor experience, but no Django/DRF plugin, so model fields and querysets are less precisely typed); annotations without a checker (documentation only, no enforcement).

## Service boundary & auth (Challenge Q7, Q8)

### D-004: RS256 JWT access tokens, verified locally by the main app via JWKS
- Status: Accepted · Origin: AI default accepted · Challenge question: #7
- Decision: The auth service issues short-lived (5–10 min) RS256 access tokens with claims `sub`, `roles`, `perms`, `iat`, `exp`, `jti`, `iss`, `aud`, `ver` (schema version, D-016). It also issues longer-lived **opaque refresh tokens**, stored server-side in auth-db. It publishes `/.well-known/jwks.json`. The main app verifies signatures locally with a cached JWKS.
- Why: No network hop per request. The main app keeps serving reads and editor writes while the auth service is down, until the cached key expires. Asymmetric keys mean the main app can verify but never mint tokens.
- Revocation / role change: role changes take effect at the next refresh. The auth service checks current roles and revocation on every refresh. Immediate revocation (a `jti` / per-user `token_version` denylist the main app polls or receives) is an optional, documented trade-off, built only if time permits.
- Auth service down: existing access tokens work until `exp`. Login and refresh fail. The main app keeps verifying with the cached JWKS (bounded TTL, refetch on unknown `kid`).
- Alternatives: opaque tokens + introspection per request (instant revocation, but the auth service becomes a hard runtime dependency and adds latency); HS256 shared secret (any holder can mint tokens); session cookies (don't fit service-to-service and curl).

### D-031: Signing key: one file, generated only in dev, no rotation
- Status: Accepted · Origin: Owner (trimmed from a larger AI proposal) · Challenge question: #7
- Decision:
  - **Source:** the auth service loads one RSA private key from the PEM file at `AUTH_SIGNING_KEY_PATH` (default `/run/keys/signing.pem`), on the `auth_keys` named volume. It's never committed, baked into an image, or logged. `make reset` deletes the volume.
  - **Dev generation:** the container entrypoint runs `manage.py ensure_signing_key` before starting the server. **Only when `DEBUG` is on and the file is missing**, it generates a 2048-bit RSA key and writes it atomically (temp file + rename) with `0600` permissions. It's an explicit step, not done in settings or `AppConfig.ready()`, so parallel server workers can't each generate a different key.
  - **Production:** the file is mounted from a secret (Docker/Kubernetes secret, or synced from a secrets manager). With `DEBUG` off, a missing or unreadable key makes the service refuse to start. It never auto-generates.
  - **`kid`:** derived from the public key's RFC 7638 JWK thumbprint. There's no separate setting to keep in sync. The token header and the JWKS carry the same value.
  - **JWKS:** publishes exactly one key.
- Why: _[owner to fill in]_. Points in favor: covers the parts reviewers probe (no committed secrets, survives restarts, a safe production path, the `kid` that the main app's refetch-on-unknown-`kid` relies on) with very little code.
- Not built (README "with more time"): **key rotation.** The path is to publish old and new keys in the JWKS, sign with the new one, and drop the old one after the max token lifetime. The main app and `auth_common` already handle it: they look keys up by `kid` and refetch on an unknown one. So adding rotation only changes the auth service.
- Alternatives: a key directory + active-`kid` setting for rotation (AI's first proposal; trimmed as unneeded for this challenge); PEM in an env var (multi-line, visible in `docker inspect`); a new key in memory per start (restarts invalidate tokens, and replicas disagree); key in `auth-db` (leaks into DB backups); cloud KMS/HSM signing (best for production, needs cloud infrastructure).

### D-032: System-architecture defaults (spec 0)
- Status: Accepted · Origin: AI default accepted · Challenge question: #3, #7
- Decision (each item is referenced from `.kiro/specs/system-architecture/requirements.md`):
  1. **Read-only imports by transaction:** importers read WP inside `START TRANSACTION READ ONLY`. There's no separate read-only MariaDB user, so the WP services stay untouched. The trade-off: the protection comes from our code, not from DB permissions.
  2. **Imports are explicit:** they never run on container start. There are two commands plus one Make target that runs both.
  3. **`503` when there are no usable keys:** if the main app has no valid cached JWKS and the auth service is unreachable, protected endpoints return `503`, not `401`, so clients can tell "auth unavailable" from "bad credentials".
  4. **Public endpoints ignore tokens:** they never authenticate, so an invalid or stale token never breaks browsing.
  5. **One origin, no CORS:** the browser only talks to the main app. Only API clients (curl, Swagger) call the auth service.
  6. **Self-contained main image:** a Node build stage compiles the SCSS and builds `<BrandList />`, so the container needs no Node on the host.
  7. **Migrations on start:** each service applies its own Django migrations in the entrypoint.
  8. **Typed, fail-fast settings:** missing or invalid settings stop startup, naming the setting. The service refuses to run with a known dev secret when `DEBUG` is off.
  9. **System-level end-to-end auth check:** login → `PATCH` as editor (200) / reader (403) / anonymous (401), plus "public endpoints work with the auth service stopped".
- Why: each one keeps a failure mode explicit (outage vs bad credentials, accidental WP writes, surprise imports) or keeps the local setup to one command.

### D-033: Two run modes, a base compose file plus an auto-loaded dev override
- Status: Accepted · Origin: Owner · Challenge question: #7
- Decision:
  - `docker-compose.yml` is the **production-like base**: gunicorn (2 workers), `DEBUG=0`, code baked into images, a provided signing key.
  - `docker-compose.override.yml` holds **only dev differences** for `main` and `auth`: `manage.py runserver`, `DEBUG=1`, a bind mount of the **service** source, and `stdin_open`/`tty` so `breakpoint()` works via `docker attach`. `auth_common` is **not** mounted: services always run their pinned released wheel, in dev too (D-003 amendment 2). Library work happens in the library's own tests, then a release.
  - Compose loads the override automatically, so `make up` is dev. `make up-prod` runs the base file alone, after `make prod-key` and with a random `DJANGO_SECRET_KEY`.
  - The entrypoint (`migrate`, `ensure_signing_key`, `exec "$@"`) is shared by both modes. Only the server command differs.
  - Dev serves static via `whitenoise.runserver_nostatic`, the same path as prod. Built frontend assets live outside the bind-mounted path.
  - `make e2e` runs against production-like mode.
- Why: _[owner to fill in]_. Points in favor: runserver gives instant reload and interactive debugging in dev. The base file reads as the deployable setup, and reviewers can see the `DEBUG=0` safeguards (refuse without a signing key or with the dev secret, docs off) actually work.
- Trade-off to defend: dev differs from prod in its process model (single-process runserver vs multi-worker gunicorn). That's mitigated by the shared entrypoint, WhiteNoise in both modes, and running e2e in production-like mode.
- Alternatives: gunicorn everywhere with `--reload` (one file, real process model, but awkward `breakpoint()`; AI's first design); two full compose files (duplication and drift).

### D-034: System-architecture design defaults (spec 0 design §13)
- Status: Accepted · Origin: AI default accepted · Challenge question: #7, #8
- Decision (details in `.kiro/specs/system-architecture/design.md`):
  1. **JWKS-over-HTTP lives in the main app** (`JWKSKeyProvider`, stdlib `urllib`). `auth_common` exposes only a `KeyProvider` Protocol + `StaticKeyProvider`, so the library stays I/O-free and follows D-006's two-consumer rule.
  2. **Adapter wiring:** one setting, `AUTH_COMMON = {"VERIFIER": "<dotted zero-arg factory>"}`. Each service builds its own `TokenVerifier`.
  3. **Token format:** logical `iss=brand-reviews-auth` / `aud=brand-reviews-api` (not URLs), one shared audience, RS256-only algorithm allow-list (rejects `none`/HS*).
  4. **Secure-by-default DRF:** global `JWTAuthentication` + `IsAuthenticated`. Public views opt out with `authentication_classes = ()` + `AllowAny`. A test asserts every URL is public-listed or protected.
  5. **JWKS cache:** fresh 300 s, max stale 3600 s, unknown-`kid` refetch at most every 30 s, 2 s fetch timeout, 30 s clock leeway. All are settings.
  6. **Refresh tokens:** opaque, stored as SHA-256 hashes, rotated on use. Proposed TTLs: access 10 min, refresh 7 days (final in spec 2).
  7. *(superseded by D-033: run modes)*
  8. **Static and assets:** WhiteNoise. A ~20-line Vite-manifest template tag instead of `django-vite`.
  9. **OpenAPI:** always generated with `manage.py spectacular`. The `/api/schema/` and `/api/docs/` HTTP endpoints only exist when `DEBUG` is on.
  10. **WP source driver:** PyMySQL, outside Django `DATABASES`.
  11. **Settings:** hand-rolled typed `env.py` + `dj-database-url`.
  12. **System e2e checks** run in Playwright's request context (reuses D-025).
- Why: each keeps a dependency out or a failure mode explicit, without adding infrastructure the challenge doesn't need.

### D-005: Roles and permissions model
- Status: Accepted · Origin: AI default accepted
- Decision: The auth service owns `Role` (`reader`, `editor`) → permission strings (e.g. `brands.change_description`). Tokens carry both roles and resolved permissions. The main app checks **permissions**, not role names.
- Why: Adding a role later doesn't touch the main app. The main app needs no role table.
- Alternatives: Django's built-in Groups/Permissions in the auth service (likely the underlying implementation anyway); roles-only claims (couples the main app to role names).

### D-006: What lives in `auth_common`
- Status: Accepted (pending spec 2 review) · Origin: AI default accepted · Challenge question: #8
- Decision:
  - In: the claims dataclass + parsing, role/permission constants, the WP-user → UUID mapping (`identity.wp_user_uuid`, D-021), JWT/JWKS verification, and a DRF adapter (optional `drf` extra): a `JWTAuthentication` class, a `TokenUser`, and a `HasPermissions` permission class (D-001).
  - Out: token **issuing** (auth service only), user models, HTTP clients, settings, password hashing (D-007).
- Why both services use it: the main app uses verification + the DRF adapter for the PATCH endpoint. The auth service uses the same claims schema/constants to build tokens and the same verifier/adapter to protect its own `/me` (and any admin) endpoints. **[Confirm each module has two real consumers before accepting.]**

### D-007: WP user migration and passwords
- Status: Accepted (confirmed by discovery, report §5 and §12) · Origin: Owner (AI overridden)
- Decision: Carry WP password hashes over as-is and verify them with a **custom Django password hasher** in the auth service, so existing users log in with their WP passwords. On first successful login, transparently rehash to Django's default hasher.
  - **Import:** the auth service's `import_wp_users` command upserts users keyed on `wp_user_id`, setting the user's UUID primary key to the deterministic value from D-021. Each `user_pass` is stored as `wordpress$<original WP hash>`. The prefix is required: Django picks the hasher by the text before the first `$`, and raw WP hashes start with `$`. Role mapping, read from the serialized `wp_capabilities` usermeta: WP `administrator` → `editor`, everyone else → `reader`. Seed data: user 1 `admin` is the only administrator (→ `editor`); users 2–9 are `subscriber` (→ `reader`).
  - **Hasher** (`accounts/hashers.py`, `WordPressPasswordHasher`, `algorithm = "wordpress"`): verify-only. `encode()` raises, because new WP-format hashes are never created. It mirrors WP 6.9.4's `wp_check_password` + `wp_authenticate` exactly (verified in core source, report §12):
    - **Pre-processing:** strip the password with **PHP `trim()` semantics** (`" \t\n\r\0\x0B"` only, not Python's `str.strip()`), because WP's login path trims and its hashing trims. Reject passwords longer than 4096 bytes.
    - **Dispatch, in WP's order:**
      - `len(hash) <= 32`: legacy plain MD5, compared with `hmac.compare_digest`.
      - `$wp…`: WP ≥ 6.8 bcrypt. `bcrypt.checkpw(base64(HMAC-SHA384(key=b"wp-sha384", msg=password)), hash[3:])`. **All 9 seeded users use this format** (`$wp$2y$10$`, cost 10).
      - `$P$…`: phpass portable (iterated salted MD5). `$H$` is *not* routed to phpass by WP core, so it isn't here either.
      - Anything else starting with `$2y$` / `$2b$`: vanilla bcrypt from plugins. Anything unrecognized → reject.
    - Test that Python's `bcrypt.checkpw` accepts the `$2y$` variant WP/PHP emits.
  - **Upgrade:** `must_update()` returns `True`. `WordPressPasswordHasher` is listed *after* Django's default in `PASSWORD_HASHERS`, so `check_password(..., setter)` rehashes on successful login.
  - **Location:** auth service only, never `auth_common` (D-006).
  - **Dependencies:** `bcrypt` (pinned). phpass is ~30 lines of stdlib `hashlib.md5`. **Not** `passlib`: unmaintained, and its bcrypt backend breaks with modern `bcrypt` releases.
  - **Tests:** known-answer tests per format, with hashes generated by the real WP container (`make wp ARGS="eval 'echo wp_hash_password(\"…\");'"`). Cover wrong password, malformed hash, upgrade-on-login, constant-time comparison (`hmac.compare_digest` / `bcrypt.checkpw`), leading/trailing whitespace (trimmed like PHP: `" pw\n"` verifies, `"\u00a0pw"` doesn't), and the 4096-byte limit.
  - **Dev convenience:** seeded WP passwords aren't documented, so a `set_dev_password` management command sets a known password (refused unless `DEBUG`). The README uses it to get an `editor` token.
- Why: _[owner to fill in]_. Points in favor: real users keep their credentials with no forced reset, showing the migration is lossless for auth too.
- Security notes: hashes are copied once, during import, over the internal network, and are never logged. bcrypt work factor is preserved. Rehash-on-login moves users to Django's stronger default.
- Alternatives: unusable passwords + forced reset (worst UX; password reset is out of scope, so users couldn't recover); `passlib` (rejected above).

## Domain model & migration (Challenge Q1, Q2, Q3)

### D-008: Average rating and review count: calculated from reviews at query time, never stored
- Status: Accepted · Origin: Owner · Challenge question: #1
- Decision: Reviews are the only source of truth. `average_rating`, `review_count`, and `top_review` are **not** columns on `Brand`. They're calculated in the database at query time, so they can never drift from the reviews.
  - **Single read path:** one queryset method, `Brand.objects.with_stats()` (a custom `BrandQuerySet`), adds all three as annotations. Every API endpoint, page, and sort uses it. Don't hand-write `annotate(...)` for these values elsewhere, and don't compute them in Python.
    - `average_rating`: `Avg("reviews__rating")`, output as `DecimalField(3,2)`. `null` when a brand has no reviews.
    - `review_count`: `Count("reviews")`, `0` when there are none.
    - `top_review`: a `Subquery` over `Review` with `OuterRef("pk")`, ordered per D-014. Fetch the fields the list row needs in the same query (no per-row queries).
  - **Sorting:** `ordering` (D-013) sorts on the annotations. For `average_rating`, brands with no reviews sort last in both directions (`nulls_last=True`). `review_count` sorts naturally: 0 is a real value, so ascending count puts zero-review brands first ("fewest reviews first").
  - **Indexes:** `Review(brand_id, rating)` backs the aggregates. `Review(brand_id, rating DESC, created DESC, id)` backs the top-review subquery.
  - **No write-side bookkeeping:** no stored stats fields, no refresh service, no repair command, no signals. Review writes need nothing extra.
  - **ACF `average_rating`:** not imported as truth. The import compares it with the calculated value and reports mismatches. Discovery (report §6): **4 of 5 ACF values are stale** (off by up to 0.82), and they reorder the ranking: ACF puts UrbanRetail first, the real reviews put Acme first. The WP theme sorts "Featured Brands" by the stale value.
  - **Tests:** assert `with_stats()` matches hand-computed values, including brands with zero reviews and rating ties.
- Why: _[owner to fill in]_. Points in favor: always correct, no cache invalidation or drift to defend, less code. At this data size the grouped aggregate is cheap.
- Trade-off to defend: every list request runs a grouped aggregate plus a correlated subquery, and sorting on an aggregate can't use a plain column index. Cost grows with review volume.
- Revisit when: list-endpoint latency becomes noticeable (e.g. the "100x data" case). Options then: stored cached columns with a single write path, a Postgres materialized view, or triggers. Because all reads go through `with_stats()`, switching later only touches that method.
- Alternatives: stored cached columns kept up to date by a refresh service (fast indexed reads, but can drift and needs repair tooling); store only the ACF value (can drift from reviews); Postgres trigger or materialized view (fast reads, logic less visible in Django code).

### D-009: Reviewers: a `Reviewer` profile in the main app, keyed by auth-service user id
- Status: Accepted (confirmed by discovery, report §5) · Origin: AI default accepted · Challenge question: #1
- Discovery facts: every review's `post_author` is a subscriber, and `reviewer_name == wp_users.display_name` in 60/60 rows. `reviewer_location` differs across one user's reviews (2–4 locations each), so it's a per-review fact. The admin wrote no reviews.
- Owner decision: **keep `Review.reviewer_name`** even though it currently equals `Reviewer.display_name`. It's the name as submitted on that review and doesn't change if the reviewer later renames themselves. Pages and the API display `Review.reviewer_name`. `reviewer_location` stays on `Review`.
- Decision: `Reviewer(auth_user_id: UUID unique, display_name, wp_user_id unique)`, with `display_name` from `wp_users.display_name`, in the main app, with no credentials or roles. `auth_user_id` is the deterministic UUID from D-021, computed by the main importer itself, so it equals the auth service's user id and the token `sub` without either service reading the other's database. `Review` has an FK to `Reviewer` **and** keeps ACF `reviewer_name` / `reviewer_location` as the as-submitted display values.
- Why: The main app may not own users (Pillar 5) but needs a stable author identity for joins and pages.
- Alternatives: denormalized strings only (loses identity); full Django users in the main app (violates the boundary).

### D-010: Postmeta strategy
- Status: Accepted (confirmed by discovery, report §3; `seo_extra` dropped by owner) · Origin: AI default accepted · Challenge question: #2
- Discovery facts: brands have **10** meta keys, not ~30: 4 ACF values, 4 ACF field-key references (`_website_url` → `field_brand_website_url`, …), and 2 Yoast keys (`_yoast_wpseo_title`, `_yoast_wpseo_metadesc`). Reviews have 4 ACF + 4 references. There are no `_edit_lock`, `_edit_last`, `_wp_old_slug` or `_thumbnail_id` keys. Yoast's own tables (`wp_yoast_indexable*`, `wp_yoast_migrations`) are derived caches.
- Decision:
  - **First-class columns:** ACF fields (`website_url`, `founded_year`, `headquarters`, `rating`, `reviewer_name`, `reviewer_location`, the `brand` relation), plus Yoast `seo_title` and `seo_description`. Small, displayed, and likely queried.
  - **No JSON catch-all.** There's no `seo_extra` field: no other `_yoast_wpseo_*` keys exist, so it would always be empty (speculative schema). If a future import meets unknown keys, the import reports them, and this decision is revisited.
  - **Dropped:** ACF field-key references (`_<field>` → `field_…`), the ACF `average_rating` value (compared only, D-008), Yoast tables, WP admin-UI usermeta, and anything that only matters to WP's editor. Any meta key the importer doesn't recognize is **reported**, never silently ignored.
  - **Every migrated row** keeps a unique `wp_id` for idempotency and traceability.

### D-011: Migration via a `manage.py import_wp` command that reads MariaDB directly
- Status: Accepted · Origin: AI default accepted · Challenge question: #3
- Decision: Read-only connection to the existing MariaDB, raw SQL over `wp_posts` / `wp_postmeta` / term tables. Order: industries → reviewers → brands → reviews. Reviewers get `auth_user_id` from `wp_user_uuid()` (D-021). The main and auth imports can run in either order and still link up. No aggregate step: stats are calculated at query time (D-008). Each entity is upserted on `wp_id` (`update_or_create` / `bulk_create(update_conflicts=True)`) in a transaction. Supports `--dry-run` and prints a summary of created / updated / unchanged / mismatch counts.
- Why (corrected by discovery, report §11): REST *does* expose all the content meta we need (ACF under `acf`, Yoast under `yoast_head_json`). The real reasons for direct DB access:
  1. The auth import needs password hashes, roles and emails, which REST never exposes. Using one source mechanism for both imports keeps them consistent.
  2. A consistent snapshot read in one transaction.
  3. No HTTP paging or rate limits.
  4. Re-running converges to the same state.
- Scaling to 100x: stream in batches with server-side cursors, `bulk_create` with conflict updates, optional incremental mode via `post_modified_gmt > last_run`.
- Alternatives: REST API (decoupled from WP schema, but paginated and incomplete meta); parsing `dump.sql` (no running DB needed, but brittle).
- **Validation (fail loudly):** the import aborts its transaction, writing nothing, and names the offending WP ids when a brand has **zero or more than one** `industry` term (the API contract has one industry per brand, D-013), or when a review's `brand` meta doesn't point at a published brand. Seed data passes (report §4–5).
- Open: should WP deletions propagate (soft-delete rows whose `wp_id` vanished)? Default: report them, don't delete.

### D-029: `short_description` is a stored, editable column seeded from the body
- Status: Accepted · Origin: Owner · Challenge question: #2, #3
- Discovery: WP stores no short description. `post_excerpt` is empty for every brand, and the theme computes card text at render time as `wp_trim_words(wp_strip_all_tags(post_content), 22)` (report §7).
- Decision:
  - `Brand.short_description` is a stored `TextField`, because `PATCH` (D-015) edits it.
  - **Seed rule (owner):** the first 22 words of the body, matching the WP theme. Algorithm, mirroring `wp_trim_words`:
    1. Strip all tags from the **sanitized** body (D-030). That's identical to the raw `post_content` result for the seed data.
    2. Collapse whitespace and split on it.
    3. Take 22 words, joined by single spaces.
    4. Append `…` only if words were cut.
  - Implemented once, as `catalog.text.trim_words(html, n)`, with unit tests (fewer than 22 words, exactly 22, em dashes, entities).
  - **Plain text only**: never HTML. `PATCH` validation: non-empty after trim, max 300 chars.
- **Re-import rule (owner): always overwrite.** WordPress is the source of truth until cutover, so every `import_wp` run re-derives `short_description` from the current WP body, replacing any value set via `PATCH`.
  - No extra tracking column (no `short_description_edited_at`).
  - **Visibility:** before overwriting, the import compares the stored value with the freshly derived one, and reports `short_description overwritten: N` with the brand slugs where they differed. Lost edits are never silent. `--dry-run` shows the same list without writing.
  - Consequence to defend: `PATCH` edits are temporary until cutover (when the import stops running). The README states this next to the `PATCH` example.
  - Alternatives considered: set only on create (keeps edits, but WP body changes never reach the description); re-derive unless edited in Django via an `edited_at` timestamp (keeps both, at the cost of an extra column and rule). AI had recommended the latter.
- Why: _[owner to fill in]_. Points in favor: it matches what WP visitors see today, and needs no new content.

### D-030: Imported HTML is sanitized with an allow-list
- Status: Accepted · Origin: Owner (sanitizer choice is an AI default) · Challenge question: #3
- Decision: brand and review bodies are sanitized **at import** with `nh3` (Rust `ammonia` bindings, pinned), then stored sanitized. Templates render them with `|safe` only because they were sanitized on write.
  - **Single write path:** `catalog.html.sanitize_body(html) -> str`. Every code path that stores a body calls it: today the importer, and any future editor endpoint.
  - **Allow-list:** `p, br, strong, em, b, i, ul, ol, li, blockquote, a`. Links keep `href` only, with schemes `http`/`https`/`mailto`; `rel="noopener noreferrer nofollow"` is forced via `nh3.clean(..., link_rel=...)` (nh3's default omits `nofollow`). Everything else is removed (tags stripped, text kept), including `script`/`style` contents, `on*` attributes, `style`, `class` and `iframe`.
  - **Report:** the import counts bodies the sanitizer changed and lists their WP ids, so silent content loss is visible. Seed data uses only `<p>` and is expected to come through unchanged (report §9).
  - **Plain-text fields** (`short_description`, review snippets, D-014) are derived from the **sanitized** body with all tags stripped, and are always auto-escaped. Never `|safe`.
  - **Tests:** XSS payloads (`<script>`, `<img onerror>`, `javascript:` links, `<a style>`) are neutralized. Seed bodies round-trip byte-for-byte.
- Why: _[owner to fill in]_. Points in favor: defense in depth. WP editors' HTML becomes our responsibility the moment we render it with `|safe`. Sanitizing on write keeps rendering cheap and makes the stored data trustworthy for every consumer (pages, API, future clients).
- Alternatives: trust WP HTML (works for today's data, but one compromised editor account becomes stored XSS); sanitize on render (re-done on every request, and easy to forget in one template); `bleach` (deprecated upstream).

### D-012: Slugs and URLs match WP permalinks
- Status: Accepted (confirmed by discovery, report §8) · Origin: AI default accepted
- Decision: Store `post_name` verbatim as a unique `slug` per model. Routes are `/brand/<slug>/` and `/review/<slug>/`. Only `publish` posts are imported and rendered.
- Discovery facts: all 5 brands and 60 reviews are `publish`. Slugs are unique within type, match `^[a-z0-9-]+$`, and are at most 51 chars. There's no `_wp_old_slug`, so no redirects to carry over. WP permalinks are `/%postname%/` with CPT rewrite slugs `brand` / `review`.

## API contract (Challenge Q4)

### D-013: `GET /api/brands/` shape
- Status: Accepted · Origin: AI default accepted · Challenge question: #4
- Decision:
  - **Pagination:** page-number, `?page=&page_size=` (default 12, max 50). Response `{count, next, previous, results}`: DRF's built-in `PageNumberPagination`, unmodified (`page_size_query_param="page_size"`, `max_page_size=50`). Owner decision: no custom pagination shape. The client derives total pages as `ceil(count / page_size)`. `next`/`previous` are kept for generic clients; `<BrandList />` doesn't use them, because it builds URLs from its own state (D-017). A page past the end returns DRF's standard 404 (`"Invalid page."`).
  - **Filter:** `?industry=<slug>`, repeatable for multi-select (`?industry=a&industry=b`), OR semantics. Implemented with `django-filter` (`ModelMultipleChoiceFilter`, `to_field_name="slug"`). An unknown slug returns 400.
  - **Sort:** `?ordering=` in `{average_rating, -average_rating, review_count, -review_count, name}`, via DRF `OrderingFilter` with an explicit `ordering_fields` allow-list. Default `-average_rating`. Stable tiebreaker: `name`, then `id`. Invalid values are ignored and the default applies (DRF's standard behavior), which matches the client's defensive URL parsing (`frontend.md` §3).
  - **Row:** `{name, slug, industry: {name, slug}, average_rating, review_count, short_description, top_review: {slug, title, snippet, rating, reviewer_name} | null}`.
  - **Numeric types:** `average_rating` is a JSON **number** rounded to 2 decimals, or `null` when `review_count == 0`. `review_count` and `top_review.rating` are integers. The serializer declares `average_rating` as `FloatField(allow_null=True)` (rounded in `to_representation`), or `DecimalField(coerce_to_string=False)`, so the OpenAPI (and the D-023 generated types) say `number`. That matters because DRF's `DecimalField` serializes as a JSON string (`"4.33"`) by default (`COERCE_DECIMAL_TO_STRING`). Display rounding (one decimal) is the client's job.
- Why: Page-number fits a small, sortable dataset and enables "page X of Y" UI. Slugs in filters keep URLs readable and stable. `-`-prefixed `ordering` is a familiar Django convention.
- Mobile client (future): switch to or add cursor pagination for infinite scroll and stability under inserts, add ETag/`Cache-Control`, keep the row lean, version the API (`/api/v1/` or an Accept header).

### D-027: `GET /api/industries/` is its own endpoint
- Status: Accepted · Origin: Owner · Challenge question: #4
- Decision: Industry filter options come from a dedicated public endpoint, not from facets on the brands response.
  - **Response:** a plain JSON array of `{slug, name}`, ordered by `name`. Not paginated: it's a small, bounded taxonomy.
  - **Contents:** all industries, including any with zero brands, so the filter options don't change as data changes. Seed data: 5 `industry` terms, 1 brand each. The `category` taxonomy (`Uncategorized`) is a different taxonomy and is never imported as an industry.
  - **Caching:** `Cache-Control: public, max-age=300`. Industries change rarely.
  - **Consumers:** `<BrandList />` fetches it once on mount, unless D-022 initial data already includes it. The `/brand/` server-rendered page uses the same selector for its no-JS filter form.
- Why: _[owner to fill in]_. Points in favor: brand list responses stay lean and single-purpose. Filter options are cacheable independently of results. A future mobile client can reuse it.
- Alternatives: facets with counts on `GET /api/brands/` (one request, and counts could reflect current filters, but couples two concerns and bloats every page response).

### D-014: "Top review" definition
- Status: Accepted · Origin: AI default accepted
- Decision: Highest rating, then most recent, then lowest id. Snippet is the plain-text excerpt (HTML stripped), truncated at a word boundary to ~160 chars. Calculated at query time by the `top_review` subquery in `Brand.objects.with_stats()` (D-008), in the same query as the list, so there are no extra queries per row.
- Alternatives: most recent; most "helpful" (no data); longest.

### D-015: `PATCH /api/brands/<slug>/`
- Status: Accepted · Origin: AI default accepted
- Decision: Accepts only `{short_description}`, as plain text, validated per D-029 (non-empty after trim, max 300 chars). Edits persist until the next `import_wp` run, which overwrites them while WP is the source of truth (D-029). Requires permission `brands.change_description` (D-005). Returns the updated row in the D-013 list-row shape. 401 if unauthenticated, 403 if the permission is missing.

## Shared library lifecycle (Challenge Q8)

### D-016: Versioning and breaking changes for `auth-common`
- Status: Accepted · Origin: AI default accepted · Challenge question: #8
- Decision: SemVer with a CHANGELOG. Each release is an immutable wheel in `packages/wheelhouse/` (D-003). Each service pins one wheel and upgrades on its own schedule. Several versions coexist in the wheelhouse, so the main app and the auth service *can* run different library versions at the same time. That makes the steps below demonstrable locally, not just described. Breaking token changes follow expand → migrate → contract, using the `ver` claim:
  1. Release N+1 of the library verifies **both** old and new formats.
  2. Deploy consumers (main app) first.
  3. The issuer (auth service) switches to the new format.
  4. Drop old-format support in a later major version.

## Frontend (Challenge Q5, Q6)

### D-017: `<BrandList />` state lives in the URL
- Status: Accepted · Origin: AI default accepted · Challenge question: #5
- Decision: Filter, sort, and page are read from and written to `URLSearchParams`. User changes call `history.pushState`, and a `popstate` listener restores state on Back/Forward. Server data comes from a `useBrands(params)` hook that uses `AbortController` to cancel stale requests. No global store. Full rules are in `frontend.md` §3.
- UX: the first render uses server-provided initial data (D-022). Skeleton cards appear only when there is no initial data. On later fetches, keep previous results visible with an `aria-busy` region and a polite live-region announcement ("12 brands found"). Error state with a retry button. Empty state with "clear filters".
- Alternatives: TanStack Query (caching/dedup, but one more dependency to justify); component-local state only (filters lost on reload/share).

### D-018: Industry filter control
- Status: Accepted · Origin: AI default accepted
- Decision: Multi-select is a `<fieldset>` of native checkboxes (accessible and keyboard-native). Sort is a native `<select>`. No custom listbox widgets.

### D-019: SCSS architecture: ITCSS layers + BEM naming
- Status: Accepted · Origin: AI default accepted · Challenge question: #6
- Decision: Components use BEM class names. Every styled element gets its own class, and almost every selector compiles to a single class. The compiled CSS keeps every rule and value from `reference/theme.css`; only the selectors change. That meets Pillar 4, which grades structure and naming, not byte equality or pixel matching.
  - **Blocks:** kebab-case, one per component partial (`.card`, `.brand-hero`, `.review-item`, `.site-header`). Existing root names are kept as block names where they already describe a component.
  - **Elements:** `.block__element` (`.card__title`, `.card__meta`, `.review-item__byline`). Elements are flat. Never chain them (`.card__title__link` ❌ → `.card__title-link` ✅).
  - **Modifiers:** `.block--modifier` / `.block__element--modifier` (`.pagination__item--current`, `.stars__star--empty`). A modifier is always used alongside its base class in markup (`class="stars__star stars__star--empty"`).
  - **Selectors:** style by class only. No descendant selectors between classes, and no tag selectors inside components (`.card h3` → `.card__title`). Two exceptions:
    - pseudo-classes and pseudo-elements on the class itself (`&:hover`, `&:focus-visible`);
    - CMS-rendered HTML you can't add classes to, styled under its own element (e.g. `.brand-body__content p`).
  - **Nesting:** in SCSS, nest only `&__element`, `&--modifier`, pseudo-classes, and `@include t.respond-below(...)`, **max 3 levels**. `&__` and `&--` compile to flat single-class selectors, so specificity stays at one class.
  - **Components inside components:** a block never styles another block's classes. When a parent needs to position or space a child block, put one of the parent's element classes on the same node (a "mix"): `<div class="container site-header__inner">`. The parent styles `.site-header__inner`, and `.container` keeps its own rules.
  - **Layout objects:** `.container` and `.grid` are layout-only blocks in `layout/`. They never set colors or type. `.section` sets heading type (`__title`), so it's a component (`components/_section.scss`, with `__title`, `__header`, `__header-link`).
  - **Responsive rules** live inside the block or element they change (see Breakpoints).
  - **Class map:** the README has a full table from each `theme.css` selector to its BEM class, which shows the equivalence. Key mappings (new names follow the same pattern):

    | `theme.css` | BEM |
    |---|---|
    | `.site-header .container` | `.site-header__inner` (mixed with `.container`) |
    | `.site-title`, `.site-title a` | `.site-header__title`, `.site-header__title-link` |
    | `.site-nav a` | `.site-nav__link` |
    | `.hero h1`, `.hero p` | `.hero__title`, `.hero__lead` |
    | `.section h2`, `.section-header`, `.section-header h2`, `.section-header a` | `.section__title`, `.section__header`, `.section__title--flush`, `.section__header-link` |
    | `.card h3`, `.card h3 a`, `.card .meta`, `.card .excerpt` | `.card__title`, `.card__title-link`, `.card__meta`, `.card__excerpt` |
    | `.stars .star-full`, `.star-empty`, `.rating-value` | `.stars__star--full`, `.stars__star--empty`, `.stars__value` |
    | `.brand-hero h1`, `.brand-meta`, `.brand-meta strong` | `.brand-hero__title`, `.brand-hero__meta`, `.brand-hero__meta-label` |
    | `.brand-body .content` | `.brand-body__content` |
    | `.review-item .review-head`, `h3`, `.review-byline`, `.review-body` | `.review-item__head`, `__title`, `__byline`, `__body` |
    | `.review-hero .brand-link`, `h1` | `.review-hero__brand-link`, `.review-hero__title` |
    | `.site-footer a`, `.page-body h1` | `.site-footer__link`, `.page-body__title` |
    | `.pagination .page-numbers`, `.current` | `.pagination__item`, `.pagination__item--current` (+ `aria-current="page"`) |

  - Example:
    ```scss
    @use "../tools" as t;

    .card {
      border: 1px solid var(--color-border);
      border-radius: var(--radius);

      &:hover { box-shadow: var(--shadow); }

      &__title { margin: 0; font-weight: 600; }
      &__title-link { color: var(--color-text); }
      &__meta { color: var(--color-muted); }

      @include t.respond-below(sm) { box-shadow: var(--shadow-sm); }
    }
    ```
  - **Tokens:** existing `:root` custom properties (`--color-*`, `--radius`, `--shadow*`, `--max-width`, `--font-sans`) stay the public runtime API, defined from SCSS token variables in `settings/`. Hard-coded values in the compiled CSS (e.g. `#374151`, `#ecfdf5`, `#111827`, the hero gradient, spacing px values) are promoted to named tokens.
  - **Breakpoints:** the existing desktop-first `max-width: 640px` becomes a named breakpoint behind a `respond-below(sm)` mixin. Responsive overrides sit next to the component they affect, not in one trailing media-query block.
  - **Layering:** folders in `frontend/scss/` in ITCSS order (settings → tools → generic → elements → layout → components → utilities), each with an `_index.scss` that `@forward`s its partials. Dart Sass module system only (`@use`/`@forward`, no `@import`). One partial per component root class (`components/_card.scss`, `_stars.scss`, `_badge.scss`, `_brand-hero.scss`, …).
  - **Adding a component:** create `components/_new-thing.scss` with one new block name, put all its elements and modifiers inside it as `&__…` / `&--…`, `@use` `settings`/`tools`, and add one line to `components/_index.scss`. Because no existing selector can match the new classes, it can't break other components, and theirs can't break it.
- Why: _[owner to fill in]_. Points AI noted in favor: components nest safely. With descendant selectors, a `.card` inside `.brand-body` would pick up rules like `.brand-body .content` or `.card h3` that weren't written for it. BEM classes are unique per block, so nothing leaks between components. Specificity is flat (one class), so order-of-rules fights go away. A class name tells you which partial styles it.
- Trade-off to defend: longer class names in markup, and the Django templates and React components must use the BEM classes rather than copying the WP markup verbatim. The compiled selectors differ from `theme.css`, so the README class map documents the one-to-one correspondence. Stylelint enforces `max-nesting-depth: 2` (the block plus two nested levels), a BEM `selector-class-pattern` (`^[a-z][a-z0-9-]*(__[a-z0-9-]+)?(--[a-z0-9-]+)?$`), `selector-max-compound-selectors: 1` (blocks descendant chains; relaxed only for the CMS-content rules), and no raw hex outside `settings/`.
- React impact: `<BrandList />` uses the global BEM classes for shared UI (`.grid`, `.card` + elements, `.stars`, `.badge`, `.pagination`) so cards match the server-rendered ones. CSS Modules are used only for BrandList-only pieces (filter bar, status messages), and they `@use` the same `settings/` tokens.
- Alternatives: keep the theme's descendant-selector naming (no markup changes, but selectors leak when components nest; rejected); block-scoped nesting with flat child names (short names, same leak problem; rejected); CSS Modules everywhere (scoped by tooling, but doesn't fit server-rendered Django templates).

### D-020: How React is delivered
- Status: Accepted · Origin: AI default accepted
- Decision: Vite builds `<BrandList />` into static assets mounted by a Django template on the brand archive (`/brand/`). It also runs standalone on the Vite dev server with an `/api` proxy for development.
- Alternatives: standalone SPA only; render on the homepage instead.

## Identity (Challenge Q7)

### D-021: Deterministic UUIDs for migrated WordPress users
- Status: Accepted · Origin: Owner · Challenge question: #7
- Decision: During import, each WordPress user id becomes a UUID through a deterministic function, so the same WP user id always produces the same UUID, in either service, on every run.
  - **Function:** `uuid.uuid5(WP_USER_NAMESPACE, f"wp_user:{wp_user_id}")`, exposed as `auth_common.identity.wp_user_uuid(wp_user_id: int) -> UUID`.
  - **Namespace:** the fixed constant `WP_USER_NAMESPACE = UUID("e35b5050-60c9-4156-86b1-f0ee85d87467")`. Generated once and committed. **Never change it**: doing so would re-key every migrated user. Changing the input format (`"wp_user:{id}"`) has the same effect, so it's frozen too.
  - **Auth service:** custom user model with `id = UUIDField(primary_key=True)`. `import_wp_users` sets `id = wp_user_uuid(wp_user_id)` and keeps `wp_user_id` as a unique nullable column. Users created later (non-WP) get `uuid4()`. The token `sub` is this UUID (D-004).
  - **Main app:** `import_wp` sets `Reviewer.auth_user_id = wp_user_uuid(post_author)` (D-009). No call to the auth service and no cross-DB read (D-002).
  - **Idempotency:** the UUID is a pure function of the WP id, so re-runs upsert the same rows (D-011), and the two importers don't depend on each other's order.
  - **Tests (in `auth_common`):** a known-answer test pins the namespace and output for a fixed id (e.g. `wp_user_uuid(1)` equals a hard-coded UUID), so an accidental change fails CI. A determinism test and a distinct-ids test.
- Why: _[owner to fill in]_. Points in favor: the two services agree on identity with no runtime coupling. UUIDs don't leak WP's sequential ids in tokens or URLs, and there's room for non-WP users to be created later without collisions.
- Placement (AI suggestion, accepted by owner): the function and namespace go in `auth_common` because both importers need the exact same constant. Copying it into each service is the drift risk Pillar 6 exists to prevent. This also gives D-006 a module with two real consumers.
- Trade-off to defend: anyone who knows the namespace and a WP id can compute the UUID. It's an identifier, not a secret, and authorization never depends on it being unguessable. Multiple WP sources would need the source site in the name string (e.g. `wp_user:{site}:{id}`). Out of scope for one site, noted for scale.
- Alternatives: use the WP integer id as the auth primary key (simplest, but exposes sequential ids and conflates the two systems' key spaces); random UUIDs plus a lookup endpoint (the main importer would depend on the auth service at import time); main app keyed by `wp_user_id` with `wp_user_id` in the token (leaks a WP concept into the token contract).

## Frontend quality (Challenge Q5)

These entries set the BrandList quality bar. `frontend.md` holds the detailed rules.

### D-022: Progressive enhancement for `/brand/`
- Status: Accepted · Origin: AI default accepted · Challenge question: #5
- Decision: Django renders page 1 server-side (filters/sort/page taken from the URL) with the same BEM card markup and the same `with_stats()` read path (D-008).
  - Filters are a plain `<form method="get">` and pagination uses real `<a href>` links, so the page works without JS.
  - React mounts over the server HTML and takes over fetching. Initial data (results + industry options) is passed with Django's `json_script`, so the first React render matches the server HTML and makes no duplicate request.
- Why: fast first paint, no layout shift, still works if JS fails to load, and a strong production story.
- Trade-off to defend: card markup exists twice (Django template + React `BrandCard`). Mitigated by the shared BEM class contract (D-019) and a test that renders both from the same fixture and compares their structure (classes, headings, link).
- Alternatives: client-only mount with skeletons (simpler, but blank without JS and a fetch before any content).

### D-023: API types generated from OpenAPI
- Status: Accepted · Origin: AI default accepted
- Decision: TypeScript types are generated from the `drf-spectacular` OpenAPI schema (`manage.py spectacular`, D-001) with `openapi-typescript` (dev dependency, pinned) into `src/api/schema.gen.ts`, which is committed. A check regenerates it and fails on any diff. The typed `fetch` wrapper stays hand-written (no generated client).
- Why: the backend schema (D-001) is the single source of truth, so the client can't silently drift from D-013.
- Alternatives: hand-written types (no tooling, but can drift).

### D-024: MSW for API mocking in frontend tests
- Status: Accepted · Origin: AI default accepted
- Decision: Vitest tests mock the API at the network layer with MSW (Node handlers, pinned). Fixtures are typed against D-023's types. The same handlers can drive local dev without a backend.
- Why: tests exercise the real client, including abort and error paths, instead of a stubbed `fetch`.
- Alternatives: hand-stubbed `fetch` (no dependency, but bypasses the client code under test).

### D-025: Playwright end-to-end and visual checks
- Status: Accepted · Origin: AI default accepted
- Decision: a small Playwright suite (≈5 specs) against the running stack:
  - filter, sort, paginate, Back button;
  - a keyboard-only flow and an axe scan;
  - a no-JS check (D-022);
  - screenshots at 360 / 768 / 1280 px.
- Why: the most direct evidence for "production quality, looks high quality". It catches responsive and integration regressions unit tests can't see.
- Alternatives: unit/integration tests only.

### D-026: Numbered pagination
- Status: Accepted · Origin: AI default accepted
- Decision: numbered pages with Previous/Next, matching the theme's `.pagination` and D-013. The page is in the URL. On page change, focus moves to the results heading.
- Why: matches the API shape and the theme, deep-links cleanly, and focus management is simple. "Load more" plus cursor pagination is the documented mobile-client path (D-013).
- Alternatives: "Load more" (better on mobile, but harder to deep-link and harder for keyboard/screen-reader users to track position).

---

## AI defaults accepted (for README)

_Log here when the owner deliberately keeps an AI suggestion over their own preference, and why._

- **D-001:** AI proposed DRF. Owner first chose Django Ninja, then returned to DRF because they know it better and can defend its internals live.
- **D-019:** AI proposed BEM. Owner first chose the theme's descendant-selector naming, then block-scoped nesting with flat class names, and returned to BEM because both alternatives leak styles when one component sits inside another.

## AI suggestions overridden (for README)

- **D-007:** AI proposed unusable passwords + a dev reset command. Owner chose a custom WordPress password hasher so migrated users keep their passwords. _[reason]_
- **D-029:** AI recommended preserving `PATCH` edits across re-imports (via an `edited_at` column). Owner chose always-overwrite, because WP stays the source of truth until cutover. _[reason]_
- **D-031:** AI proposed a multi-key directory with an active-`kid` setting for rotation. Owner trimmed it to one key file with rotation documented only, because rotation isn't something the challenge asks about. _[reason]_
- **D-008:** Owner chose to calculate averages, counts, and the top review from reviews at query time instead of storing cached values. _[reason]_

## Revisit / with more time

_Log items here as they come up._
