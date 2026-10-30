---
inclusion: fileMatch
fileMatchPattern: 'frontend/**'
---

# Frontend quality bar (`<BrandList />` and `frontend/scss/`)

`<BrandList />` ships like production code and must look polished, not just work. This file is the definition of done for anything under `frontend/`. Decisions it relies on: D-017 (URL state), D-018 (native controls), D-019 (BEM/SCSS), D-020 (delivery), D-013 (API contract), D-022 (progressive enhancement), D-023 (generated API types), D-024 (MSW), D-025 (Playwright), and D-026 (numbered pagination).

## 1. Visual quality

- **One visual language.** Cards use the global BEM classes (`.grid`, `.card` + elements, `.stars`, `.badge`, `.pagination`) and look identical to the server-rendered cards. CSS Modules are only for BrandList-only pieces (filter bar, toolbar, status messages). Every value comes from `settings/` tokens: no raw colors, spacing, radii or shadows.
- **Layout.**
  - The toolbar (result count, filters, sort) sits above the grid. On desktop (≥ 768px), filters and sort share one row, with the count on the left.
  - Below 768px, filters collapse into a native `<details>`/`<summary>` disclosure ("Filters (2)") and sort stays visible.
  - It must look deliberate at 320, 360, 768, 1024 and 1280 px: no horizontal scroll, no orphaned controls.
- **Cards.**
  - Equal heights within a row.
  - The snippet is clamped to 3 lines and the description to 2 (`line-clamp` with a non-clamped fallback). Long brand names wrap and never overflow.
  - The industry badge, stars with numeric value, review count, description, and top-review snippet with reviewer name all appear in a consistent order.
- **Loading.**
  - First load shows skeleton cards with the **same dimensions** as real cards (count = `page_size`), so there's no layout shift.
  - Later fetches keep the current results visible and dim them slightly (`aria-busy="true"` on the results region). Don't replace them with skeletons.
  - Only show a spinner if a fetch takes longer than ~300 ms, to avoid flashes.
- **Interaction feedback.** Hover lift on cards (as in the theme), plus a visible `:focus-visible` ring on every interactive element: 2px solid `--color-primary`, 2px offset. Never remove outlines without a replacement.
- **Motion.** Transitions ≤ 150 ms, `transform`/`opacity` only. Everything non-essential is disabled under `prefers-reduced-motion: reduce`.
- **Empty, error, and no-reviews states are designed, not default text.** Each gets an icon-free heading, a sentence, and one clear action:
  - empty: "No brands match these filters", with a "Clear filters" button;
  - error: "We couldn't load brands", with a "Try again" button;
  - a brand with `review_count == 0`: "No reviews yet" instead of stars.

## 2. Accessibility (target WCAG 2.2 AA)

- **Semantics.**
  - Results are a `<ul role="list">` of `<li>`, and each card is an `<article>` with an `<h3>`.
  - The page `<h1>`/`<h2>` belong to the Django template; the component starts at the level it's given (`headingLevel` prop, default 2 for the results heading).
  - Pagination is `<nav aria-label="Brand pages">` with `aria-current="page"` on the current page.
- **One link per card.** The brand name is the only `<a>` and covers the whole card through a stretched pseudo-element (`.card__title-link::after { inset: 0 }`). No nested interactive elements, and no `onClick` on `<article>`.
- **Controls.**
  - Industry filter: `<fieldset>` + `<legend>` + native checkboxes, each with a `<label>`.
  - Sort: a labelled native `<select>`.
  - No custom listbox/combobox widgets (D-018).
  - Touch targets ≥ 24×24 px (WCAG 2.5.8); aim for 44 px on touch layouts.
- **Live updates.** A visually hidden `role="status"` region announces results after each fetch ("12 brands, page 1 of 2"). Errors go into the same region (polite) and the visible error state.
- **Focus management.**
  - Filter/sort changes: focus stays on the control the user changed.
  - Page change: focus moves to the results heading (`tabIndex={-1}`) and the view scrolls to it.
  - Retry: focus returns to the results heading.
  - No positive `tabindex`, and no focus traps.
- **Ratings.** Stars are decorative (`aria-hidden="true"`). The accessible text is the visible numeric value plus a visually hidden "out of 5" ("Rated 4.3 out of 5, 12 reviews").
- **Measured color contrast** (theme tokens, already checked):

  | Pair | Ratio | Rule |
  |---|---|---|
  | `--color-star` on card | 2.15:1 | Fails 3:1 non-text contrast, so stars can't carry meaning alone. The numeric value is always shown. |
  | `--color-star-empty` on card | 1.47:1 | Same as above. |
  | `--color-border` on card | 1.24:1 | Card edges only. **Never** for form-control borders: those use a control-border token ≥ 3:1 (e.g. `--color-muted`, 4.83:1). |
  | `--color-muted` on `--color-bg` | 4.51:1 | Just passes AA. Don't make secondary text any lighter. |
  | `--color-primary` on white / white on primary | 5.47:1 | OK for the focus ring, links and the current page. |

- **Zoom/reflow.** Usable at 200% zoom and at 320 CSS px wide (WCAG 1.4.10). No fixed heights on text containers.

## 3. State and URL (D-017)

- The URL is the single source of truth for `industry` (repeatable), `ordering`, `page`. Component state is derived from it, never duplicated.
- User changes use `history.pushState`. The component listens to `popstate`, so Back/Forward restore filters and results.
- Changing filters or sort resets `page` to 1 (and removes it from the URL).
- Parse defensively: unknown params are ignored; `industry` slugs not in the D-027 industries list are dropped before requesting, since the API returns 400 for unknown slugs (D-013); invalid `ordering` falls back to the default; non-numeric or out-of-range `page` goes to 1. A bad URL never produces an error state.
- Default values are omitted from the **browser** URL, keeping it short and shareable.
- Pagination (D-013, D-026): the API returns DRF's `{count, next, previous, results}`. The client always sends `page_size` explicitly in **API** requests (never relies on the server default) and computes `totalPages = Math.max(1, Math.ceil(count / pageSize))`. It ignores `next`/`previous`. If a page is out of range (API 404 `"Invalid page."`, e.g. after filters shrink the results or from a stale link), it replaces the URL with page 1 and refetches. That's not an error state.
- Every request is cancelled by `AbortController` when params change or the component unmounts, and aborted responses never update state.
- Hydrate from the server-provided `json_script` initial data and skip the first fetch (D-022). The server and client must parse URL params identically, so the first render matches the HTML.

## 4. Data and errors

- One typed client module (`src/api/`) owns URL building, `fetch`, and response parsing (types per D-023). Components never call `fetch`.
- Map failures to a small union: `network` | `server (5xx)` | `client (4xx)` | `aborted` (ignored). The user-facing copy depends on the kind, and raw error messages are never shown.
- Retry is user-initiated (button). No automatic retry loops.
- Format numbers with `Intl.NumberFormat` (rating: one decimal; counts: grouped). Pluralize "1 review" / "12 reviews" correctly.
- All API text is rendered as text. **Never `dangerouslySetInnerHTML`.** The snippet arrives as plain text from the API (D-014).
- Industry options come from `GET /api/industries/` (D-027), or from the `json_script` initial data (D-022). Never hard-code them. If the industries request fails, the results still render and the filter shows its own inline error with a retry.

## 5. Component design

- **Container/presentational split.** `BrandList` (container: URL state, `useBrands`, focus management) renders presentational components: `Toolbar`, `IndustryFilter`, `SortSelect`, `ResultsSummary`, `BrandGrid`, `BrandCard`, `Stars`, `Pagination`, `StatusMessage`, `CardSkeleton`.
- Presentational components are pure: props in, JSX out, with no fetching and no URL access. All props are typed, with no `any` and no non-null `!` assertions on API data.
- Hooks: `useUrlState` (parse/serialize + `popstate`) and `useBrands(params)` (fetch, abort, status). Each is unit-testable alone.
- Public props for `BrandList`: `apiBaseUrl`, `initialData?`, `headingLevel?`, `pageSize?`. Nothing else is configurable without a decision.
- No new runtime dependencies beyond React without a decision entry.

## 6. Testing

- **Vitest + React Testing Library + `user-event`.** Test behavior, not implementation. Query by role/label, never by class or test id unless there's no accessible handle.
- **Required cases:**
  - every state (initial loading, results, refetching, empty, error → retry success);
  - filter toggle updates URL and results;
  - sort change;
  - pagination with focus moving to the heading;
  - Back button restores the previous state;
  - invalid URL params fall back cleanly;
  - stale response ignored after a fast second change;
  - zero-review brand rendering.
- **`vitest-axe`** assertion on every state above.
- API mocking with MSW (D-024).
- Markup parity: a test renders `BrandCard` and the Django card template from the same fixture and compares structure (D-022).
- Playwright (D-025): filter, sort, paginate, Back button, keyboard-only flow, no-JS flow, axe scan, screenshots at 360 / 768 / 1280 px.

## 7. Definition of done (frontend)

All of these pass before a frontend task is marked complete:

1. `tsc --noEmit` (strict), ESLint (incl. `jsx-a11y`), Prettier check, Stylelint (D-019 rules).
2. `vitest --run`: all tests and axe checks green. `schema.gen.ts` regenerates with no diff.
3. Playwright suite green against the running stack (`playwright test`). Screenshot diffs reviewed, not auto-accepted.
4. SCSS compiles with Dart Sass with no deprecation warnings.
5. Manual checks the AI can't do; list them for the owner in the task summary: keyboard-only pass through every state, a VoiceOver pass (macOS Safari), 200% zoom, and a visual check at 360 / 768 / 1280 px.

Full WCAG conformance requires manual testing with assistive technology. Automated axe checks catch only part of it, so never claim "WCAG compliant" from tests alone.
