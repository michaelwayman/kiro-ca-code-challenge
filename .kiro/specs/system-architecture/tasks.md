# Tasks: System Architecture (spec 0)

Implements #[[file:.kiro/specs/system-architecture/design.md]] against #[[file:.kiro/specs/system-architecture/requirements.md]].

## Scope

Spec 0 builds the **runnable skeleton and the cross-cutting guardrails**:

- repo scaffolding;
- the `auth_common` package shell;
- both Django projects with typed settings, health checks and secure-by-default DRF;
- placeholder frontend builds;
- the Docker images;
- both run modes (D-033);
- signing-key provisioning (D-031);
- Make targets and quality gates.

Token issuing and verification, the JWKS provider, the importers, the APIs and the UI are built in specs 1–5. The traceability table at the end shows where each requirement is delivered.

## Rules for every task

- **Definition of done:** the task's "Done when" checks pass, plus the component's quality gate:
  - backend: `ruff check`, `ruff format --check`, `mypy`, `pytest` (tech.md);
  - frontend: `frontend.md` §7 automated steps.
- **Dependencies:** exact pins in services and dev/tool groups. Bounded ranges in `auth_common`'s published metadata (D-003 amendment). Add a dependency only if this spec's design names it.
- **Placeholders** (frontend shells in task 5) are explicitly marked `PLACEHOLDER (replaced in spec N)` in a header comment. Nothing else is stubbed.

## Tasks

- [x] 1. Root scaffolding
  - Add `.dockerignore`: `wp-content/`, `db/`, `.git/`, `.agents/`, `**/node_modules/`, `**/.venv/`, `**/__pycache__/`, `**/dist/`, caches, Playwright reports.
  - Extend `.gitignore` with the same build and cache artifacts. Keep the existing entries.
  - Extend `.env.example` with every variable in design §8 that has a default. `DJANGO_DEBUG` is **not** added (the compose files own it, D-033).
  - **Done when:** `git status` shows only intended files; `.env.example` covers every variable in design §8.
  - _Requirements: 10.2_

- [x] 2. `auth_common` package shell
  - `packages/auth_common/pyproject.toml`: name `auth-common`, version **`0.0.1`**, Python ≥ 3.12, build backend hatchling, optional extra `drf` (`django`, `djangorestframework`). Core runtime dependency: `PyJWT[crypto]`. Metadata uses bounded ranges; the lockfile is exact (D-003 amendment).
  - `src/auth_common/__init__.py` (`__version__` read from package metadata), `py.typed`, `CHANGELOG.md`.
  - **Revised:** the skeleton is `0.0.1` and released as the first wheel (`packages/wheelhouse/auth_common-0.0.1-py3-none-any.whl`) by `scripts/release-auth-common.sh`, keeping `0.1.0` free for spec 2's first API (D-003 amendment 2).
  - Tooling config in the package: ruff (with `ANN`), mypy `strict = true` (plus `django-stubs` / `djangorestframework-stubs` as dev dependencies for the future `drf.py`), pytest.
  - Test `test_package.py`: `__version__ == "0.0.1"`, and **`import auth_common` succeeds with Django not installed** (run the core test environment without the `drf` extra).
  - **Done when:** `uv run pytest`, `uv run mypy src`, `uv run ruff check` and `ruff format --check` pass in `packages/auth_common/`.
  - _Requirements: 8.1, 8.3, 12.1_

- [x] 3. Auth service skeleton (`services/auth/`)
  - uv project with exact pins:
    - Django 5.2 LTS, `djangorestframework`, `drf-spectacular`, `psycopg[binary]`, `dj-database-url`, `gunicorn`, `whitenoise`;
    - `auth-common[drf]`, pinned to the released wheel `packages/wheelhouse/auth_common-0.0.1-py3-none-any.whl` via `[tool.uv.sources]` (design §2.1, D-003 amendment 2);
    - dev: `pytest`, `pytest-django`, `mypy`, `django-stubs[compatible-mypy]`, `djangorestframework-stubs`, `ruff`.
  - `config/env.py`: typed `env_str` / `env_int` / `env_bool` / `env_path`. Missing or invalid values raise `ImproperlyConfigured` naming the variable. `DJANGO_DEBUG` defaults to `False`.
  - `config/settings.py`:
    - all config from `env.py`;
    - **refuse to start** when `DEBUG` is off and `DJANGO_SECRET_KEY` is the known dev value;
    - logging to stdout;
    - `REST_FRAMEWORK` secure defaults (`DEFAULT_PERMISSION_CLASSES = [IsAuthenticated]`; authentication class added in spec 2);
    - drf-spectacular, with schema/docs URLs mounted only when `DEBUG` is on.
  - `accounts` app created (empty models for now) and `health` views: `/healthz/live` (always 200) and `/healthz/ready` (200 if `SELECT 1` on the default DB succeeds, else 503). Both public (`authentication_classes = ()`, `AllowAny`).
  - mypy config with the `django-stubs` and DRF plugins; migrations excluded (D-028).
  - Tests:
    - `env.py` (missing, invalid, bool parsing);
    - the dev-secret refusal;
    - live/ready (ready → 503 when the DB is unavailable, via a patched cursor);
    - `/api/docs/` is 404 when `DEBUG` is off.
  - **Done when:**
    - the backend quality gate passes in `services/auth/`;
    - the installed `auth_common.__version__` is the pinned wheel's version;
    - a copy of the service and wheelhouse at a different absolute path passes `uv sync --locked` (lockfile portability);
    - a modified wheel fails `uv sync --locked`.
  - **Finding:** the original done-when ("`uv lock` fails on a mismatched `==` pin") was **false** for path sources, which led to D-003 amendment 2.
  - _Requirements: 2.9, 8.6, 9.6, 10.1, 10.3, 10.4, 11.1, 11.3, 12.1_

- [ ] 4. Main app skeleton (`services/main/`)
  - Same base as task 3 (dependencies, `env.py`, settings rules, health views, spectacular, mypy), plus:
    - `whitenoise` middleware **and** `whitenoise.runserver_nostatic` in `INSTALLED_APPS` (D-033);
    - `STATICFILES_DIRS` includes `/opt/frontend-dist` (design §7).
  - `catalog`, `wp_import`, `api` and `pages` apps created as empty shells (filled by specs 1, 3, 4).
  - `pages` template tag `vite_asset(entry)`:
    - reads the Vite `manifest.json` from staticfiles and emits `<script type="module">` / `<link rel="stylesheet">` for the entry and its CSS;
    - when `VITE_DEV_SERVER` is set, emits dev-server tags instead;
    - when the manifest is missing, raises a clear error in `DEBUG` and logs + renders nothing otherwise.
  - **URL allow-list test** (design §6.1): resolves every URL pattern and asserts it's either in an explicit `PUBLIC_ROUTES` list (today: health) or rejects an anonymous request. Spec 3 adds the API routes to the list.
  - Tests: as task 3, plus the `vite_asset` tag (manifest present, dev-server mode, missing manifest).
  - **Done when:** the backend quality gate passes in `services/main/`.
  - _Requirements: 1.6, 2.9, 4.11 (mechanism), 9.1, 9.6, 10.1, 10.3, 10.4, 11.1, 11.3, 12.1_

- [ ] 5. Frontend build shells (PLACEHOLDER content, replaced in specs 4 and 5)
  - `frontend/scss/main.scss`: a placeholder that `@use`s nothing and emits one comment. It's enough for the build to produce `theme.css`.
  - `frontend/brandlist/`: Vite + React 19.3 + TypeScript (strict) project with exact pins. `vite.config.ts` has `build.manifest = true`, the entry `src/main.tsx`, and a dev `server.proxy['/api'] = 'http://localhost:8000'`. `src/main.tsx` renders nothing into `#brand-list-root` if present.
  - Root `package.json` scripts (or Make targets) for `build:css` (Dart Sass) and `build:js` (Vite).
  - **Done when:** `npm ci && npm run build` produces `dist/.vite/manifest.json`, the SCSS build produces `theme.css`, and `tsc --noEmit` passes.
  - _Requirements: 9.3, 9.4_

- [ ] 6. Dockerfiles and the shared entrypoint
  - `services/auth/Dockerfile`: `python:3.12-slim`, uv, build context = repo root.
    - `COPY packages/wheelhouse` (released wheels only) and the service, then `uv sync --frozen --no-dev`.
    - Non-root user. `ENTRYPOINT ["/app/entrypoint.sh"]`, `CMD` = the gunicorn command (design §3.1).
  - `services/main/Dockerfile`: a multi-stage build.
    - **`frontend` stage** (`node:22-slim`): builds the task 5 outputs.
    - **`python` stage:** as auth, then copies the frontend outputs to `/opt/frontend-dist` and runs `collectstatic`.
    - Non-root user, same entrypoint/CMD pattern.
  - `entrypoint.sh` per service, exactly as design §3.2 (`set -eu`, `migrate`, auth also `ensure_signing_key`, then `exec "$@"`).
  - **Done when:**
    - `docker compose build main auth` succeeds;
    - `docker compose run --rm --no-deps --entrypoint python main -c "import auth_common; print(auth_common.__version__)"` prints `0.1.0`;
    - the main image contains `/opt/frontend-dist/.vite/manifest.json` and the collected `theme.css`;
    - both images run as non-root.
  - _Requirements: 2.9, 9.3_

- [ ] 7. `ensure_signing_key` command (auth service, D-031)
  - `accounts/management/commands/ensure_signing_key.py`. Behavior:
    - file exists and parses as an RSA private key → no-op;
    - `DEBUG` on and missing → generate RSA-2048, write a temp file in the same directory, `chmod 0600`, `os.replace` (atomic);
    - `DEBUG` off and missing or unreadable → exit non-zero with a message naming `AUTH_SIGNING_KEY_PATH`.
    - Never prints key material.
  - `accounts/keys.py`: `load_private_key(path)` and `public_jwk_and_kid(private_key)` (RFC 7638 thumbprint). Used by spec 2 for the JWKS and token headers.
  - Tests:
    - creates once and is idempotent (a second run doesn't change the file);
    - mode `0600`;
    - refuses when `DEBUG` is off;
    - rejects a corrupt file;
    - the RFC 7638 known-answer test, using the example key from RFC 7638 §3.1 with its expected thumbprint.
  - **Done when:** the backend quality gate passes, and the tests above are included.
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 11.4_

- [ ] 8. Compose: base file and dev override (D-033)
  - `docker-compose.yml`: add `main-db`, `auth-db` (`postgres:16`, `pg_isready` healthchecks), `auth` and `main` per design §3 and §3.1. Base settings: `DJANGO_DEBUG: "0"`, gunicorn, healthchecks on `/healthz/ready`, volumes `main_db_data`, `auth_db_data`, `auth_keys`. `main` depends only on `main-db`; `auth` only on `auth-db`. **WP services are not edited.**
  - `docker-compose.override.yml`: for `main` and `auth` only.
    - `command: python manage.py runserver 0.0.0.0:8000`, `DJANGO_DEBUG: "1"`;
    - a bind mount of the service source only. `auth_common` is never mounted: services run their pinned wheel in dev too (D-003 amendment 2). The container's virtualenv lives outside the mount (e.g. `UV_PROJECT_ENVIRONMENT=/opt/venv`), so the mount can't hide it;
    - `stdin_open: true`, `tty: true`.
  - **Done when:**
    1. `cp .env.example .env && make up` (dev) brings every service to healthy;
    2. `curl -fs localhost:8000/healthz/ready` and `curl -fs localhost:8001/healthz/ready` both return 200;
    3. editing a view file reloads without a restart;
    4. `docker compose stop auth` leaves `localhost:8000/healthz/ready` at 200 (Req 6.1, 11.2);
    5. `/api/docs/` is 200 in dev;
    6. `docker compose config` shows the WP service definitions unchanged from `git show HEAD:docker-compose.yml`.
  - _Requirements: 1.1, 1.5, 2.1, 2.2, 2.3, 2.4, 2.6, 2.7, 2.8, 6.1, 11.1, 11.2_

- [ ] 9. Make targets and production-like mode (design §3.3, §9)
  - Update `up` to start the whole stack (dev). Keep `down`, `logs`, `status`, `wp`, `bootstrap`, `dump`. `reset` also removes `main_db_data`, `auth_db_data`, `auth_keys`.
  - Add `prod-key`: a one-off `auth` container with `DJANGO_DEBUG=1` running `ensure_signing_key`, base file only.
  - Add `up-prod`: depends on `prod-key`, runs `docker compose -f docker-compose.yml up -d --build` with a per-invocation random `DJANGO_SECRET_KEY`.
  - Add `check-auth-common`, `check-auth`, `check-main`, `check-frontend` and the aggregate `check`. Update `help`.
  - Add `release-auth-common` (runs `scripts/release-auth-common.sh`, D-003 amendment 2).
  - (`import`, `import-dry`, `dev-password` and `token` are added by specs 1–2 when their commands exist. `e2e` and `e2e-dev` are added once the Playwright suite exists.)
  - **Done when:**
    1. `make reset && make up-prod` brings every service to healthy, with gunicorn visible in `docker compose top`;
    2. `/api/docs/` is 404 in prod mode;
    3. static `theme.css` is served by WhiteNoise with a hashed filename;
    4. `docker compose -f docker-compose.yml up auth` **without** `make prod-key` on a fresh volume makes the auth container exit with the `AUTH_SIGNING_KEY_PATH` error (Req 5.4);
    5. prod mode with `DJANGO_SECRET_KEY=dev-insecure-change-me` refuses to start (Req 10.4);
    6. `make check` passes.
  - _Requirements: 2.2, 2.8, 5.4, 10.4, 12.3_

- [ ] 10. README: running the system (spec 0 sections)
  - Sections:
    - prerequisites (Docker only);
    - dev mode vs production-like mode (`make up` / `make up-prod`, what differs, how to `docker attach` for `breakpoint()`);
    - ports;
    - `make check`;
    - how a new `auth_common` version reaches each service: bump the version + CHANGELOG → `make release-auth-common` → change **one** service's wheel path → `uv lock`. The other service stays on its wheel until it opts in (D-003 amendment 2, D-016);
    - where signing keys come from (D-031), plus key rotation as a "with more time" item.
  - Keep the existing WP-source README content intact under its own heading.
  - **Done when:** following the README from a clean clone (`make reset`) reproduces task 8 checks 1–2 and task 9 check 1.
  - _Requirements: 2.2, 8.6, 12.3_

- [ ] 11. Checkpoint: clean-checkout smoke test
  - From `make reset`:
    - run `make up` → all healthy → stop `auth` → main still ready;
    - run `make up-prod` → all healthy → task 9 checks 2–5;
    - run `make check` → green.
  - Record any deviation from the design in `decisions.md` (new `Proposed` entry), rather than silently changing the code or the spec.
  - **Done when:** all of the above pass, and the owner has reviewed the diff.
  - _Requirements: all spec 0 requirements delivered by tasks 1–10 (see the table below)_

## Requirement traceability

| Requirement | Delivered by |
|---|---|
| 1 Service inventory and ownership | tasks 3, 4, 8 (structure). 1.2–1.4 data ownership is enforced by specs 1–2 models |
| 2 Container topology | tasks 3, 4, 6, 8, 9 |
| 3 Data migration orchestration | **spec 1** (`import_wp`), **spec 2** (`import_wp_users`), their Make targets |
| 4 Authentication flow | **spec 2** (issuing, JWKS, `JWTAuthentication`, `JWKSKeyProvider`), **spec 3** (`PATCH` permission). Task 4 provides the default-deny mechanism (4.11) |
| 5 Signing keys | task 7 (5.1–5.5), task 9 (5.4 end-to-end). Token `kid` in headers: spec 2 |
| 6 Dependency unavailable | task 8 (6.1). **Spec 2** (6.2–6.6, JWKS cache state machine) |
| 7 Revocation and role changes | **spec 2**. README statement (7.3): spec 2 |
| 8 Shared library contract | task 2 (8.1, 8.3), tasks 3–4 (8.6). **Spec 2** (8.2, 8.4 contents; 8.5 `ver` handling) |
| 9 Routing and frontend | tasks 4, 5, 6 (9.1, 9.3, 9.4, 9.6). 9.2 is structural. **Specs 4–5** (9.5 no-JS `/brand/`) |
| 10 Configuration and secrets | tasks 1, 3, 4, 9. 10.5 (`set_dev_password`): spec 2 |
| 11 Health and observability | tasks 3, 4, 7, 8. 11.5 (auth-failure log reasons): spec 2 |
| 12 Quality gates | tasks 2–4, 9. **12.4 system e2e:** added after spec 3 (Playwright request specs, D-034.12) |
