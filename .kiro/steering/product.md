# Product context

## What this is

A take-home for a senior full-stack role: replace a small WordPress consumer-reviews site with Django. The full brief is in #[[file:CHALLENGE.md]]. When in doubt, it wins over this file.

The WP site is a directory of **brands** (CPT `brand`, `/brand/<slug>/`) with user-submitted **reviews** (CPT `review`, `/review/<slug>/`), one **industry** taxonomy, ACF fields, and Yoast SEO postmeta. Seed volume: 5 industries, 5 brands, 60 reviews, 8 reviewer users plus 1 admin.

## Deliverables (the six pillars)

1. **Django main app** (Django REST Framework for APIs): clean relational models, a re-runnable WP → Django import, and server-rendered homepage, brand detail and review detail pages. URL slugs must match WP permalinks.
2. **`GET /api/brands/`**: filter by industry, sort by average rating and review count, paginated. Each card row has name, slug, industry, avg rating, review count, short description and top review snippet.
3. **React `<BrandList />`**: consumes the API. Industry filter, sort control, loading/empty/error states, keyboard accessible, semantic, responsive.
4. **SCSS source tree** under `frontend/scss/` that compiles to CSS equivalent to `reference/theme.css`. Graded on structure, not byte equality.
5. **Auth service**: a separate Django project, container and database. Owns users, credentials and roles (at least `reader` and `editor`). Login endpoint issues tokens. Main app exposes `PATCH /api/brands/<slug>/`, callable only by `editor`.
6. **Shared Python library**: installable package with its own `pyproject.toml`, version and tests that run without either Django project. It holds token verification and permission checks. Keep it minimal.

## How the work is judged

- Architectural judgment: schema, API contracts, service boundaries, shared code, component boundaries, SCSS structure.
- How AI is briefed and steered, and when its output is accepted or rejected.
- Whether the author can explain and defend every line. **Never introduce code, dependencies or patterns that aren't justified in a spec or in `decisions.md`.**
- Frontend craft: component design, CSS architecture, a11y, responsive behavior.

## Explicitly out of scope (do not build)

- WP admin/editor experience; Yoast frontend output (the data may be surfaced optionally).
- WP plugin parity beyond data structure.
- User-facing review submission, search.
- Registration, password reset, social login, MFA, login UI (curl, the DRF browsable API, or Swagger UI at `/api/docs/` is enough).
- Image uploads (placeholder boxes only), pixel-matching the WP theme.

## Working agreement for AI

- Prefer small, verifiable steps. Every task ends in something runnable: a test, a `curl`, or `docker compose up`.
- When there's a real choice, present options with trade-offs and let the human decide. Record the outcome in `decisions.md`.
- If you take a default the human didn't explicitly choose, say so in the response so it can be logged under "AI defaults accepted".
