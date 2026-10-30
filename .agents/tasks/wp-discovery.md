# WP source discovery report

- **Date:** 2026-10-29
- **Source:** the running stack (`make up`): MariaDB 11 `wp` database, WordPress **6.9.4**, the REST API at `localhost:8080`, `wp-content/mu-plugins/{cpt,acf-fields}.php`, and the `consumer-reviews` theme.
- **Method:** read-only SQL via `docker compose exec db mariadb`, REST `curl`, and reading WP core/theme source in the containers. Nothing was written to the WP database.

## 1. Content inventory

| Type | Status | Count | In scope |
|---|---|---|---|
| `brand` | publish | 5 | yes |
| `review` | publish | 60 (12 per brand) | yes |
| `page` | publish 4 / draft 1 | 5 | no (only homepage, brand and review pages are required) |
| `post` | publish | 1 (WP default "Hello world") | no |
| users | | 9 (1 `administrator`, 8 `subscriber`) | yes, imported into the auth service |
| `industry` terms | | 5, each with exactly 1 brand | yes |
| `category` terms | | 1 (`Uncategorized`) | no (different taxonomy; don't confuse it with industry) |

There are no other statuses (no `draft`, `private` or `trash` brands or reviews). Brands have `post_author = 0`, no featured images (`_thumbnail_id` absent) and no parent or menu order.

## 2. Authoritative schema (from `cpt.php` / `acf-fields.php`)

- **`brand`:** rewrite slug `brand`. Supports title, editor, thumbnail, **excerpt**, custom-fields. Taxonomy `industry`: non-hierarchical, attached to `brand` only.
- **`review`:** rewrite slug `review`. Supports title, editor, **author**, custom-fields.
- **ACF, Brand Profile:**
  - `website_url` (url, optional);
  - `founded_year` (number, 1800–2100);
  - `headquarters` (text);
  - `average_rating` (number, 0–5, step 0.1).
- **ACF, Review Details:**
  - `rating` (number 1–5, step 1, **required**);
  - `reviewer_name` (text);
  - `reviewer_location` (text);
  - `brand` (post_object → brand, return id, **required**).
- Permalinks: `/%postname%/` with CPT rewrite slugs, so `/brand/<post_name>/` and `/review/<post_name>/`.

## 3. Postmeta: every key present

| Post type | Key | Rows | Classification |
|---|---|---|---|
| brand | `website_url`, `founded_year`, `headquarters` | 5 each | **column** |
| brand | `average_rating` | 5 | **not truth**: compare-and-report only (D-008, see §6) |
| brand | `_website_url`, `_founded_year`, `_headquarters`, `_average_rating` | 5 each | **drop**: ACF field-key references (`field_brand_*`) |
| brand | `_yoast_wpseo_title`, `_yoast_wpseo_metadesc` | 5 each | **column** (`seo_title`, `seo_description`) |
| review | `rating`, `reviewer_name`, `reviewer_location`, `brand` | 60 each | **column** / FK |
| review | `_rating`, `_reviewer_name`, `_reviewer_location`, `_brand` | 60 each | **drop**: ACF field-key references |
| page | `_wp_page_template` | 2 | out of scope |

- **That's 10 meta keys per brand, not "~30"** as CHALLENGE.md says. Only **2** Yoast keys exist. There are no `_edit_lock`, `_edit_last`, `_wp_old_slug` or `_thumbnail_id` keys in this dataset.
- Yoast also has its own tables (`wp_yoast_indexable`: 78 rows; `wp_yoast_indexable_hierarchy`: 76; `wp_yoast_migrations`: 25; two empty). These are Yoast's derived caches and bookkeeping. **Drop.**
- **`post_excerpt` is empty for all 5 brands and all 60 reviews.** See §7.

## 4. Brands

| wp_id | slug | title | industry | founded | HQ | ACF avg |
|---|---|---|---|---|---|---|
| 7 | `acme-insurance` | Acme Insurance Co. | insurance | 1985 | Hartford, CT | 4.2 |
| 8 | `primepath-bank` | PrimePath Bank | finance | 1978 | New York, NY | 4.0 |
| 9 | `homeshield-pro` | HomeShield Pro | home-services | 1999 | Atlanta, GA | 3.9 |
| 10 | `swiftstream-internet` | SwiftStream Internet | telecom | 2014 | Austin, TX | 3.5 |
| 11 | `urbanretail-co` | UrbanRetail Co. | retail | 2005 | Seattle, WA | 4.4 |

- Every brand has **exactly one** industry. None has zero or several. The API's single `industry` object per row (D-013) matches the data. The WP taxonomy allows several, so the import must decide what to do if it ever finds more than one (suggest: fail loudly).
- Content is 703–820 chars of plain `<p>…</p>` HTML.

## 5. Reviews, reviewers and users

- All 60 reviews have a valid `brand` meta pointing at a published brand. There are no orphans.
- Ratings are all integers 1–5. Distribution: 1×1, 13×2, 14×3, 13×4, 19×5.
- **Every review's `post_author` is a subscriber (users 2–9), and `reviewer_name` equals that user's `display_name` in 60/60 rows.** The admin (user 1) wrote no reviews.
- **`reviewer_location` varies per review for the same user** (2–4 distinct locations each, e.g. Jenny W.: Albany NY, Boerne TX, Cedar Rapids IA, Chicago IL). Location is a per-review fact, not a reviewer attribute.
- Review counts per user: 10, 9, 8, 9, 7, 7, 5, 5.
- Dates: all 60 `post_date`s are distinct but fall within ~100 seconds on 2026-05-19 (seed artifacts). `post_modified == post_date` for all. "Most recent" is effectively seed order.
- Content is 181–483 chars of plain `<p>` HTML.

### Users

| wp_id | login | display_name | role (`wp_capabilities`) | email |
|---|---|---|---|---|
| 1 | admin | admin | administrator | admin@example.com |
| 2–9 | sarah_k, mike_t, jenny_w, david_l, anna_r, roberto_g, maya_p, kenji_o | Sarah K., Mike T., … | subscriber | `<first>@example.com` |

- `first_name` / `last_name` are empty for everyone. `user_url` is set only for admin. `user_status = 0` for all.
- Usermeta beyond `wp_capabilities` / `wp_user_level` is WP admin UI preferences (`admin_color`, `rich_editing`, …) plus `_yoast_wpseo_profile_updated`. **Drop.**

## 6. ACF `average_rating` vs reality (D-008)

| Brand | Reviews | Computed avg | ACF avg | Δ |
|---|---|---|---|---|
| acme-insurance | 12 | **3.92** | 4.2 | −0.28 |
| primepath-bank | 12 | **3.83** | 4.0 | −0.17 |
| homeshield-pro | 12 | **3.08** | 3.9 | **−0.82** |
| swiftstream-internet | 12 | **3.50** | 3.5 | 0 |
| urbanretail-co | 12 | **3.67** | 4.4 | **−0.73** |

- **4 of 5 ACF values are wrong**, and they change the ordering:
  - ACF order: UrbanRetail, Acme, PrimePath, HomeShield, SwiftStream.
  - Real order: Acme, PrimePath, UrbanRetail, SwiftStream, HomeShield.
- The WP theme sorts "Featured Brands" by the ACF value (`orderby meta_value_num`), so **the live WP site shows stale ratings and ranks.**
- This is concrete evidence for D-008 (derive from reviews), and the import's mismatch report will show exactly these 4 rows.
- Since every brand has 12 reviews, sorting by `review_count` currently produces a full tie, broken by `name` (D-013). Worth knowing before demoing the sort.

## 7. Short description: no stored source (needs a decision)

- Brand `post_excerpt` is empty everywhere. The REST API's `excerpt.rendered` is WP's **auto-generated** 55-word excerpt, not stored data.
- The theme's card "excerpt" is computed at render time: `wp_trim_words(wp_strip_all_tags(post_content), 22)` (brands on the homepage and archive). Reviews use 24 words on the homepage and 40 in the archive.
- Pillar 2 needs `short_description` per row, and D-015 makes it **editable** via `PATCH`, so it must be a stored column. Open questions for the owner:
  1. **Seed value:** the theme's rule (first 22 words of stripped content), the Yoast `metadesc` (written as a description, ~150 chars), or empty?
  2. **Re-import semantics:** a re-run of `import_wp` would overwrite a description an editor changed via `PATCH`. Options:
     - overwrite (WP stays the source of truth until cutover);
     - set only on create;
     - track whether it was edited in Django and skip edited rows.

## 8. Slugs and URLs (D-012)

- All brand/review slugs are unique within type and match `^[a-z0-9-]+$`. There are no brand/review collisions. Max length: brand 20, review 51.
- No `_wp_old_slug` meta exists, so there are no redirects to carry over.
- Site options: `permalink_structure=/%postname%/`, `show_on_front=page` (`page_on_front=4`), `posts_per_page=10`, timezone UTC (`gmt_offset=0`, no `timezone_string`).

## 9. Content format and encoding

- Brand and review bodies use only `<p>` tags (75 pairs). There are no Gutenberg block comments, shortcodes, images or links.
- The only non-ASCII character is the em dash `—` (16 occurrences). The DB is utf8mb4.
- Rendering stored HTML in Django needs `|safe` (or equivalent). **Open question:** sanitize on import with an allow-list (e.g. `nh3`), or trust WP editors? The data is trivially safe today, but the import should define the rule.

## 10. Theme behavior worth matching (for spec 4)

- **Homepage:**
  - hero (`<h1>Honest reviews of consumer brands</h1>`);
  - "Featured Brands": 6 brands by ACF avg desc (should become the computed avg);
  - "Recent Reviews": 6 newest reviews, with rating, reviewer name, location and a 24-word excerpt.
- **Brand detail:** website / founded / HQ meta, rating, body, and all reviews newest first (`cr_get_reviews_for_brand`, limit 100).
- **Review detail:** back-link to its brand, rating, reviewer name/location, body.
- `/brand/` and `/review/` archives exist in WP (CHALLENGE.md only requires the three pages above; `/brand/` is where `<BrandList />` mounts, D-020/D-022).

## 11. REST API vs direct DB (D-011)

- **REST exposes all content we need:** ACF fields (under `acf`), industry ids, Yoast data (`yoast_head_json`), and authors.
- **REST does not expose** password hashes, roles/capabilities or emails (the public `/users` returns only `id`, `name`, `slug`, `url`, `description`, avatars). The auth import (D-007) therefore **requires DB access**.
- D-011's "REST hides some meta" rationale is weak for content. The real reasons are users/passwords, transactional consistency, and no HTTP paging.

## 12. WordPress password hashing, verified against WP 6.9.4 source (D-007)

From `wp-includes/pluggable.php` in the running container:

- **Hashing** (`wp_hash_password`): `'$wp' . password_hash(base64_encode(hash_hmac('sha384', trim($password), 'wp-sha384', true)), PASSWORD_BCRYPT)`. Passwords longer than 4096 bytes return `'*'`. Uses `$wp_hasher->HashPassword(trim($password))` if a global hasher is set.
- **Checking** (`wp_check_password`), in this order:
  1. `strlen($hash) <= 32` → **plain MD5** (`hash_equals($hash, md5($password))`). This is a legacy format that D-007 doesn't list.
  2. Global `$wp_hasher` set → phpass `CheckPassword`.
  3. Password longer than 4096 bytes → false.
  4. Starts with `$wp` → `password_verify(base64(HMAC-SHA384), substr($hash, 3))`.
  5. Starts with `$P$` → phpass portable (`PasswordHash(8, true)`). `$H$` is **not** routed to phpass by core.
  6. Otherwise → `password_verify($password, $hash)` (vanilla bcrypt/argon from plugins).
- **Trim:** `wp_check_password` does **not** trim, but the login path does (`wp_authenticate`: `$password = trim($password)`), and hashing trims. To match real WP logins, the Django hasher must strip the password with **PHP `trim()` semantics** (`" \t\n\r\0\x0B"`, not Python's broader `str.strip()`) before verifying.
- **Seed data:** all 9 users are `$wp$2y$10$…` (cost 10, 63 chars). Python `bcrypt.checkpw` needs a `$2y$` compatibility test.
- Known-answer fixtures can be generated with `make wp ARGS="eval 'echo wp_hash_password(\"…\");'"`.

## 13. Impact on decisions

| Decision | Status after discovery |
|---|---|
| D-007 roles | **Confirmed:** `administrator` → `editor` (1 user), `subscriber` → `reader` (8). **Amend:** add the plain-MD5 format, PHP-`trim()` before verify, the 4096-byte limit; `$P$` only (match core). |
| D-008 | **Strongly supported:** 4/5 ACF averages are stale (§6). |
| D-009 | **Confirmed.** `reviewer_location` stays on `Review` (varies per review). `reviewer_name` always equals the author's `display_name`, so `Reviewer.display_name` comes from `wp_users.display_name`. **Open:** keep `Review.reviewer_name` as a redundant as-submitted value, or drop it. |
| D-010 | **Confirmed with amendment:** there are no extra Yoast keys, so `seo_extra` JSON would always be empty. Suggest dropping it. Yoast tables are dropped. |
| D-011 | **Decision unchanged; rationale corrected** (§11). |
| D-012 | **Confirmed:** all `publish`, slugs clean and unique, no old slugs. |
| D-013 | All brands have 12 reviews, so the `review_count` sort is a full tie in the seed data. Single industry per brand confirmed. |
| D-014 | Works. 3–5 five-star candidates per brand, distinct dates, so the "most recent" tiebreak is deterministic (but reflects seed order). |
| D-015 | **Blocked on §7:** `short_description` needs a stored column, a seed rule and re-import semantics. |
| D-027 | 5 industries, each with 1 brand. The "zero-brand industries" question is moot for this data. Exclude the `category` taxonomy. |
| New | HTML sanitization rule for imported content (§9). Multi-industry handling in the import (§4). |
