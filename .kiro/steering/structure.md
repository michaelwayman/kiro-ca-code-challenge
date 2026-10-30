# Repository structure

> Status: **Accepted**.

```
.
├── CHALLENGE.md, README.md, Makefile, docker-compose.yml, .env.example
├── db/dump.sql                     # WP source snapshot (read-only input)
├── reference/theme.css             # compiled WP CSS (target for Pillar 4)
├── wp-content/                     # WP source (read-only; schema reference)
│
├── services/
│   ├── main/                       # Pillar 1, 2, protected PATCH
│   │   ├── pyproject.toml
│   │   ├── Dockerfile
│   │   ├── manage.py
│   │   ├── config/                 # settings, urls, wsgi/asgi
│   │   ├── catalog/                # domain: Industry, Brand, Review, Reviewer models;
│   │   │                           #   BrandQuerySet.with_stats() (the only stats read path, D-008);
│   │   │                           #   html.sanitize_body (D-030), text.trim_words (D-029)
│   │   ├── wp_import/              # management command `import_wp` + source readers/mappers
│   │   ├── api/                    # DRF serializers, views, FilterSets, pagination, urls
│   │   ├── pages/                  # server-rendered views + templates (incl. /brand/ no-JS list + React mount, D-022)
│   │   └── tests/
│   │
│   └── auth/                       # Pillar 5
│       ├── pyproject.toml
│       ├── Dockerfile
│       ├── manage.py
│       ├── config/
│       ├── accounts/               # User, roles/permissions, login/refresh/JWKS endpoints,
│       │                           #   hashers.py (WordPressPasswordHasher), `import_wp_users`, `set_dev_password`,
│       │                           #   `ensure_signing_key` (D-031)
│       └── tests/
│
├── scripts/
│   └── release-auth-common.sh      # gate + build an immutable wheel into packages/wheelhouse/ (D-003)
├── packages/
│   ├── wheelhouse/                 # released auth_common wheels, committed; the file-based private index
│   └── auth_common/                # Pillar 6
│       ├── pyproject.toml          # name = "auth-common", version = "X.Y.Z"
│       ├── CHANGELOG.md
│       ├── src/auth_common/
│       │   ├── py.typed            # PEP 561 marker (D-028)
│       │   ├── claims.py           # typed claims model + role/permission constants
│       │   ├── identity.py         # wp_user_uuid() + frozen WP_USER_NAMESPACE (D-021)
│       │   ├── verify.py           # JWT verification against a JWKS / public key
│       │   └── drf.py              # optional DRF adapter: JWTAuthentication, TokenUser, HasPermissions
│       └── tests/
│
├── frontend/
│   ├── scss/                       # Pillar 4 (global theme source)
│   │   ├── main.scss               # entry point: only @use statements
│   │   ├── settings/               # design tokens (colors, type, spacing, breakpoints, radii, shadows)
│   │   ├── tools/                  # functions + mixins (no CSS output)
│   │   ├── generic/                # reset/normalize, box-sizing
│   │   ├── elements/               # bare HTML element styles
│   │   ├── layout/                 # layout-only objects: .container, .grid (no color/type)
│   │   ├── components/             # one partial per block (_section, _site-header, _card, _stars, _badge, _brand-hero, …)
│   │   └── utilities/              # single-purpose helpers (last in cascade)
│   └── brandlist/                  # Pillar 3 (Vite + React + TS)
│       ├── package.json
│       ├── vite.config.ts
│       ├── src/
│       │   ├── BrandList/          # component, subcomponents, *.module.scss, tests
│       │   ├── api/                # typed fetch client; schema.gen.ts (generated from OpenAPI, D-023)
│       │   ├── hooks/              # useBrands, useUrlState
│       │   └── mocks/              # MSW handlers + typed fixtures (D-024)
│       └── e2e/                    # Playwright specs + screenshot baselines (D-025)
│
└── .kiro/
    ├── steering/                   # product, tech, structure, decisions (always); frontend (fileMatch: frontend/**)
    └── specs/                      # one folder per spec (see below)
```

## Spec plan (`.kiro/specs/`)

| Order | Spec folder | Covers |
|---|---|---|
| 0 | `system-architecture` | Service boundaries, token flow, compose topology, shared-lib contract |
| 1 | `domain-model-and-migration` | Models, WP import command |
| 2 | `auth-service-and-shared-lib` | Auth service, `auth_common`, user import |
| 3 | `brands-api` | `GET /api/brands/`, `GET /api/industries/`, `PATCH /api/brands/<slug>/` |
| 4 | `server-rendered-pages-and-scss` | Homepage, brand/review detail, `frontend/scss/` |
| 5 | `brandlist-component` | `<BrandList />` |

Later specs reference earlier ones with `#[[file:.kiro/specs/<name>/design.md]]` instead of restating them.

## Naming conventions

- Python: Django app names are short, lowercase, singular-domain nouns (`catalog`, `accounts`). Business logic goes in `services.py`/`selectors.py` within an app, not in views or serializers.
- DRF view class attributes are **tuples**, e.g. `authentication_classes = ()`, `permission_classes = (AllowAny,)`. ruff's `RUF012` rejects mutable class defaults.
- API: plural resource nouns, trailing slashes (Django default), snake_case JSON keys. Each app's `api/` holds serializers, views and urls, included under `/api/` in `config/urls.py`. Prefer explicit `generics` views over `ViewSet` + router (only a few endpoints). Request/response shapes are serializers, never raw dicts. Auth and permission classes are set per view, not only via global defaults, so a reader sees the protection at the endpoint.
- SCSS (D-019): BEM. Kebab-case blocks, one per partial, filename matches (`_brand-hero.scss` → `.brand-hero`). Flat elements (`.card__title-link`, never `.card__title__link`). Modifiers always alongside their base class (`.pagination__item .pagination__item--current`). Style by class only: no descendant chains between classes and no tag selectors, except CMS-rendered content (e.g. `.brand-body__content p`). A block never styles another block; use a mix. Max 3 nesting levels. Tokens are SCSS variables in `settings/`, emitted as the existing `:root` custom properties (`--color-…`, `--radius`, …). No raw hex outside `settings/`. The full `theme.css` → BEM class map is in D-019.
- React: PascalCase component files, one component per file, colocated `Component.test.tsx`. Add a colocated `Component.module.scss` only for BrandList-only styling. Shared UI uses the global BEM classes (D-019).
- Boundaries: the main app never imports from `services/auth/` and vice versa. Shared code goes only through `auth_common`.
