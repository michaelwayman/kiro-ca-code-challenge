#!/usr/bin/env bash
# Release auth-common: run its quality gate, then build an immutable wheel into
# packages/wheelhouse/ (D-003). Services opt in by bumping their exact pin and re-locking.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
pkg_dir="$repo_root/packages/auth_common"
wheelhouse="$repo_root/packages/wheelhouse"

cd "$pkg_dir"
version="$(uv version --short)"
wheel="$wheelhouse/auth_common-${version}-py3-none-any.whl"

# Released versions are immutable: a consumer pinned to X.Y.Z must always get the same bytes.
if [[ -e "$wheel" ]]; then
  echo "error: auth-common $version is already released ($wheel)." >&2
  echo "       Bump the version in packages/auth_common/pyproject.toml and CHANGELOG.md first." >&2
  exit 1
fi
if ! grep -q "^## ${version} " CHANGELOG.md; then
  echo "error: CHANGELOG.md has no '## ${version}' entry." >&2
  exit 1
fi

echo "==> quality gate for auth-common $version"
uv sync --all-extras --locked --quiet
uv run pytest -q
uv run mypy
uv run ruff check
uv run ruff format --check

echo "==> building wheel"
mkdir -p "$wheelhouse"
# --no-create-gitignore: released wheels are committed. uv's default `*` .gitignore would hide them.
uv build --wheel --out-dir "$wheelhouse" --no-create-gitignore --quiet
echo "released: ${wheel#"$repo_root"/}"
