SHELL := /bin/bash
# Dev mode: base + docker-compose.override.yml (auto-loaded). Design §3.1, D-033.
COMPOSE := docker compose
# Production-like mode: the base file alone (gunicorn, DJANGO_DEBUG=0). Design §3.3.
COMPOSE_PROD := docker compose -f docker-compose.yml
WPCLI := $(COMPOSE) run --rm wpcli

# Backend quality gate (tech.md): ruff, format check, mypy, pytest. Run from a component dir.
# `uv sync --locked` fails if the lockfile is out of date, so the gate also proves lock hygiene.
# The env vars are unset so the tests' own safe defaults (tests/settings.py) apply: a shell that
# exports e.g. the dev DJANGO_SECRET_KEY would otherwise trip the Req 10.4 guard under DEBUG=0.
PY_GATE := unset DJANGO_SECRET_KEY DJANGO_DEBUG DJANGO_ALLOWED_HOSTS MAIN_DATABASE_URL AUTH_DATABASE_URL VITE_DEV_SERVER \
	&& uv sync --locked --quiet && uv run ruff check && uv run ruff format --check && uv run mypy && uv run pytest -q

.PHONY: help up up-prod prod-key down logs reset wp bootstrap dump status \
	check check-auth-common check-auth check-main check-frontend release-auth-common

help:
	@echo "Targets:"
	@echo "  up                   Start the whole stack in dev mode (runserver, DEBUG on) and wait until healthy"
	@echo "  up-prod              Start the whole stack in production-like mode (gunicorn, DEBUG off, random secret)"
	@echo "  prod-key             Provision the auth signing key into the auth_keys volume (run by up-prod)"
	@echo "  down                 Stop containers (preserve data)"
	@echo "  reset                Stop containers AND wipe all volumes (WP db, main_db_data, auth_db_data, auth_keys)"
	@echo "  logs                 Tail wordpress + db logs"
	@echo "  wp ARGS=\"...\"        Run wp-cli inside the stack (e.g. make wp ARGS=\"plugin list\")"
	@echo "  bootstrap            One-shot: install WP core + plugins + seed all content"
	@echo "  dump                 Export current DB to db/dump.sql"
	@echo "  status               Show running services"
	@echo "  check                Run every quality gate (check-auth-common, check-auth, check-main, check-frontend)"
	@echo "  check-auth-common    auth_common: ruff, format check, mypy, pytest"
	@echo "  check-auth           auth service: ruff, format check, mypy, pytest"
	@echo "  check-main           main service: ruff, format check, mypy, pytest"
	@echo "  check-frontend       frontend: npm ci, tsc --noEmit, SCSS + Vite build"
	@echo "  release-auth-common  Quality gate, then build an immutable auth_common wheel into packages/wheelhouse/"

up:
	$(COMPOSE) up -d --build --wait

# One-off auth container with DEBUG on for this single command only, so ensure_signing_key
# may generate the key (D-031). No-op if the key already exists. Base file only, so the
# server-side override (bind mount, runserver) is not involved.
prod-key:
	$(COMPOSE_PROD) run --rm --build --no-deps -e DJANGO_DEBUG=1 --entrypoint python auth manage.py ensure_signing_key

# A fresh random DJANGO_SECRET_KEY per invocation: the dev placeholder is refused when
# DEBUG is off (Req 10.4). Shares volumes with dev mode, so imported data survives switching.
up-prod: prod-key
	DJANGO_SECRET_KEY="$$(openssl rand -hex 32)" $(COMPOSE_PROD) up -d --build --wait

down:
	$(COMPOSE) down

# `down -v` removes every named volume declared in docker-compose.yml: db_data, wp_files,
# main_db_data, auth_db_data and auth_keys (Req 2.8). Dev and prod modes share them.
reset:
	$(COMPOSE) down -v --remove-orphans
	@echo "Volumes wiped (WP db, main_db_data, auth_db_data, auth_keys). Run 'make up' to start fresh from db/dump.sql"

logs:
	$(COMPOSE) logs -f wordpress db

wp:
	$(WPCLI) $(ARGS)

bootstrap:
	$(COMPOSE) run --rm --entrypoint bash wpcli /scripts/seed.sh

dump:
	@mkdir -p db
	$(COMPOSE) exec db sh -c 'mariadb-dump -u root -p"$$MYSQL_ROOT_PASSWORD" --default-character-set=utf8mb4 --add-drop-table --skip-extended-insert "$$MYSQL_DATABASE"' > db/dump.sql
	@echo "Wrote db/dump.sql ($$(wc -l < db/dump.sql) lines)"

status:
	$(COMPOSE) ps

check: check-auth-common check-auth check-main check-frontend
	@echo "All quality gates passed."

check-auth-common:
	cd packages/auth_common && $(PY_GATE)

check-auth:
	cd services/auth && $(PY_GATE)

check-main:
	cd services/main && $(PY_GATE)

# frontend.md §7 automated steps that exist so far: strict tsc and the SCSS + Vite build.
# ESLint, Prettier, Stylelint and Vitest join this target when specs 4-5 add them.
check-frontend:
	cd frontend/brandlist && npm ci --no-audit --no-fund && npm run typecheck && npm run build

# D-003 amendment 2: the script runs the library's gate, then builds the wheel.
release-auth-common:
	./scripts/release-auth-common.sh
