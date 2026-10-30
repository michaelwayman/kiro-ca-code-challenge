# syntax=docker/dockerfile:1
#
# Main app image (design §2, §3.1, §3.2, §7). Multi-stage: node → python.
# Build context is the REPO ROOT:  docker build -f services/main/Dockerfile .
# Only released wheels (packages/wheelhouse) enter the image, never the auth_common source.

# --- frontend: compile the SCSS theme and the Vite bundle -------------------
FROM node:22-slim AS frontend

WORKDIR /src/frontend/brandlist

# Dependencies first (cached layer), installed exactly from the lockfile.
COPY frontend/brandlist/package.json frontend/brandlist/package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY frontend/scss/ /src/frontend/scss/
COPY frontend/brandlist/ ./

# Writes /src/frontend/build/{css/theme.css, brandlist/assets/*, brandlist/.vite/manifest.json},
# the same layout as /opt/frontend-dist (task 5).
RUN npm run build

# --- python: the Django app ---------------------------------------------------
FROM ghcr.io/astral-sh/uv:0.11.28 AS uv

FROM python:3.12-slim AS python

COPY --from=uv /uv /uvx /usr/local/bin/

# The virtualenv and the frontend build live OUTSIDE /app, so the dev bind mount of the
# source can't hide them (D-033, design §7). Use the image's interpreter; never download one.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_PYTHON_DOWNLOADS=never \
    UV_PYTHON=/usr/local/bin/python3.12 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    FRONTEND_DIST_DIR=/opt/frontend-dist \
    PATH=/opt/venv/bin:$PATH

RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app

# Install dependencies in a directory that mirrors the repo layout, so the pyproject's
# relative wheel path (../../packages/wheelhouse/...) resolves as it does on a host. The
# project itself is not installed (package = false), so the venv doesn't depend on this
# directory. --frozen installs exactly what uv.lock says, including the auth_common wheel
# by sha256. This is a cached layer: it only reruns when the lock or the wheels change.
COPY packages/wheelhouse/ /build/packages/wheelhouse/
WORKDIR /build/services/main
COPY services/main/pyproject.toml services/main/uv.lock services/main/.python-version ./
RUN uv sync --frozen --no-dev

WORKDIR /app

COPY --from=frontend /src/frontend/build/ /opt/frontend-dist/
COPY services/main/ ./
RUN chmod 0755 /app/entrypoint.sh

# Collect static at build time (design §3.2, §7). Settings need a secret and a DB URL to
# import; these throwaway values exist only for this RUN (no DB connection is made) and
# are not part of the image's environment.
RUN DJANGO_DEBUG=0 \
    DJANGO_SECRET_KEY=collectstatic-build-only \
    MAIN_DATABASE_URL=postgres://build:build@localhost:5432/build \
    python manage.py collectstatic --noinput

USER app:app

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["gunicorn", "config.wsgi", "--bind", "0.0.0.0:8000", "--workers", "2"]
