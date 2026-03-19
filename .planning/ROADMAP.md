# Roadmap: Reconnect

## Milestones

- ✅ **v1.0 Actionable PWA + Rich Email Digests** — Phases 1-3 (shipped 2026-03-09)
- ✅ **v1.1 Network Intelligence** — Phases 4-6 (shipped 2026-03-10)
- ✅ **v1.2 Intent-Driven Triage** — Phases 7-11 (shipped 2026-03-13)
- 🚧 **v1.3 Contact Discovery** — Phases 12-14 (in progress)

## Phases

<details>
<summary>✅ v1.0 Actionable PWA + Rich Email Digests (Phases 1-3) — SHIPPED 2026-03-09</summary>

- [x] Phase 1: Infrastructure Foundations (2/2 plans) — completed 2026-03-08
- [x] Phase 2: Email Reliability (2/2 plans) — completed 2026-03-09
- [x] Phase 3: PWA Feature Completeness (3/3 plans) — completed 2026-03-09

See: `.planning/milestones/v1.0-ROADMAP.md` for full details.

</details>

<details>
<summary>✅ v1.1 Network Intelligence (Phases 4-6) — SHIPPED 2026-03-10</summary>

- [x] Phase 4: Foundation Fixes + Queue UX (3/3 plans) — completed 2026-03-09
- [x] Phase 5: Dashboard Intelligence (2/2 plans) — completed 2026-03-09
- [x] Phase 6: CLI + Gmail OAuth + Streamlit Removal (2/2 plans) — completed 2026-03-10

See: `.planning/milestones/v1.1-ROADMAP.md` for full details.

</details>

<details>
<summary>✅ v1.2 Intent-Driven Triage (Phases 7-11) — SHIPPED 2026-03-13</summary>

- [x] Phase 7: Signal Foundation (2/2 plans) — completed 2026-03-12
- [x] Phase 8: Email + Signal UI + Profile Content (4/4 plans) — completed 2026-03-12
- [x] Phase 9: Goals, Sync, and Pipeline Intelligence (3/3 plans) — completed 2026-03-12
- [x] Phase 10: Draft Tone Adaptation (2/2 plans) — completed 2026-03-13
- [x] Phase 11: Signal Write Completion + Draft Wiring (1/1 plan) — completed 2026-03-13

See: `.planning/milestones/v1.2-ROADMAP.md` for full details.

</details>

### 🚧 v1.3 Contact Discovery (In Progress)

**Milestone Goal:** Enable finding specific people in your network by enriching contacts comprehensively and adding flexible search/browse capabilities to the PWA.

- [x] **Phase 12: Enrichment Audit and Schema Extraction** — Diagnose coverage gaps, extract 7 enrichment fields to queryable columns, backfill all existing contacts (completed 2026-03-16)
- [x] **Phase 13: Contacts Browse Page** — Paginated contacts list with role, industry, and location filters; explicit field selection; server-side pagination (completed 2026-03-18)
- [ ] **Phase 14: Search Bar** — Full-text search across name, role, company, location, and school with debounce and result count

## Phase Details

### Phase 12: Enrichment Audit and Schema Extraction
**Goal**: Enrichment fields needed for search and browse (education, industry, headline, city, school, seniority) exist as queryable first-class columns in both SQLite and Supabase, all existing contacts are backfilled, and the pipeline writes these columns on every future enrichment run
**Depends on**: Nothing (first phase of milestone)
**Requirements**: ENRICH-01, ENRICH-02, ENRICH-03, ENRICH-04
**Success Criteria** (what must be TRUE):
  1. Running `reconnect contacts stats --enrichment` prints coverage percentages for education, industry, skills, and location across all contacts
  2. After the Supabase migration runs, `connections` has columns for `enriched_industry`, `enriched_headline`, `enriched_city`, `enriched_country`, `enriched_school`, `enriched_seniority`, and `education_text` — all queryable via PostgREST without touching `raw_enrichment`
  3. Every existing contact whose `raw_enrichment` contains education, industry, or location data has those fields populated in the new columns without any new API calls
  4. A contact enriched after this phase completes has all 7 new columns written at enrichment time alongside the existing `current_role` and `current_company` fields
**Plans:** 2/2 plans complete
Plans:
- [ ] 12-01-PLAN.md — Schema + extraction core module + Supabase migration
- [ ] 12-02-PLAN.md — Pipeline wiring + CLI commands + tests

### Phase 13: Contacts Browse Page
**Goal**: Users can navigate to a Contacts page in the PWA and browse all non-archived contacts with role, industry, and location filters — returned via server-side pagination with no `raw_enrichment` in the payload
**Depends on**: Phase 12
**Requirements**: BROWSE-01, BROWSE-02, BROWSE-03, BROWSE-04, BROWSE-05
**Success Criteria** (what must be TRUE):
  1. A Contacts tab appears in the PWA nav and navigates to `/contacts` showing a paginated list of all non-archived contacts
  2. Selecting a role/title filter narrows the contact list to contacts whose role contains that text
  3. Selecting an industry filter narrows the contact list to contacts in that industry using the `enriched_industry` column
  4. Selecting a location filter narrows the contact list to contacts in that city or country
  5. Loading more contacts uses server-side `.range()` pagination — no single request fetches more than the page size, and `raw_enrichment` is never included in the payload
**Plans:** 2/2 plans complete
Plans:
- [ ] 13-01-PLAN.md — Nav tab, route wiring, CSS classes, validation tests
- [ ] 13-02-PLAN.md — contacts.js browse module (filter, paginate, render) + visual checkpoint

### Phase 14: Search Bar
**Goal**: Users can type a query into a search bar on the Contacts page and see matching contacts across name, role, company, location, and school simultaneously, with results updating as they type and a result count displayed
**Depends on**: Phase 13
**Requirements**: SEARCH-01, SEARCH-02
**Success Criteria** (what must be TRUE):
  1. Typing "University of Miami" in the search bar returns contacts who attended that school, even when no filter is active
  2. Typing a combined query (e.g., "Sales Miami") returns contacts matching all terms across name, role, company, location, and school simultaneously
  3. Search results update automatically after the user pauses typing (debounced input — not on every keystroke), and a result count ("12 contacts") is displayed below the search bar
**Plans:** 1/2 plans executed
Plans:
- [ ] 14-01-PLAN.md — Test scaffolding + tsvector migration + Phase 13 test updates
- [ ] 14-02-PLAN.md — Search bar implementation (contacts.js + CSS) + visual checkpoint

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Infrastructure Foundations | v1.0 | 2/2 | Complete | 2026-03-08 |
| 2. Email Reliability | v1.0 | 2/2 | Complete | 2026-03-09 |
| 3. PWA Feature Completeness | v1.0 | 3/3 | Complete | 2026-03-09 |
| 4. Foundation Fixes + Queue UX | v1.1 | 3/3 | Complete | 2026-03-09 |
| 5. Dashboard Intelligence | v1.1 | 2/2 | Complete | 2026-03-09 |
| 6. CLI + Gmail OAuth + Streamlit Removal | v1.1 | 2/2 | Complete | 2026-03-10 |
| 7. Signal Foundation | v1.2 | 2/2 | Complete | 2026-03-12 |
| 8. Email + Signal UI + Profile Content | v1.2 | 4/4 | Complete | 2026-03-12 |
| 9. Goals, Sync, and Pipeline Intelligence | v1.2 | 3/3 | Complete | 2026-03-12 |
| 10. Draft Tone Adaptation | v1.2 | 2/2 | Complete | 2026-03-13 |
| 11. Signal Write Completion + Draft Wiring | v1.2 | 1/1 | Complete | 2026-03-13 |
| 12. Enrichment Audit and Schema Extraction | v1.3 | 2/2 | Complete | 2026-03-16 |
| 13. Contacts Browse Page | v1.3 | 2/2 | Complete | 2026-03-18 |
| 14. Search Bar | 1/2 | In Progress|  | - |
