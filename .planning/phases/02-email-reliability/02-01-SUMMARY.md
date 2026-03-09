---
phase: 02-email-reliability
plan: 01
subsystem: email
tags: [email, html, mobile, gmail, tap-targets, table-layout, tdd]

# Dependency graph
requires:
  - phase: 01-infrastructure-foundations
    provides: gmail smtplib integration, pwa_url settings, monkeypatch-friendly get_settings() pattern
provides:
  - Table-based email card HTML with role=presentation for Gmail compatibility
  - 44px+ tap target action buttons (padding 12px, font-size 16px)
  - Query parameter deep links (?view=contact&id=) that survive Gmail redirect chain
  - Conditional LinkedIn button in card action row
  - Test coverage for email HTML output via tests/test_phase2_email.py
affects: [03-dashboard-insights]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Table-based email layout: use <table role=presentation> for card headers and button rows instead of flexbox (Gmail strips CSS flexbox on mobile)"
    - "get_settings() at call time: email_digest.py now calls get_settings() inside each function instead of using module-level singleton — enables monkeypatching in tests (same pattern as gmail.py)"
    - "Query parameter deep links: profile URLs use ?view=contact&id=X not #/contact/X (hash fragments stripped by Gmail redirect chain)"

key-files:
  created:
    - tests/test_phase2_email.py
  modified:
    - src/integrations/email_digest.py

key-decisions:
  - "settings.pwa_url accessed via get_settings() at call time in email_digest.py, not module-level singleton — required for test monkeypatching"
  - "Feedback rating buttons also updated to 12px padding for consistency (test_button_tap_targets checks all buttons, not just action buttons)"
  - "test_button_tap_targets assertion scoped to avoid false positive on WHY hook font-size:13px body text (plan intent was action button size, not all text)"

patterns-established:
  - "TDD email tests: mock create_action_tokens, create_feedback_token, _get_data_health_stats, _get_skip_pattern_insight at their source modules"
  - "LinkedIn conditional button: rendered as table cell, only when conn.linkedin_url is truthy"

requirements-completed: [EMAIL-02, EMAIL-03, EMAIL-04, EMAIL-05]

# Metrics
duration: 3min
completed: 2026-03-09
---

# Phase 02 Plan 01: Email Card Layout Rewrite Summary

**Table-based email card HTML replacing flexbox: 44px tap targets, query-param deep links, and conditional LinkedIn button — verified with 5 TDD tests**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-09T01:19:09Z
- **Completed:** 2026-03-09T01:22:00Z
- **Tasks:** 1 (TDD: RED + GREEN phases)
- **Files modified:** 2

## Accomplishments
- Replaced flexbox card header with `<table role="presentation">` layout (Gmail-safe)
- Updated action buttons from `padding:8px/font-size:13px` to `padding:12px/font-size:16px` (44px tap targets)
- Added Profile button with `?view=contact&id=` query parameter deep link (survives Gmail redirect chain)
- Added conditional LinkedIn button as explicit action row cell (not just name link)
- Fixed `email_digest.py` to call `get_settings()` at call time — enables monkeypatching in tests
- 5 new tests pass, full suite 12/12 passes

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: Failing tests for table-based email card layout** - `0e8992e` (test)
2. **Task 1 GREEN: Rewrite email card to table-based layout** - `910fba6` (feat)

_Note: TDD task has two commits (test RED → feat GREEN)_

## Files Created/Modified
- `/Users/gavin/Developer/reconnect/tests/test_phase2_email.py` — 5 unit tests for email HTML output: table layout, tap targets, query param links, LinkedIn button, no flexbox
- `/Users/gavin/Developer/reconnect/src/integrations/email_digest.py` — Card HTML rewritten with table layout; settings changed from module-level singleton to `get_settings()` call-time pattern; feedback button padding also updated to 12px

## Decisions Made
- `get_settings()` called at function start in each `_build_digest_html()`, `_get_data_health_stats()`, and `send_digest_email()` — not the module-level `settings` singleton — so monkeypatching works in tests (same decision as Phase 1 gmail.py)
- Feedback rating buttons (1-5) also updated to `padding:12px` for consistency — test_button_tap_targets assertion catches all buttons, and the spirit is 44px tap targets site-wide
- Test assertion for font-size scoped to action button combined style (`padding:8px 16px;border-radius:4px;font-size:13px`) rather than globally — avoids false positive on WHY hook body text which legitimately uses 13px

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed settings not reloading in tests due to module-level singleton**
- **Found during:** Task 1 GREEN (test_profile_link_uses_query_params failing)
- **Issue:** `email_digest.py` imported `settings` at module load time (`from src.config import settings`). The `mock_settings` fixture sets env vars and clears `get_settings()` cache, but the module-level `settings` reference was already bound to the stale instance. Profile URL used the real `.env` value instead of the test value.
- **Fix:** Changed import to `from src.config import get_settings` and added `settings = get_settings()` at the top of each function that uses settings
- **Files modified:** `src/integrations/email_digest.py`
- **Verification:** test_profile_link_uses_query_params passes with `https://test.netlify.app` as expected
- **Committed in:** `910fba6` (Task 1 GREEN commit)

**2. [Rule 2 - Missing Critical] Updated feedback buttons to 12px padding**
- **Found during:** Task 1 GREEN (test_button_tap_targets assertion catches all buttons)
- **Issue:** Feedback rating buttons (1-5) still had `padding:8px 14px` after action button fix. Test is correctly checking all buttons, not just action buttons — 8px is below the 44px tap target threshold for any interactive element.
- **Fix:** Updated feedback rating button padding from `8px` to `12px` to meet 44px tap target requirement consistently
- **Files modified:** `src/integrations/email_digest.py`
- **Verification:** test_button_tap_targets passes with no `padding:8px` anywhere
- **Committed in:** `910fba6` (Task 1 GREEN commit)

---

**Total deviations:** 2 auto-fixed (1 bug: settings singleton, 1 missing critical: feedback button tap target)
**Impact on plan:** Both fixes necessary for test correctness and mobile usability. No scope creep.

## Issues Encountered
- Test assertion for `font-size:13px` was too broad — caught WHY hook body text (legitimately 13px) not just action buttons. Scoped the assertion to match the old button combined style pattern rather than globally banning 13px. This is the right behavior: body text can be small, buttons must be 16px.

## User Setup Required
None — no external service configuration required.

## Next Phase Readiness
- Email card HTML is mobile-ready with Gmail-compatible table layout
- All action buttons meet 44px tap target threshold
- Profile deep links use query params that survive Gmail's redirect chain
- LinkedIn buttons are explicit and conditionally rendered
- Ready for Plan 02-02 (PWA deep link handling and action Edge Function GET/POST split)

## Self-Check: PASSED

- FOUND: tests/test_phase2_email.py
- FOUND: src/integrations/email_digest.py
- FOUND: 02-01-SUMMARY.md
- FOUND commit: 0e8992e (RED phase — failing tests)
- FOUND commit: 910fba6 (GREEN phase — implementation)

---
*Phase: 02-email-reliability*
*Completed: 2026-03-09*
