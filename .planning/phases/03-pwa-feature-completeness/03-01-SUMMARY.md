---
phase: 03-pwa-feature-completeness
plan: 01
subsystem: testing, database
tags: [pytest, sqlmodel, dashboard, funnel, tdd, monkeypatch]

# Dependency graph
requires:
  - phase: 02-email-reliability
    provides: Existing test patterns (conftest.py, monkeypatch fixtures, mock session helpers)
provides:
  - Phase 3 test scaffold with 7 tests covering VIEW-01/02, PROFILE-01/02/03/04, VIEW-03
  - Funnel stage counts (reviewed, reached_out, connected) in compute_data_quality() dict
affects:
  - 03-02-PLAN, 03-03-PLAN (depend on funnel data in dashboard snapshot)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "_make_mock_get_session() context-manager factory for isolating dashboard_service DB calls"
    - "side_effect list on mock .one() to handle sequential exec() calls in one session block"

key-files:
  created:
    - tests/test_phase3_pwa.py
  modified:
    - src/services/dashboard_service.py

key-decisions:
  - "Mock get_session as a contextmanager factory (not a bare mock) so the 'with get_session()' syntax works in dashboard_service"
  - "side_effect list on exec().one() handles all sequential queries within a single session block"
  - "test_netlify_toml failure is pre-existing (before this plan) — out of scope, deferred"

patterns-established:
  - "_make_mock_session(return_values) + _make_mock_get_session(return_values): standard pattern for mocking dashboard_service DB calls"

requirements-completed: [VIEW-01, VIEW-02]

# Metrics
duration: 2min
completed: 2026-03-09
---

# Phase 3 Plan 01: PWA Test Scaffold and Funnel Counts Summary

**Phase 3 Wave 0 test scaffold (7 tests covering all 4 PROFILE and 3 VIEW requirements) plus TDD implementation of reviewed/reached_out/connected funnel counts in compute_data_quality()**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-09T03:37:29Z
- **Completed:** 2026-03-09T03:39:58Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Created Phase 3 Nyquist test scaffold with 7 test functions (Wave 0 satisfied)
- TDD: wrote failing test_funnel_counts_in_snapshot (RED), then implemented funnel counts (GREEN)
- `compute_data_quality()` now returns `reviewed`, `reached_out`, and `connected` alongside existing metrics
- Tests 2-7 pass immediately against existing data shapes — confirmed PWA data contract is already correct

## Task Commits

Each task was committed atomically:

1. **Task 1: Create Phase 3 test scaffold** - `f5d27aa` (test)
2. **Task 2: Add funnel stage counts to compute_data_quality()** - `611ba04` (feat)

**Plan metadata:** (docs commit follows)

_Note: Task 2 used TDD — test was committed RED in Task 1, implementation committed GREEN in Task 2._

## Files Created/Modified
- `tests/test_phase3_pwa.py` - 7 test functions for Phase 3 requirements (VIEW-01/02/03, PROFILE-01/02/03/04)
- `src/services/dashboard_service.py` - Added reviewed, reached_out, connected queries and return values to compute_data_quality()

## Decisions Made
- Used a contextmanager factory for `_make_mock_get_session()` so the `with get_session() as session:` pattern in `dashboard_service.py` works correctly in tests
- `side_effect` list on `exec().one()` mock handles all 8 sequential queries (5 existing + 3 new funnel) within one `with` block

## Deviations from Plan

None - plan executed exactly as written.

Note: `test_netlify_toml` in `test_phase1_infra.py` was failing before this plan (pre-existing, out of scope). No new regressions introduced by this plan's changes.

## Issues Encountered
- Pre-existing `test_netlify_toml` failure (netlify.toml has an echo build command rather than no command). Out of scope — not caused by Phase 3 work.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Wave 0 test scaffold complete — all subsequent Phase 3 plans have their Nyquist verification baseline
- `compute_data_quality()` now provides funnel data for Plan 03-03 (PWA dashboard funnel view)
- No blockers for Phase 3 Plans 02-05

---
*Phase: 03-pwa-feature-completeness*
*Completed: 2026-03-09*
