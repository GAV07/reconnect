---
phase: 14-search-bar
plan: 02
subsystem: ui
tags: [javascript, postgresql, fts, tsvector, search, contacts, pwa, vanilla-js, posrgrest]

# Dependency graph
requires:
  - phase: 14-search-bar-01
    provides: tests/test_phase14_search.py (RED contract), supabase/migrations/20260318000000_fts_column.sql, updated Phase 13 tests
  - phase: 13-contacts-browse-page
    provides: pwa/js/contacts.js (roleQuery state, role filter HTML that gets replaced)
provides:
  - pwa/js/contacts.js — search bar with textSearch('fts'), ilike fallback, 300ms debounce, search-aware count banner, search-aware empty state
  - pwa/css/app.css — .search-input-wrap, .search-icon-svg, .search-input CSS rules
affects: [future-phases-using-contacts-browse]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "PostgREST .textSearch('fts', query, {type:'plain', config:'english'}) for server-side FTS queries"
    - "ilike fallback on fts error: check error.message.includes('fts'), retry with per-term .or() chaining across all searchable columns"
    - "type='search' HTML input for native browser clear button (fires oninput with empty string)"
    - "Inline SVG search icon absolutely positioned within relative-positioned wrapper div"

key-files:
  created: []
  modified:
    - pwa/js/contacts.js
    - pwa/css/app.css

key-decisions:
  - "searchQuery replaces roleQuery in contactFilters — cleaner name aligns with broader multi-field scope"
  - "ilike fallback checks error.message.includes('fts') — only triggers on fts-column-missing errors, not other failures"
  - "loadMoreContacts omits ilike fallback — if initial renderContacts succeeds with textSearch, loadMore will too"
  - "Pre-existing test_gmail_not_configured_without_password failure is out-of-scope, logged to deferred-items.md"

patterns-established:
  - "Search-aware count banner: conditional on contactFilters.searchQuery, returns different copy for browse vs search mode"
  - "Search-aware empty state: two branches — search-specific message with query in quotes, vs generic filter no-results"

requirements-completed: [SEARCH-01, SEARCH-02]

# Metrics
duration: 3min
completed: 2026-03-19
---

# Phase 14 Plan 02: Search Bar Implementation Summary

**Multi-field contacts search bar with textSearch('fts') primary path, multi-column ilike fallback, 300ms debounce, inline SVG icon, and search-aware count/empty-state messages**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-19T03:08:20Z
- **Completed:** 2026-03-19T03:11:00Z
- **Tasks:** 1 of 2 complete (Task 2 is human-verify checkpoint)
- **Files modified:** 2

## Accomplishments

- Replaced role/title filter input with full-text search bar in `pwa/js/contacts.js`
- `contactFilters.searchQuery` replaces `roleQuery`; `onContactSearchInput` replaces `onContactRoleInput` with 300ms debounce
- `renderContacts()` uses `.textSearch('fts', query, {type:'plain', config:'english'})` as primary path
- ilike fallback triggers on fts-column errors — splits multi-word query, chains `.or()` per term across name, current_role, current_company, enriched_city, enriched_school
- `buildCountBanner()` shows `X contacts match "query"` when search active; `Showing X of Y contacts` when browsing
- Empty state shows query-specific message: `No contacts match "[query]". Try different keywords or clear your search.`
- `clearContactFilters()` resets `searchQuery` (not `roleQuery`)
- Datalist `role-suggestions` and `onContactRoleInput` entirely removed
- `type="search"` input with inline SVG magnifying glass icon (`.search-icon-svg` absolutely positioned inside `.search-input-wrap`)
- Added `.search-input-wrap`, `.search-icon-svg`, `.search-input` CSS rules to `app.css`
- All 12 Phase 14 tests pass; all 12 Phase 13 tests pass; 205 other tests pass

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement search bar in contacts.js and CSS** - `68a8029` (feat)
2. **Task 2: Verify search bar works end-to-end** — PENDING human verification

## Files Created/Modified

- `pwa/js/contacts.js` — Search bar replaces role filter: searchQuery state, onContactSearchInput, textSearch('fts') primary query, ilike fallback, search-aware count banner + empty state, clearContactFilters reset
- `pwa/css/app.css` — Added .search-input-wrap (relative+flex), .search-icon-svg (absolute, left:8px, 16x16), .search-input (padding-left:28px)

## Decisions Made

- `searchQuery` replaces `roleQuery` — cleaner naming for the broader multi-field search scope
- ilike fallback only triggers when `error.message.includes('fts')` — avoids masking real errors with a fallback retry
- `loadMoreContacts` omits ilike fallback — if initial `renderContacts` succeeds via textSearch, load-more will too; avoids duplicate fallback code
- Pre-existing `test_gmail_not_configured_without_password` failure confirmed out-of-scope and logged to `deferred-items.md`

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

Pre-existing failing test `tests/test_phase1_infra.py::test_gmail_not_configured_without_password` found during full suite run. Confirmed pre-existing (fails on main before Phase 14 changes via `git stash` verification). Logged to `.planning/phases/14-search-bar/deferred-items.md`. Not caused by Phase 14 changes.

## User Setup Required

- Apply Supabase migration before testing: paste `supabase/migrations/20260318000000_fts_column.sql` into Supabase Dashboard > SQL Editor > Run. Verify: `SELECT fts FROM connections LIMIT 1;` returns a tsvector value.
- If migration not applied, search falls back to ilike (still functional, different matching behavior for short queries)

## Next Phase Readiness

- Phase 14 is functionally complete pending human verification (Task 2 checkpoint)
- After user verifies search bar behavior at https://eg-connect.netlify.app, Phase 14 is done
- `supabase/migrations/20260318000000_fts_column.sql` must be applied to Supabase for textSearch to work (ilike fallback available if not)

## Self-Check: PASSED

- FOUND: pwa/js/contacts.js (modified)
- FOUND: pwa/css/app.css (modified)
- FOUND: .planning/phases/14-search-bar/14-02-SUMMARY.md (this file)
- FOUND: 68a8029 (Task 1 commit)

---
*Phase: 14-search-bar*
*Completed: 2026-03-19*
