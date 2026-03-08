---
phase: 01-infrastructure-foundations
plan: "01"
subsystem: infra
tags: [gmail, smtplib, pytest, config, email]

# Dependency graph
requires: []
provides:
  - smtplib-based Gmail sending via App Password (no OAuth)
  - Settings fields: pwa_url, gmail_app_password, gmail_sender_email
  - Test scaffold for all Phase 1 requirements (tests/test_phase1_infra.py)
  - Cleaned dependencies (google-api-python-client, google-auth-oauthlib, apify-client removed)
affects:
  - 01-02 (netlify/PWA deploy -- uses pwa_url, test stubs)
  - 01-03 (action edge function -- email sending via gmail.py)
  - 01-04 (email digest -- imports is_gmail_configured, get_user_email, send_html_email)

# Tech tracking
tech-stack:
  added: [pytest, pytest-mock, pytest-cov, smtplib (stdlib)]
  patterns: [get_settings() called at runtime (not module-level singleton) for testability, TDD RED-GREEN per task]

key-files:
  created:
    - tests/__init__.py
    - tests/conftest.py
    - tests/test_phase1_infra.py
  modified:
    - src/config.py
    - src/integrations/gmail.py
    - requirements.txt
    - pyproject.toml

key-decisions:
  - "Use get_settings() at call time (not module-level settings singleton) in gmail.py so monkeypatching works in tests"
  - "Gmail App Password via smtplib replaces entire OAuth flow -- 330 lines replaced with 60"
  - "pytest-mock added to dev deps; pytest installed in venv (was missing)"

patterns-established:
  - "Integration modules: call get_settings() inside functions, not at import time, for test isolation"
  - "conftest.py: mock_settings fixture clears lru_cache before AND after each test"

requirements-completed: [EMAIL-01, DEPLOY-03]

# Metrics
duration: 3min
completed: 2026-03-08
---

# Phase 1 Plan 01: Gmail smtplib + Config + Test Scaffold Summary

**smtplib App Password email sending replaces unconfigured OAuth flow; pwa_url config field added; pytest scaffold with passing gmail/config tests established**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-08T23:11:41Z
- **Completed:** 2026-03-08T23:14:14Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments
- Replaced 330-line OAuth gmail.py with 60-line smtplib implementation preserving all function signatures
- Added pwa_url, gmail_app_password, gmail_sender_email to Settings; removed OAuth fields
- Created test scaffold (tests/__init__.py, conftest.py, test_phase1_infra.py) with 7 tests total
- Removed google-api-python-client, google-auth-oauthlib, apify-client from all dependency files
- 5 gmail/config tests pass GREEN; 2 infra stubs (netlify/service-worker) intentionally RED until Plan 02

## Task Commits

Each task was committed atomically:

1. **Task 1: Test scaffold + config.py changes** - `9ba82dc` (feat)
2. **Task 2: Gmail smtplib rewrite + package cleanup** - `091829e` (feat)

**Plan metadata:** (docs commit follows)

_Note: TDD tasks committed RED state with Task 1; GREEN achieved within Task 2 commit._

## Files Created/Modified
- `tests/__init__.py` - Empty test package marker
- `tests/conftest.py` - mock_settings fixture with lru_cache clearing
- `tests/test_phase1_infra.py` - 7 tests covering config, gmail, netlify (stub), service-worker (stub)
- `src/config.py` - Added pwa_url, gmail_app_password, gmail_sender_email; removed OAuth fields
- `src/integrations/gmail.py` - Full smtplib rewrite (330 lines -> 60 lines)
- `requirements.txt` - Removed google-api-python-client, google-auth-oauthlib
- `pyproject.toml` - Removed apify-client, google-* packages; added pytest-mock to dev deps

## Decisions Made
- Used `get_settings()` at call time (not module-level singleton) in gmail.py so monkeypatching works in tests — the module-level `settings = get_settings()` pattern freezes the cache at import time, defeating monkeypatch
- Installed pytest, pytest-mock, pytest-cov into venv (were not installed, pyproject.toml listed them as dev deps but pip install hadn't been run)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] gmail.py used module-level `settings` singleton breaking test isolation**
- **Found during:** Task 2 (Gmail smtplib rewrite)
- **Issue:** `from src.config import settings` imports the lru_cache result at module load time. Even after `get_settings.cache_clear()`, the `settings` name in gmail.py still pointed to the old instance, so `is_gmail_configured()` always saw empty strings.
- **Fix:** Changed `from src.config import settings` to `from src.config import get_settings` and call `get_settings()` inside each function so the cache is consulted fresh after the fixture clears it.
- **Files modified:** src/integrations/gmail.py
- **Verification:** `test_gmail_is_configured` and all 5 gmail/config tests pass GREEN
- **Committed in:** 091829e (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - Bug)
**Impact on plan:** Required for test correctness. No scope creep. Production behavior unchanged — get_settings() returns same cached instance in normal operation.

## Issues Encountered
- pytest not installed in venv despite being in pyproject.toml dev deps — installed pytest, pytest-mock, pytest-cov via pip during Task 1.

## User Setup Required

**External services require manual configuration before email sending works:**

- `GMAIL_SENDER_EMAIL` — Your Gmail address
- `GMAIL_APP_PASSWORD` — Generate at: Google Account > Security > 2-Step Verification > App passwords (16 chars, spaces OK)

Prerequisites: 2-Step Verification must be enabled on the Google Account first.

## Next Phase Readiness
- Test scaffold ready for Plan 02 (netlify/service-worker stubs will turn green after Plan 02 executes)
- gmail.py function signatures preserved — email_digest.py imports work without changes
- Config fields ready for all subsequent plans that reference pwa_url or Gmail settings

---
*Phase: 01-infrastructure-foundations*
*Completed: 2026-03-08*
