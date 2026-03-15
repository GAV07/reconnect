# Project Research Summary

**Project:** Reconnect — v1.3 Contact Discovery
**Domain:** Personal networking CRM — contact search, browse, and enrichment completeness
**Researched:** 2026-03-14
**Confidence:** HIGH

## Executive Summary

Reconnect v1.3 adds contact discovery capabilities to an existing, working personal CRM. The core problem is straightforward: enrichment data that matters for search (education, industry, skills) is buried in a `raw_enrichment` JSONB column that neither PostgREST nor clean client-side filtering can work with. The solution is to extract those fields into first-class text columns during the enrichment pipeline write step, which unlocks both server-side filtering and full-text search without any new infrastructure. The pipeline already does this for `current_role`, `current_company`, and `location` — v1.3 extends that pattern to cover industry, headline, school, seniority, and a denormalized `education_text` string.

The critical design decision — and the primary tension across research outputs — is the search implementation strategy. The STACK researcher recommends Fuse.js (client-side fuzzy search, CDN-loaded, zero infrastructure, no migrations, instant in-memory results). The ARCHITECTURE researcher recommends PostgreSQL `tsvector` with a generated column and GIN index (server-side, scalable, handles structured plus free-text in one PostgREST call). Both approaches are technically sound but have different prerequisites and tradeoffs. **The recommended path is a hybrid: extract enrichment fields to real columns first (both approaches require this), then use PostgreSQL `tsvector` for the search implementation.** The `tsvector` approach handles the full contact base without a row-limit problem, avoids fetching thousands of rows on browse view load, and supports server-side pagination natively. The only additional complexity is a `GENERATED ALWAYS AS ... STORED` column in Supabase migration SQL — which research explicitly warns must not go in `models.py` due to SQLite incompatibility. If that constraint is respected, the server-side approach is cleaner for long-term use. Fuse.js remains the right fallback if the tsvector migration proves problematic during execution.

The primary risks for this milestone are not architectural but operational: the PostgREST 1000-row hard limit silently truncating contact lists, re-enriching contacts with permanently unfetchable fields (wasting daily API budget), and the SQLite/PostgreSQL schema split that means generated columns must live only in migration SQL files. All three risks have well-defined prevention strategies documented in research. The enrichment planner also needs explicit budget allocation before a "completeness for search" tier is added, or that new tier will crowd out queue-quality enrichment.

---

## Key Findings

### Recommended Stack

The v1.3 stack requires no new Python packages, no new Edge Functions, and no new enrichment providers. All search-relevant data already comes from the existing RapidAPI `fresh-linkedin-profile-data` provider — it returns `educations[]`, `skills[]`, `experiences[]`, and `company_industry` already. The gap is extraction, not acquisition.

For the browse/search UI, a new `pwa/js/contacts.js` module is added following the existing `queue.js` and `contact.js` patterns. One Supabase Dashboard configuration change is required regardless of search approach: `max_rows` must be increased from 1000 to 5000, or server-side pagination must be implemented.

**Core technologies — existing, unchanged:**
- Python 3.11 + SQLModel 0.0.31 + Click 8.3.1 — pipeline (no change)
- Supabase PostgreSQL + PostgREST — cloud database and REST API (config change: `max_rows`)
- Vanilla JS + CDN — PWA (additive only: new `contacts.js` module and nav tab)
- RapidAPI `fresh-linkedin-profile-data` — enrichment provider (already returns all needed fields)

**Search implementation — choose one approach, decision point is at Phase 2 completion:**

| Approach | Complexity | Prerequisites | Tradeoffs |
|----------|-----------|---------------|-----------|
| PostgreSQL `tsvector` (RECOMMENDED) | MEDIUM | Extracted columns migration + Supabase-only generated column | Server-side filtering + pagination, no row-limit issue, handles structured + free-text in one query |
| Fuse.js 7.1.0 via CDN (FALLBACK) | LOW | PostgREST `max_rows` increase or pagination loop | Zero infrastructure, instant UX, no migration, but requires full dataset fetch on browse load |

The Fuse.js approach is fully specified in STACK.md including CDN URL (`https://cdn.jsdelivr.net/npm/fuse.js@7.1.0/dist/fuse.mjs`), configuration weights, and the `_education` flattening pattern. It is a viable fallback that delivers the same user-facing result if the tsvector migration encounters complications.

**v1.3 stack additions:**
- New `pwa/js/contacts.js` PWA module (browse + search page)
- `/contacts` route in `app.js`
- Contacts nav tab in `index.html`
- Supabase migration: 7 extracted enrichment columns + `fts` generated tsvector + GIN index + B-tree indexes
- `models.py` `Connection`: 7 new TEXT/INTEGER fields (not `fts` — SQLite incompatibility)
- `push.py` `CONNECTION_SYNC_FIELDS`: 7 new fields added
- `rapidapi_linkedin.py` `update_connection_from_profile()`: extraction logic added

**No new pip packages. No new Edge Functions. No new enrichment API keys.**

See: `.planning/research/STACK.md`

### Expected Features

The milestone has a clear litmus test: "Find Sales/Marketing people who are University of Miami alum in my network." All features in scope are evaluated against this test case.

**Must have (table stakes):**
- Enrichment coverage diagnostic (`reconnect contacts stats --enrichment`) — gates education and skills filter decisions; run before writing any search UI
- Contacts browse page (`/contacts` route, new `contacts.js`) — foundational; no search or filter feature is meaningful without a page showing the full contact list
- Multi-field search bar — searches `name`, `current_role`, `current_company`, `location`, `education_text` simultaneously; passes the UMiami litmus test
- `education_text` denormalized column — extracts `educations[].school/degree/field_of_study` as a flat concatenated string; required for reliable education search regardless of which search approach is chosen
- Role and industry filters — `current_role` is already indexed; industry requires `enriched_industry` extracted column
- Location filter — `location` is already indexed; `enriched_location_city` adds city-level precision

**Should have (differentiators, add after core works):**
- Seniority filter (`enriched_seniority` derived from `current_role`) — VP/Director/Manager/Senior classification
- Data completeness filter — surfaces contacts to prioritize for enrichment runs; `data_completeness_score` column already exists
- Signal filter on contacts page — `latest_signal` is already synced; just needs the contacts page to render it
- Contact count summary ("12 contacts match") — trivial once the page exists

**Defer to v1.4:**
- Skills filter — only if Phase 1 diagnostic shows >50% of contacts have `skills[]` populated
- Graduation year / cohort filter — only if education coverage is strong (>60%)
- Saved searches / smart lists — 3x the complexity of search itself
- Semantic / AI search (pgvector + embeddings) — explicitly listed in PROJECT.md as v1.3+ potential

**Anti-features (do not build):**
- Server-side `raw_enrichment` JSONB filtering via PostgREST — will fail with operator error; confirmed PostgREST limitation
- `select('*')` for browse view — 15 MB+ payload on mobile, approaches Supabase free-tier 5 GB/month egress
- Per-keystroke PostgREST queries — round-trip latency makes search feel broken
- LLM-based query parsing — ~$0.01/search, adds latency, breaks offline mode
- New enrichment providers for education data — RapidAPI already returns `educations[]`

See: `.planning/research/FEATURES.md`

### Architecture Approach

The architecture is a direct extension of the existing pattern: extract at write time (pipeline), sync to Supabase (push.py), query via PostgREST (PWA). The `fts` generated tsvector column is PostgreSQL-only and must not appear in `models.py` — it lives only in the Supabase migration SQL file and auto-updates via `GENERATED ALWAYS AS ... STORED` whenever source columns change through push.py upserts.

The browse/search page (`contacts.js`) is a distinct module from the queue page (`queue.js`). Queue fetches from `outreach_queue` with a `connections` join; contacts fetches from `connections` directly. They have different semantics, different sort orders, and different filter sets. They must not be merged — the queue is for triage, contacts is for discovery.

**Major components:**

1. **Supabase migration** (`supabase/migrations/20260314000000_enrichment_extraction.sql`) — adds 7 extracted columns, backfills from existing `raw_enrichment` JSONB via UPDATE, adds `fts` tsvector generated column, creates GIN index on `fts` and B-tree indexes on extracted columns
2. **`src/ingestion/rapidapi_linkedin.py` `update_connection_from_profile()`** — extended to write 7 extracted columns at enrichment time (write-time extraction pattern, mirrors existing `current_role` extraction)
3. **`src/sync/push.py` `CONNECTION_SYNC_FIELDS`** — updated to include all 7 extracted columns; `fts` is NOT included (it is a generated column, auto-computes on upsert)
4. **`src/database/models.py` `Connection`** — 7 new SQLModel fields (TEXT/INTEGER only, no `fts`, no generated column expression)
5. **One-time backfill script** — populates extracted columns in SQLite from existing `raw_enrichment` data without API calls
6. **`pwa/js/contacts.js`** — new PWA module: `textSearch('fts', query, { type: 'websearch' })` + `ilike` structured filters + `.range()` server-side pagination

**Key patterns:**
- Extract at write time, not query time — extracted columns are queryable via PostgREST; `raw_enrichment` is preserved intact for profile detail views
- PostgreSQL generated column for `fts` — declarative, zero-maintenance, auto-updates on column changes, GIN-indexed; no trigger needed
- `fts` lives in Supabase only — never map in SQLModel, never write from Python
- Explicit field selection in browse view — `BROWSE_SELECT` constant in `contacts.js`, never `select('*')`
- Pagination at the PostgREST layer — `.range(offset, limit)`, not client-side array slicing

See: `.planning/research/ARCHITECTURE.md`

### Critical Pitfalls

1. **Generated column in `models.py` breaks SQLite** — The `fts tsvector` column must only appear in Supabase migration SQL, never in the SQLModel `Connection` class. Adding it to `models.py` causes `OperationalError: near "GENERATED": syntax error` on the next `init_db()` call. This same constraint was already encountered in v1.2 (partial index in signal foundation migration). All generated columns and GIN indexes must live in `supabase/migrations/*.sql` only.

2. **PostgREST 1000-row hard limit silently truncates contacts** — The default `db-max-rows = 1000` causes PostgREST to return only the first 1000 rows with no error or warning. A contact at row 1001+ disappears from search results. Prevention: implement `.range()`-based pagination in `contacts.js` from the initial implementation, or increase `max_rows` to 5000 in Supabase Dashboard before browse ships.

3. **Re-enrichment loop for permanently unfetchable fields wastes API budget** — Contacts with no LinkedIn education listed will always score low on completeness, but re-enriching them returns the same empty data. Without an "unfetchable" status flag in `missing_data_fields`, the completeness tier burns the daily 30-call API budget on contacts that will never improve, blocking higher-priority contacts. Prevention: add `_is_worth_re_enriching()` guard with `PERMANENTLY_OPTIONAL_FIELDS` set before enabling completeness-based enrichment scheduling.

4. **Education requires a flat denormalized column, not array traversal** — Education is stored as `educations[]` (array of objects) in `raw_enrichment`. Neither PostgREST nor a `tsvector` generated column can aggregate values from a JSONB array using `GENERATED ALWAYS AS` — the expression cannot call set-returning functions over array elements. Prevention: write `education_text TEXT` as a regular pipeline-written column containing a concatenated string of all education entries; the `fts` generated column then includes `education_text` as a source.

5. **`select('*')` for browse view causes mobile payload and egress problems** — `raw_enrichment` averages 15-30 KB per contact. Fetching 500+ contacts with `select('*')` produces a 7.5-15 MB payload — unacceptable on mobile and approaches Supabase free-tier 5 GB/month egress on daily use. Prevention: define `BROWSE_SELECT` as an explicit column list in `contacts.js` that excludes `raw_enrichment`, `activity_log`, and `score_reasoning`.

See: `.planning/research/PITFALLS.md`

---

## Implications for Roadmap

Research converges on a strict build order: schema and pipeline extraction must precede the browse/search UI, and the enrichment planner must be guarded before completeness-based scheduling is enabled. The diagnostic runs first because it gates the education and skills filter decisions.

### Phase 1: Enrichment Coverage Audit

**Rationale:** Run before writing any code. Education coverage (estimated 50-75% for college-era contacts, lower for purely professional contacts) determines whether the education filter is a viable v1.3 feature or should be deferred to v1.4. Skills coverage determines the same for skills filtering. This is a 1-2 hour diagnostic step that prevents building features on sparse data.
**Delivers:** Education and skills coverage percentages from production data; go/no-go decision for education filter and skills filter in v1.3; CLI command `reconnect contacts stats --enrichment`
**Addresses:** FEATURES.md — "enrichment coverage verification gates everything"
**Avoids:** Pitfall 7 (completeness score counting unfetchable fields as gaps), Pitfall 4 (re-enrichment loops)
**Research flag:** No additional research needed — diagnostic is a SQL query against existing production data

### Phase 2: Schema Migration and Enrichment Extraction

**Rationale:** This is the hard dependency for all subsequent phases. No browse page can be built, no search can work, and no server-side filters can execute until extracted columns exist in both Supabase and SQLite. The SQL migration backfills existing contacts from their existing `raw_enrichment` JSONB — so Phase 3's browse page immediately has populated data without requiring any API calls.
**Delivers:** Supabase migration with 7 extracted columns + `fts` tsvector generated column + GIN index + B-tree indexes + JSONB backfill UPDATE; `Connection` model updated (7 fields, no `fts`); `update_connection_from_profile()` writes extracted columns; one-time SQLite backfill script; `push.py` sync includes new fields
**Addresses:** ARCHITECTURE.md Phase 1 (schema + extraction); FEATURES.md — `education_text` extraction, `enriched_school` column, `enriched_industry` column
**Avoids:** Pitfall 1 (generated column in `models.py` — `fts` goes in migration SQL only), Pitfall 2 (PostgREST JSONB filtering bypassed by extracted columns), Pitfall 5 (education array traversal — `education_text` flat column written by pipeline), Pitfall 11 (sync field coverage — new columns added to `CONNECTION_SYNC_FIELDS` in same step)
**Research flag:** No additional research needed — migration SQL is fully specified in ARCHITECTURE.md with exact column names, JSONB path expressions, and index definitions

### Phase 3: Contacts Browse Page (Filters and Pagination, No Search Yet)

**Rationale:** Build the contacts page with structured filters and server-side pagination first, without the search bar. This validates that the data pipeline is producing correct extracted column data before search complexity is added on top. It also validates the PostgREST row limit fix and the explicit field selection pattern.
**Delivers:** `pwa/js/contacts.js` with paginated list of all non-archived contacts; role/industry/location/signal filter chips; explicit `BROWSE_SELECT` field list (no `raw_enrichment`); `/contacts` route in `app.js`; Contacts nav tab in `index.html`; server-side `.range()` pagination with load-more
**Addresses:** FEATURES.md must-have table stakes (contacts browse page, role filter, location filter, signal filter, industry filter)
**Avoids:** Pitfall 3 (PostgREST 1000-row limit — pagination implemented from day one), Pitfall 10 (`select('*')` egress — explicit field list), Pitfall 6 (per-keystroke mobile lag — no search input yet)
**Research flag:** No additional research needed — implementation patterns are fully specified in ARCHITECTURE.md with exact PostgREST query shapes

### Phase 4: Full-Text Search Bar

**Rationale:** Search is built on top of a working browse page (Phase 3) and populated extracted columns (Phase 2). The `fts` GIN index is already in place from the Phase 2 migration. This phase wires `textSearch('fts', query, { type: 'websearch' })` into the existing contacts page query builder alongside the existing structured filters.
**Delivers:** Search input with 200ms debounce; `textSearch` PostgREST call against `fts` column; combined structured + free-text query in single PostgREST request; result count display; empty state for no results; DocumentFragment-based DOM render for mobile performance; passes UMiami litmus test ("University of Miami" + industry filter)
**Addresses:** FEATURES.md — multi-field search bar (must-have); STACK.md — search implementation decision
**Avoids:** Pitfall 6 (per-keystroke DOM rebuild on mobile — 200ms debounce + 50-result display limit), Pitfall 8 (undefined query model — document comma-split AND logic in search placeholder text)
**Research flag:** No additional research needed — `textSearch` PostgREST API behavior verified against Supabase docs; `websearch_to_tsquery` behavior confirmed

**Note on Fuse.js as fallback:** If the Phase 2 tsvector migration encounters problems (e.g., unexpected errors on edge-case `raw_enrichment` shapes, generated column expression failures), switch to Fuse.js 7.1.0. The fallback requires increasing `max_rows` to 5000 in Supabase Dashboard and fetching all contacts on page load. The full Fuse.js implementation is specified in STACK.md, including CDN URL, weight configuration, and the `_education` flattening approach. The decision point is at Phase 2 completion — validate that `fts` is populated on the Supabase side before proceeding.

### Phase 5: Enrichment Planner Hardening

**Rationale:** Completeness-based enrichment improvements must not be enabled until the "unfetchable" guard and explicit budget allocation percentages are in place. Without these guards, a new completeness tier will exhaust the daily API budget on contacts with permanently sparse LinkedIn profiles, blocking queue-quality enrichment.
**Delivers:** `_is_worth_re_enriching()` guard in `enrichment_planner.py` with `PERMANENTLY_OPTIONAL_FIELDS` set (education, school, degree); "unfetchable" status in `missing_data_fields` JSON; explicit percentage budget allocation per tier (priority contacts 30%, email finding 25%, activity refresh 20%, completeness for search 15%, re-enrichment 10%); `X-RateLimit-Requests-Remaining` logging from RapidAPI response headers
**Addresses:** FEATURES.md — data completeness filter (differentiator); PITFALLS.md Pitfalls 4, 7, and 9
**Avoids:** API budget exhaustion before queue-priority contacts are enriched; completeness sort surfacing permanently-empty contacts in the browse UI
**Research flag:** Review current `plan_enrichment()` tier structure in `enrichment_planner.py` before refactoring — the budget allocation logic needs to be understood before percentages are introduced

### Phase Ordering Rationale

- Phase 1 (diagnostic) must run before any code is written; it gates which features are worth building
- Phase 2 (schema) must precede Phase 3 (browse) — the columns the browse page queries must exist in Supabase and be populated
- Phase 3 (browse without search) must precede Phase 4 (search) — search is added to an already-working, already-paginated contacts page
- Phase 5 (enrichment planner) is parallel-eligible with Phases 3-4 on the Python/pipeline side, but must complete before completeness-based sorting is surfaced in the browse UI as a filter option
- The build order matches ARCHITECTURE.md Steps 1-8 exactly

### Research Flags

Phases with well-documented patterns (no additional research needed):
- **Phase 1 (audit):** Diagnostic SQL query against existing production data
- **Phase 2 (schema):** Full migration SQL specified in ARCHITECTURE.md; generated column syntax verified against PostgreSQL official docs; JSONB backfill expressions verified
- **Phase 3 (browse):** PostgREST query patterns verified in ARCHITECTURE.md; pagination pattern verified against PostgREST v12 docs
- **Phase 4 (search):** `textSearch` PostgREST API verified; `websearch_to_tsquery` behavior confirmed in Supabase FTS docs

Phases that benefit from deeper review before execution:
- **Phase 5 (enrichment planner):** Current `plan_enrichment()` budget allocation structure was reviewed at a high level but not deeply analyzed; budget refactoring may surface unexpected coupling with daily pipeline step ordering or existing tier definitions

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Direct codebase inspection; npm version verification for Fuse.js 7.1.0; PostgREST row-limit confirmed from Supabase community discussions; CDN URL verified via jsDelivr |
| Features | HIGH | Codebase analysis confirms field availability; PostgREST filter operator behavior confirmed from official docs; education coverage estimate is LOW-MEDIUM (no authoritative stat, derived from LinkedIn data product descriptions — validate via Phase 1 diagnostic) |
| Architecture | HIGH | All claims grounded in direct source-code inspection; PostgreSQL generated column syntax verified from official docs; PostgREST `textSearch` and `ilike` behavior verified from official docs and community discussions; SQLite incompatibility of generated columns confirmed |
| Pitfalls | HIGH (architecture-specific); MEDIUM (enrichment API costs) | Architecture pitfalls confirmed by codebase review (SQLite incompatibility, PostgREST JSONB limitation, row limit). RapidAPI free-tier exact limits are not publicly documented — cost estimates based on paid-plan pricing; empirical measurement recommended |

**Overall confidence:** HIGH

### Gaps to Address

- **Education coverage is unknown until Phase 1 diagnostic runs.** If coverage is below 40%, the education filter should be deferred to v1.4. The Phase 2 migration can still add `education_text` and `enriched_school` columns (the backfill script will populate them from existing `raw_enrichment`), but the browse UI education filter chip should be conditional on diagnostic results.

- **The `tsvector` vs Fuse.js decision should be validated at Phase 2 completion.** If the migration succeeds and `fts` is confirmed populated on the Supabase side, proceed with `textSearch`. If there are complications (edge-case `raw_enrichment` shapes causing generated column expression errors), fall back to Fuse.js. Do not attempt to build both simultaneously.

- **RapidAPI free-tier exact request limits are not publicly documented.** The pipeline should log `X-RateLimit-Requests-Remaining` from response headers to surface the actual limit empirically. Until that data exists, assume 30 calls/day is the effective budget ceiling.

- **Skills coverage is unknown.** Skills are opt-in endorsements with MEDIUM estimated coverage. Defer skills filter to v1.4 unless the Phase 1 diagnostic shows >50% of contacts have `skills[]` populated.

---

## Sources

### Primary (HIGH confidence — direct codebase inspection)
- `src/database/models.py` — Connection model, field inventory, existing indexes
- `src/ingestion/rapidapi_linkedin.py` — enrichment field extraction, `raw_enrichment` shape, mock API response structure
- `src/sync/push.py` — `CONNECTION_SYNC_FIELDS`, sync patterns
- `src/pipeline/enrichment_planner.py` — enrichment budget and tier logic
- `src/llm/data_analyzer.py` — completeness scoring, `FIELD_WEIGHTS`
- `pwa/js/queue.js` — PostgREST query patterns, client-side filter patterns, `raw_enrichment` access patterns
- `pwa/js/contact.js` — `raw_enrichment` rendering, PostgREST read patterns
- `pwa/js/app.js` — router structure, Supabase client initialization
- `supabase/migrations/20260305000000_pwa_overhaul.sql` — migration pattern reference
- `.planning/PROJECT.md` — v1.3 requirements, existing key decisions, out-of-scope list

### Primary (HIGH confidence — official documentation verified)
- [PostgreSQL Generated Columns](https://www.postgresql.org/docs/current/ddl-generated-columns.html) — GENERATED ALWAYS AS STORED syntax, SQLite incompatibility
- [Supabase Full Text Search Guide](https://supabase.com/docs/guides/database/full-text-search) — tsvector + GIN index pattern
- [Supabase JS textSearch reference](https://supabase.com/docs/reference/javascript/textsearch) — `websearch_to_tsquery` behavior
- [PostgREST Tables and Views v12](https://docs.postgrest.org/en/v12/references/api/tables_views.html) — ilike, eq, or, textSearch operators
- [PostgREST Pagination docs](https://docs.postgrest.org/en/v12/references/api/pagination_count.html) — max-rows hard limit, range-based pagination

### Secondary (MEDIUM confidence — community sources, multiple agreement)
- [Supabase Discussion #6778](https://github.com/orgs/supabase/discussions/6778) — multi-column ilike via `.or()`, limitations on JSONB path filtering
- [PostgREST Issue #240](https://github.com/PostgREST/postgrest/issues/240) — JSONB filtering limitation confirmed
- [Fuse.js npm](https://www.npmjs.com/package/fuse.js) — version 7.1.0, ESM build at `fuse.mjs` (~23KB minified)
- [Fuse.js GitHub Issue #282](https://github.com/krisk/Fuse/issues/282) — performance at scale: 5K records expected < 100ms
- [Supabase Discussion #3765](https://github.com/orgs/supabase/discussions/3765) — `max_rows` default 1000, configurability in Dashboard
- [RapidAPI fresh-linkedin-profile-data pricing](https://rapidapi.com/freshdata-freshdata-default/api/fresh-linkedin-profile-data/pricing) — $0.0065/call overage on Ultra plan
- [Supabase free tier limits](https://uibakery.io/blog/supabase-pricing) — 500 MB storage, 5 GB/month egress

### Tertiary (LOW confidence — estimates or inferred)
- LinkedIn education data coverage: estimated 50-75% for college-era connections — no authoritative stat; validate via Phase 1 diagnostic
- RapidAPI free-tier request limits: not publicly documented; empirical measurement via `X-RateLimit-Requests-Remaining` headers recommended

---

*Research completed: 2026-03-14*
*Ready for roadmap: yes*
