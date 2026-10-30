# Brand Reviews — WP → Django migration

This repository holds two things:

1. **The running system** — two Django services (a public `main` app and an `auth` service), a React/TypeScript frontend, and the Docker setup that runs them. This is what you build and deploy.
2. **The WordPress source** — a self-contained WordPress site that the migration reads from. Its documentation is preserved under [WordPress source site](#wordpress-source-site) at the end of this file.

Everything below, up to that heading, describes running the Django system.

## Prerequisites

**Docker only.** You need Docker with Compose v2 (the `docker compose` subcommand) and `make`. Everything else — Python, uv, Node, Postgres — runs inside containers. You do not install a toolchain on the host to run the stack.

(Running `make check` directly on the host does use host-side `uv` and `npm`; it is not needed to run the system.)

## Running the system

```bash
cp .env.example .env    # safe local defaults; no real secrets
make up                 # dev mode
```

`make up` builds the images and waits until every service reports healthy. Then both health endpoints return 200:

```bash
curl -fs localhost:8000/healthz/ready    # main
curl -fs localhost:8001/healthz/ready    # auth
```

Stop with `make down` (keeps data) or `make reset` (stops **and** wipes every volume — see below).

### Dev mode vs production-like mode

There are two run modes (D-033). They share one base compose file so they can't drift structurally; the differences are deliberately small.

| | Dev — `make up` | Production-like — `make up-prod` |
|---|---|---|
| Compose files | `docker-compose.yml` + auto-loaded `docker-compose.override.yml` | `docker-compose.yml` only |
| Server | Django `runserver` (autoreload) | `gunicorn`, 2 workers |
| `DJANGO_DEBUG` | `1` | `0` |
| Source | bind-mounted (edit a file, it reloads) | baked into the image |
| Static files | served from source via WhiteNoise finders | collected, hashed filenames (WhiteNoise) |
| `/api/docs/` | 200 | 404 (schema/docs mounted only when DEBUG is on) |
| `DJANGO_SECRET_KEY` | the `.env` dev placeholder | a fresh random value per run (`openssl rand -hex 32`); the dev placeholder is **refused** at startup (Req 10.4) |
| Signing key | generated on demand (DEBUG on) | must be pre-provisioned; `make up-prod` runs `make prod-key` first |

Both modes share the same named volumes, so imported data survives switching between them. Only `make reset` wipes data.

**Attaching a debugger (dev mode).** The `main` and `auth` containers run with `stdin_open` and `tty`, so a `breakpoint()` in your code drops into an interactive `pdb` once you attach to the container:

```bash
docker attach kiro-ca-code-challenge-main-1    # or ...-auth-1
# hit a request that reaches your breakpoint(), then debug interactively
# detach without killing the process: Ctrl-p Ctrl-q
```

Use `docker compose ps` to confirm the exact container name if yours differs.

### Ports

| Service | Host port | Notes |
|---|---|---|
| `main` (public Django app) | `8000` | `/healthz/ready`, `/api/docs/` in dev |
| `auth` (auth service) | `8001` | `/healthz/ready`, `/.well-known/jwks.json` |
| `wordpress` (migration source) | `8080` | the WP site |
| `phpmyadmin` | `8081` | optional DB browser for the WP DB |

The Postgres databases (`main-db`, `auth-db`) and the WP `db` deliberately expose **no** host ports — only the owning service connects to each (D-002).

### Quality gates — `make check`

```bash
make check
```

runs every component gate: `check-auth-common`, `check-auth`, `check-main`, `check-frontend`. The backend gates run `uv sync --locked` (which also proves the lockfile is current), `ruff check`, `ruff format --check`, `mypy`, and `pytest`. The frontend gate runs `npm ci`, strict `tsc --noEmit`, and the SCSS + Vite build.

The backend gate first **unsets** `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS` and the database URLs so the tests' own safe defaults apply. Without this, a shell that has exported the dev `DJANGO_SECRET_KEY` would trip the Req 10.4 refusal under `DEBUG=0` and fail the gate for the wrong reason.

Individual gates (`make check-auth`, etc.) are available too; see `make help`.

### Shipping a new `auth_common` version

`auth_common` is the shared library both services depend on. It is distributed as **immutable wheels** in `packages/wheelhouse/`, and each service pins **one** wheel by path in its `pyproject.toml` and `uv.lock`. A released version's bytes never change, and the two services upgrade independently (D-003 amendment 2, D-016). The current wheel is `auth_common-0.0.1-py3-none-any.whl`.

To release and roll out a new version:

1. **Bump the version** in `packages/auth_common/pyproject.toml` and add a matching `## <version>` entry to `packages/auth_common/CHANGELOG.md`. (The release script refuses to build if the CHANGELOG entry is missing, or if that version's wheel already exists.)
2. **Build the wheel:** `make release-auth-common`. This runs the library's own quality gate, then writes `packages/wheelhouse/auth_common-<version>-py3-none-any.whl`.
3. **Opt one service in:** change that service's wheel path in `[tool.uv.sources]` (e.g. in `services/auth/pyproject.toml`) to the new filename.
4. **Re-lock:** run `uv lock` in that service directory.

The other service keeps running the older wheel until you repeat steps 3–4 for it. Nothing forces both services onto the same version at once.

### Signing keys

The `auth` service signs tokens with an RSA-2048 private key (D-031). The key lives in the `auth_keys` volume at `AUTH_SIGNING_KEY_PATH` (default `/run/keys/signing.pem`) and never leaves the container as anything but that PEM file. Its `kid` is the RFC 7638 thumbprint of the public key, so the JWKS entry and token headers always agree without separate configuration.

- **Where it comes from:** the auth entrypoint runs `ensure_signing_key` on startup. With `DEBUG` on (dev mode) it generates the key if one is missing. With `DEBUG` off (production-like mode) it **refuses to start** when the key is missing, rather than inventing one — so a prod key must be provisioned first.
- **`make prod-key`** provisions it: a one-off auth container with `DEBUG=1` runs `ensure_signing_key` to populate the volume, then exits. `make up-prod` runs this for you. It is a no-op if the key already exists.

#### With more time

**Key rotation** is not implemented. A production system would publish more than one key in the JWKS during an overlap window, sign new tokens with the incoming key while still verifying tokens signed by the outgoing one, and retire the old key only after the longest token TTL has elapsed. The `kid`-in-header plus JWKS design already supports multiple keys; the missing pieces are the rotation command and the overlap bookkeeping.

---

# WordPress source site

Self-contained, reproducible WordPress site used as the source for a WP → Django migration challenge.

The site is a small consumer-reviews directory: **brands** with profile pages plus user-submitted **reviews** linked to each brand. Two custom post types, one taxonomy, ACF fields, Yoast SEO metadata.

## Quick start

```bash
cp .env.example .env
make up
```

After ~20 seconds:

- Public site: <http://localhost:8080>
- WP admin:    <http://localhost:8080/wp-admin> (`admin` / `admin`)
- phpMyAdmin:  <http://localhost:8081>
- REST root:   <http://localhost:8080/wp-json/wp/v2/>

The DB is auto-imported from `db/dump.sql` on first boot. No manual setup required for candidates.

## Stack

| Service     | Image                            | Port  | Purpose                                |
|-------------|----------------------------------|-------|----------------------------------------|
| `db`        | `mariadb:11`                     | -     | Database; auto-imports `db/dump.sql`   |
| `wordpress` | `wordpress:6.9-php8.3-apache`    | 8080  | WP + Apache + PHP                      |
| `wpcli`     | `wordpress:cli-php8.3`           | -     | Helper for re-seeding / dumping        |
| `phpmyadmin`| `phpmyadmin:5`                   | 8081  | Optional DB browser                    |

## What's committed

```
docker-compose.yml          # the stack
.env.example                # config defaults
Makefile                    # make targets
db/dump.sql                 # seeded database snapshot
scripts/seed.sh             # bootstrap script (install + plugins + seed)
wp-content/plugins/         # WP default plugins + ACF + Yoast (committed for offline reproducibility)
wp-content/mu-plugins/
  cpt.php                   # registers `brand` and `review` CPTs and `industry` taxonomy
  acf-fields.php            # registers ACF field groups in code
wp-content/themes/
  consumer-reviews/         # custom theme used by the site
```

WP core files and the default themes (e.g. twentytwentyfour) live inside the `wp_files` named volume and are recreated from the image on first boot. Only the custom `consumer-reviews` theme is committed to the repo.

## Make targets

```
make up         # start db + wordpress + phpmyadmin
make down       # stop containers (keeps volumes)
make reset      # stop AND wipe volumes (next 'up' re-imports dump.sql)
make logs       # tail wordpress + db
make wp ARGS="plugin list"   # run wp-cli inside the stack
make bootstrap  # full re-seed: WP core install + plugin install + content seed
make dump       # export the current DB to db/dump.sql
make status     # show running services
```

## Rebuilding the dump from scratch

If you change the schema or seed data:

```bash
make reset
make up
make bootstrap
make dump
git add db/dump.sql wp-content/plugins
git commit -m "Refresh seed data"
```

`make bootstrap` is idempotent enough to re-run, but the cleanest path is reset → up → bootstrap → dump.

## Content model

**`brand` CPT** at `/brand/<slug>/`
- Standard fields: title, content (body), featured image (optional)
- ACF fields: `website_url`, `founded_year`, `headquarters`, `average_rating`
- Taxonomy: `industry`
- Yoast: `_yoast_wpseo_title`, `_yoast_wpseo_metadesc` in postmeta

**`review` CPT** at `/review/<slug>/`
- Standard fields: title, content (review body), post_author (mapped to a real WP user)
- ACF fields: `rating` (1-5), `reviewer_name`, `reviewer_location`, `brand` (post object → brand id)

Seeded volume: 5 brands (one per industry), 60 reviews (12 per brand) authored by 8 reviewer users, 3 static pages (Home/About/Contact), 1 admin user.

## Theme

The active theme is a custom one at `wp-content/themes/consumer-reviews/` (committed to the repo). It renders:

- Homepage with featured brands and recent reviews
- Brand archive (`/brand/`) — card grid
- Single brand page (`/brand/<slug>/`) — hero with industry badge, star rating, website / founded / HQ metadata, body content, and full list of customer reviews
- Review archive (`/review/`) — paginated list
- Single review (`/review/<slug>/`) — back-link to brand, star rating, reviewer name/location, body
- Page template for About / Contact / Home pages

The theme is intentionally small (~10 PHP files + one stylesheet) and is meant to show candidates what the data renders as. They are not expected to clone the theme — just to migrate the underlying data.

## Endpoints worth knowing

- `/wp-json/wp/v2/brands` — list brands (note: `rest_base` is `brands` even though post type is `brand`)
- `/wp-json/wp/v2/brands/<id>` — single brand with ACF fields under `acf`
- `/wp-json/wp/v2/reviews` — list reviews
- `/wp-json/wp/v2/industry` — taxonomy terms
- `/wp-json/wp/v2/users` — reviewer users
- `/wp-json/wp/v2/pages` — static pages

ACF fields are exposed natively via `show_in_rest: true` set in `wp-content/mu-plugins/acf-fields.php`.

## Notes for the maintainer

- The `wp-content/plugins/advanced-custom-fields/` and `wp-content/plugins/wordpress-seo/` plugin code is GPL and committed to the repo so candidates don't need internet on first boot.
- `wp-content/plugins/akismet/` and `hello.php` are WP defaults — left in place but inactive.
- The site URL is hardcoded as `http://localhost:8080` in the dump (in `wp_options.siteurl` and `home`). Changing the port requires a search/replace in `db/dump.sql` before commit, or just override via `WP_HOME` / `WP_SITEURL` constants.
- `_yoast_wpseo_*` postmeta is seeded for brand posts only.
