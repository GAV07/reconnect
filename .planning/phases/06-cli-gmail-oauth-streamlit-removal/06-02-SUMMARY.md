---
phase: 06-cli-gmail-oauth-streamlit-removal
plan: 02
subsystem: ui
tags: [streamlit, plotly, cleanup, launchagent, cli, testing]

# Dependency graph
requires:
  - phase: 06-01
    provides: reconnect CLI binary (.venv/bin/reconnect) that LaunchAgent now calls directly
provides:
  - src/ui/ directory deleted (Streamlit app removed)
  - scripts/ directory deleted (old shell script runners removed)
  - src/config.py cleaned (no get_streamlit_secrets, no streamlit reference)
  - LaunchAgent updated to call CLI binary directly
  - Static cleanup verification tests (5 new tests)
affects: [future-phases]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Static verification tests use subprocess.run + grep with returncode assertions to verify file system state"
    - "LaunchAgent ProgramArguments uses three separate <string> entries for binary + subcommand + verb"

key-files:
  created:
    - tests/test_phase6_cli.py (5 new tests appended)
  modified:
    - src/config.py
    - src/database/engine.py
    - src/services/dashboard_service.py
    - "~/Library/LaunchAgents/com.reconnect.daily-pipeline.plist (outside repo)"

key-decisions:
  - "Stale .pyc cache files from deleted src/ui/ matched grep for streamlit — cleaned all __pycache__ files as Rule 3 auto-fix"
  - "LaunchAgent plist is outside the git repo (~/Library/LaunchAgents/) — committed only in-repo changes; plist tracked by launchctl reload"

patterns-established:
  - "Static tests as regression guards: after deleting code, add assertions that verify the deletion persists"

requirements-completed: [CLI-02]

# Metrics
duration: 5min
completed: 2026-03-10
---

# Phase 6 Plan 02: Streamlit Removal and LaunchAgent Update Summary

**Deleted Streamlit UI (src/ui/), scripts/ directory, and all streamlit/plotly references; updated LaunchAgent to call .venv/bin/reconnect pipeline run directly**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-10T00:13:59Z
- **Completed:** 2026-03-10T00:19:00Z
- **Tasks:** 2
- **Files modified:** 4 modified, 17 deleted

## Accomplishments
- Deleted all 17 files in src/ui/ (Streamlit dashboard app and components)
- Deleted all 6 files in scripts/ (run_scheduled.sh, run_pipeline.py, init_db.py, etc.)
- Removed get_streamlit_secrets() function and 'from typing import Any' import from src/config.py
- Updated LaunchAgent plist to call /Users/gavin/Developer/reconnect/.venv/bin/reconnect pipeline run directly
- Added 5 static verification tests; full suite: 55 passed, 3 skipped

## Task Commits

Each task was committed atomically:

1. **Task 1: Delete src/ui/ and scripts/, clean streamlit refs, update LaunchAgent** - `9004237` (feat)
2. **Task 2: Add static cleanup verification tests** - `99ec88a` (test)

**Plan metadata:** (see final commit below)

## Files Created/Modified
- `src/config.py` - Removed get_streamlit_secrets() function, removed `from typing import Any`, updated module docstring
- `src/database/engine.py` - Updated check_same_thread comment from "Required for Streamlit" to "Allow multi-thread access"
- `src/services/dashboard_service.py` - Updated module docstring from "shared by pipeline and Streamlit" to "shared by pipeline and PWA"
- `~/Library/LaunchAgents/com.reconnect.daily-pipeline.plist` - ProgramArguments now calls .venv/bin/reconnect + pipeline + run
- `tests/test_phase6_cli.py` - Added 5 static cleanup verification tests + import subprocess

**Deleted:**
- `src/ui/` (17 files: app.py, __init__.py, components/*, views/*)
- `scripts/` (6 files: run_scheduled.sh, run_pipeline.py, init_db.py, run_sync.py, import_csv.py, scheduler.sh)

## Decisions Made
- Stale .pyc cache files from deleted src/ui/ matched grep for "streamlit" — cleaned all __pycache__ files as part of cleanup (Rule 3 auto-fix; blocking verification)
- LaunchAgent plist lives outside the git repo (~/Library/LaunchAgents/) — tracked by launchctl, not committed to git

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Removed stale .pyc cache files matching streamlit grep**
- **Found during:** Task 1 (verification step)
- **Issue:** `grep -r "streamlit" src/` matched binary `.pyc` files in `src/__pycache__/` and `src/reconnect/ui/components/__pycache__/` that were left over from before src/ui/ was deleted. These are compiled bytecode containing string literals from the original imports.
- **Fix:** Ran `find src -name "*.pyc" -delete && find src -name "__pycache__" -type d -empty -delete`
- **Files modified:** All stale .pyc files in src/
- **Verification:** Re-ran grep; returned exit 1 (no matches). Verification passed.
- **Committed in:** 9004237 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Auto-fix necessary for correct verification. No scope creep.

## Issues Encountered
- None beyond the .pyc cache deviation documented above.

## User Setup Required
None - LaunchAgent was reloaded via `launchctl unload` + `launchctl load` during execution. No manual steps needed.

## Next Phase Readiness
- Phase 6 complete: CLI built (Plan 01), Streamlit/scripts removed (Plan 02)
- Zero streamlit/plotly references remain in src/
- All 55 tests pass (3 skipped as expected)
- CLI binary at .venv/bin/reconnect is the sole entry point for automation

---
*Phase: 06-cli-gmail-oauth-streamlit-removal*
*Completed: 2026-03-10*
