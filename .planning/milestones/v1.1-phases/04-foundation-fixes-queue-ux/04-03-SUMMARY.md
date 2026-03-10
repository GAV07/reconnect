---
phase: 04-foundation-fixes-queue-ux
plan: 03
subsystem: infra
tags: [gmail, oauth, google-auth, email-digest, security]

# Dependency graph
requires:
  - phase: 04-01
    provides: GmailCredentials model in database, test stubs with @pytest.mark.skip for INFRA-01
provides:
  - Gmail OAuth send path via GCP JSON credentials (InstalledAppFlow)
  - is_oauth_configured() / oauth_send_html_email() / authorize_gmail_oauth() in gmail.py
  - GmailCredentials removed from cloud sync (push.py) for security
  - OAuth-first email send with App Password fallback in daily_pipeline.py and email_digest.py
  - Google auth packages in requirements.txt and pyproject.toml
affects: [daily-pipeline, email-digest, sync-push, gmail-integration]

# Tech tracking
tech-stack:
  added:
    - google-api-python-client==2.192.0
    - google-auth-oauthlib==1.3.0
    - google-auth==2.49.0
  patterns:
    - OAuth credentials stored locally in GmailCredentials table, never synced to cloud
    - get_session imported at module level in gmail.py for testability (patchable in tests)
    - OAuth-first with App Password fallback pattern in send_digest_email()

key-files:
  created: []
  modified:
    - src/integrations/gmail.py
    - src/integrations/email_digest.py
    - src/sync/push.py
    - src/pipeline/daily_pipeline.py
    - requirements.txt
    - pyproject.toml
    - tests/test_phase4_foundation.py

key-decisions:
  - "get_session imported at module level in gmail.py so tests can patch src.integrations.gmail.get_session directly"
  - "OAuth tokens stored in local GmailCredentials table only — never synced to Supabase (security boundary)"
  - "OAuth-first fallback pattern: is_oauth_configured() checked before is_gmail_configured() in pipeline"

patterns-established:
  - "OAuth credentials: always local-only, module-level import for patchability"
  - "Dual-path send: OAuth takes precedence, App Password is graceful degradation"

requirements-completed: [INFRA-01]

# Metrics
duration: 1min
completed: 2026-03-09
---

# Phase 4 Plan 03: Gmail OAuth Send Path Summary

**Gmail OAuth send via GCP InstalledAppFlow with token storage in local GmailCredentials table, App Password fallback, and OAuth tokens removed from Supabase cloud sync**

## Performance

- **Duration:** ~1 min
- **Started:** 2026-03-09T19:20:14Z
- **Completed:** 2026-03-09T19:21:00Z
- **Tasks:** 2 of 2 completed
- **Files modified:** 7

## Accomplishments
- Added `authorize_gmail_oauth()`, `is_oauth_configured()`, `oauth_send_html_email()` to `gmail.py`
- Removed `GmailCredentials` from `push.py` imports and stats dict (security fix)
- Updated `daily_pipeline.py` to check `is_oauth_configured()` first, fall back to App Password
- Updated `email_digest.py` to use OAuth send when available, App Password as fallback
- Added Google auth packages to `requirements.txt` and `pyproject.toml`
- Implemented and passed all 3 INFRA-01 TDD tests (previously `@pytest.mark.skip` stubs)

## Task Commits

Each task was committed atomically:

1. **Task 1: Add Gmail OAuth functions and update pipeline send logic** - `174a46c` (feat)
2. **Task 2: Authorize Gmail OAuth (one-time GCP setup)** - human action (no code commit — OAuth tokens saved to local DB)

**Plan metadata:** `a45eaa3` (docs: complete Gmail OAuth plan)

## Files Created/Modified
- `src/integrations/gmail.py` - Added GMAIL_SCOPES, _save_oauth_credentials(), _load_oauth_credentials(), authorize_gmail_oauth(), is_oauth_configured(), oauth_send_html_email(); imported get_session at module level
- `src/integrations/email_digest.py` - OAuth-first send with App Password fallback in send_digest_email()
- `src/sync/push.py` - Removed GmailCredentials from imports and stats dict; replaced section 5 with comment
- `src/pipeline/daily_pipeline.py` - OAuth-first email_configured check before sending digest
- `requirements.txt` - Added google-api-python-client, google-auth-oauthlib, google-auth
- `pyproject.toml` - Added same Google auth packages to project dependencies
- `tests/test_phase4_foundation.py` - Implemented test_oauth_not_configured, test_oauth_send_email_mock, test_no_gmail_creds_in_push

## Decisions Made
- `get_session` imported at module level in `gmail.py` so tests can patch `src.integrations.gmail.get_session` directly (instead of the deep import path)
- OAuth tokens stored in local `GmailCredentials` table only — never synced to Supabase (security boundary enforced in push.py)
- OAuth-first fallback: `is_oauth_configured()` checked before `is_gmail_configured()` in both pipeline and email_digest

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Module-level get_session import for testability**
- **Found during:** Task 1 (GREEN phase — tests failing after implementation)
- **Issue:** `_load_oauth_credentials()` imported `get_session` locally, making it unpatchable at `src.integrations.gmail.get_session`. Tests got `AttributeError: module 'src.integrations.gmail' does not have attribute 'get_session'`
- **Fix:** Added `from src.database.engine import get_session` at module level; removed redundant local imports in `_save_oauth_credentials` and `_load_oauth_credentials`
- **Files modified:** src/integrations/gmail.py
- **Verification:** Tests patching `src.integrations.gmail.get_session` pass correctly
- **Committed in:** 174a46c (Task 1 commit)

**2. [Rule 1 - Bug] Test assertion too broad for GmailCredentials comment**
- **Found during:** Task 1 (GREEN phase — test_no_gmail_creds_in_push failing)
- **Issue:** Test asserted `"GmailCredentials" not in push_source` but the replacement comment `# 5. GmailCredentials removed...` contained the string
- **Fix:** Refined test to check only import lines and non-comment active lines
- **Files modified:** tests/test_phase4_foundation.py
- **Verification:** All 3 INFRA-01 tests pass
- **Committed in:** 174a46c (Task 1 commit)

---

**Total deviations:** 2 auto-fixed (1 missing critical, 1 bug)
**Impact on plan:** Both fixes necessary for test correctness and code testability. No scope creep.

## Issues Encountered
- `pytest` not installed in the system Python; installed `pytest` and `pytest-mock` (these were already in `pyproject.toml` dev dependencies but not yet installed in the active Python environment)

## User Setup Required

Completed. The user:
1. Created a Desktop app OAuth client in GCP and added erickgavin7@gmail.com as a test user
2. Downloaded credentials.json and ran `authorize_gmail_oauth('credentials.json')` — browser OAuth flow completed
3. Verified: `is_oauth_configured()` returns True

OAuth tokens are stored in the local `GmailCredentials` table. The daily pipeline will now use OAuth send on first run.

## Next Phase Readiness
- Gmail OAuth authorized and working — `is_oauth_configured()` returns True
- App Password fallback preserved — pipeline degrades gracefully if OAuth expires
- GmailCredentials no longer synced to Supabase (security fix live)
- Phase 4 fully complete: INFRA-02 (score breakdown), QUEUE-01/02/03 (sort/filter), INFRA-01 (Gmail OAuth) all resolved
- Ready for Phase 5: Dashboard Intelligence

---
*Phase: 04-foundation-fixes-queue-ux*
*Completed: 2026-03-09*

## Self-Check: PASSED
- FOUND: src/integrations/gmail.py
- FOUND: src/sync/push.py
- FOUND: src/pipeline/daily_pipeline.py
- FOUND: 04-03-SUMMARY.md
- FOUND: 174a46c commit
