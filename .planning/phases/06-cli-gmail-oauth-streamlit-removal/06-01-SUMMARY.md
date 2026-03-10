---
phase: 06-cli-gmail-oauth-streamlit-removal
plan: "01"
subsystem: cli
tags: [click, cli, console_scripts, queue, pipeline, gmail, sync]

# Dependency graph
requires:
  - phase: 04-foundation-fixes-queue-ux
    provides: queue_generator.py with get_queue_stats(), daily_pipeline.py with run_daily_pipeline()
  - phase: 04-foundation-fixes-queue-ux
    provides: gmail.py with authorize_gmail_oauth(), is_oauth_configured()
  - phase: 05-dashboard-intelligence
    provides: scoring.py with rescore_missing_dimensions()
provides:
  - reconnect CLI binary at .venv/bin/reconnect (console_scripts entry point)
  - reset_queue() function in queue_generator.py
  - src/cli.py with all 5 Click command groups and 9 commands
  - click>=8.0.0 added to dependencies
  - streamlit and plotly removed from dependencies
affects: [06-02-streamlit-removal, launchagent-update]

# Tech tracking
tech-stack:
  added: [click>=8.0.0 (explicit dependency, was already transitively installed)]
  patterns:
    - Click nested groups with lazy imports inside commands for fast CLI startup
    - CliRunner + unittest.mock.patch for CLI unit tests (patches applied inside test body)
    - console_scripts entry point via [project.scripts] in pyproject.toml

key-files:
  created:
    - src/cli.py
    - tests/test_phase6_cli.py
  modified:
    - src/pipeline/queue_generator.py
    - pyproject.toml
    - requirements.txt

key-decisions:
  - "reset_queue() added to queue_generator.py (not inline in CLI) for testability and module cohesion"
  - "Lazy imports inside each Click command body keep CLI startup fast (no heavy pipeline imports at module load)"
  - "import json as _json inside queue_stats() avoids name collision with --json Click option alias"
  - "Exit 0 even when pipeline steps have errors — matches existing run_pipeline.py behavior; only exit 1 on init_db failure"

patterns-established:
  - "Click lazy import pattern: business logic imported inside command body, not at module top"
  - "CliRunner mock ordering: patch() context manager wraps runner.invoke() call inside test body (not as decorator)"
  - "CLI binary at .venv/bin/reconnect — always use absolute path for LaunchAgent ProgramArguments"

requirements-completed: [CLI-01]

# Metrics
duration: 3min
completed: 2026-03-10
---

# Phase 6 Plan 01: CLI Implementation Summary

**Click-based `reconnect` CLI binary with 5 command groups (pipeline/queue/contacts/gmail/sync) and `reset_queue()` function, registered as a console_scripts entry point, replacing all scripts/ functionality**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-10T00:08:55Z
- **Completed:** 2026-03-10T00:11:35Z
- **Tasks:** 1 (TDD: RED + GREEN)
- **Files modified:** 5

## Accomplishments
- Created `src/cli.py` with all 5 Click command groups and 9 commands, wired to existing business logic
- Added `reset_queue()` to `queue_generator.py` — extracts queue reset from Streamlit UI into a testable pipeline module function
- Registered `reconnect = "src.cli:main"` as console_scripts entry point; binary available at `.venv/bin/reconnect`
- Removed streamlit and plotly from `pyproject.toml` and `requirements.txt`; added `click>=8.0.0`
- 14 CliRunner tests pass covering all CLI commands and the `reset_queue()` unit behavior

## Task Commits

Each task was committed atomically:

1. **RED — Failing tests** - `54241d0` (test)
2. **GREEN — Implementation** - `1889422` (feat)

_Note: TDD task with RED and GREEN commits._

## Files Created/Modified
- `src/cli.py` - Click CLI with 5 groups: pipeline run, queue stats/reset, contacts import/score, gmail auth/status, sync push/pull
- `src/pipeline/queue_generator.py` - Added `reset_queue()` function before `expire_stale_queue_items()`
- `pyproject.toml` - Added `[project.scripts]` entry, added click>=8.0.0, removed streamlit and plotly
- `requirements.txt` - Added click>=8.0.0, removed streamlit and plotly
- `tests/test_phase6_cli.py` - 14 CliRunner tests for all commands and reset_queue() unit test

## Decisions Made
- `reset_queue()` extracted to `queue_generator.py` rather than implemented inline in CLI — keeps business logic in the correct module, enables independent unit testing
- Lazy imports inside each Click command body (not at module top) — keeps CLI startup fast; avoids importing heavy pipeline dependencies just to show `--help`
- `import json as _json` inside `queue_stats()` — avoids name collision with Click option alias `as_json` (research Pitfall noted this explicitly)
- Exit code 0 even when individual pipeline steps fail — matches existing `scripts/run_pipeline.py` behavior; only `sys.exit(1)` if `init_db()` raises

## Deviations from Plan

None - plan executed exactly as written. The Research.md reference implementation was followed closely.

## Issues Encountered
None.

## User Setup Required
None — no external service configuration required. The `reconnect` binary is available at `.venv/bin/reconnect`. Users should activate the venv or use the absolute path.

## Next Phase Readiness
- `reconnect` CLI binary fully operational
- CLI-01 requirement satisfied
- Ready for Phase 6 Plan 02: Streamlit cleanup (delete src/ui/, remove config.py get_streamlit_secrets(), update LaunchAgent plist)
- The `reset_queue()` function is now in the right module for the CLI to call cleanly

---
*Phase: 06-cli-gmail-oauth-streamlit-removal*
*Completed: 2026-03-10*
