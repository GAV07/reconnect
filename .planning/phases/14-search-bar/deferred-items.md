# Deferred Items — Phase 14 Search Bar

## Out-of-Scope Issues Discovered During Execution

### Pre-existing test failure: test_gmail_not_configured_without_password

- **Found during:** Task 1 full test suite run
- **File:** tests/test_phase1_infra.py::test_gmail_not_configured_without_password
- **Issue:** `is_gmail_configured()` returns True when `GMAIL_APP_PASSWORD` env var is missing. This test has been failing since before Phase 14 (confirmed by git stash verification — fails on main before any Phase 14 changes).
- **Scope:** Phase 1 infrastructure — not caused by Phase 14 changes, not relevant to search bar.
- **Action required:** Fix `src/integrations/gmail.py` `is_gmail_configured()` to correctly check for `GMAIL_APP_PASSWORD` env var. Defer to a future phase or hotfix.
