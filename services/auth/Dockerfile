# syntax=docker/dockerfile:1
#
# Auth service image (design §2, §3.1, §3.2).
# Build context is the REPO ROOT:  docker build -f services/auth/Dockerfile .
# Only released wheels (packages/wheelhouse) enter the image, never the auth_common source.

FROM ghcr.io/astral-sh/uv:0.11.28 AS uv

FROM python:3.12-slim

COPY --from=uv /uv /uvx /usr/local/bin/

# The virtualenv lives OUTSIDE /app, so the dev bind mount of the source can't hide it
# (D-033). Use the image's interpreter; never download one.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_PYTHON_DOWNLOADS=never \
    UV_PYTHON=/usr/local/bin/python3.12 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH=/opt/venv/bin:$PATH

RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app

# Install dependencies in a directory that mirrors the repo layout, so the pyproject's
# relative wheel path (../../packages/wheelhouse/...) resolves as it does on a host. The
# project itself is not installed (package = false), so the venv doesn't depend on this
# directory. --frozen installs exactly what uv.lock says, including the auth_common wheel
# by sha256. This is a cached layer: it only reruns when the lock or the wheels change.
COPY packages/wheelhouse/ /build/packages/wheelhouse/
WORKDIR /build/services/auth
COPY services/auth/pyproject.toml services/auth/uv.lock services/auth/.python-version ./
RUN uv sync --frozen --no-dev

WORKDIR /app

COPY services/auth/ ./
RUN chmod 0755 /app/entrypoint.sh

# Signing-key directory (D-031). Owned by the runtime user so a fresh named volume mounted
# here inherits the ownership and ensure_signing_key can write the key.
RUN mkdir -p /run/keys && chown app:app /run/keys && chmod 0700 /run/keys

USER app:app

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["gunicorn", "config.wsgi", "--bind", "0.0.0.0:8000", "--workers", "2"]
