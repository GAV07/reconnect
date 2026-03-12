---
phase: 09-goals-sync-and-pipeline-intelligence
plan: 02
subsystem: pipeline
tags: [cadence, re-queuing, queue-generation, tdd]
dependency_graph:
  requires: [src/pipeline/queue_generator.py, src/database/models.py, src/services/signal_service.py]
  provides: [_get_cadence_expired_candidates, cadence re-queuing in generate_daily_queue]
  affects: [daily outreach queue composition, contacts with expired cadence_due_at]
tech_stack:
  added: [sqlalchemy or_() for NULL-safe user_priority filter]
  patterns: [TDD red-green, SQLModel in-memory testing with create_engine sqlite:///memory]
key_files:
  created:
    - tests/test_phase9_cadence.py
  modified:
    - src/pipeline/queue_generator.py
    - src/pipeline/daily_pipeline.py
decisions:
  - "NULL user_priority: use or_(is_(None), != 'never') — SQL != excludes NULLs, so contacts without priority set were incorrectly excluded"
  - "Cadence candidates injected before fresh scored contacts but after always-priority (belt-and-suspenders exclusion via is_contact_excluded)"
metrics:
  duration: "3 minutes"
  completed: "2026-03-12"
  tasks_completed: 2
  files_modified: 3
---

# Phase 9 Plan 02: Cadence Re-queuing Summary

**One-liner:** Automatic cadence re-queuing via `_get_cadence_expired_candidates()` integrated into `generate_daily_queue()` with 50% volume cap and NULL-safe ARCHIVE exclusion.

## What Was Built

Contacts whose cadence timer has expired (cadence_due_at <= now) now automatically re-enter the daily outreach queue without manual intervention. ARCHIVE contacts (user_priority='never') never reappear. Volume is capped at limit // 2 to prevent stale contacts from crowding out fresh high-scorers.

### Key Implementation Details

**`_get_cadence_expired_candidates(session, limit)` in `src/pipeline/queue_generator.py`:**
- Queries `Connection` where `cadence_due_at <= now` AND `cadence_due_at IS NOT NULL`
- Excludes ARCHIVE contacts using `or_(user_priority IS NULL, user_priority != 'never')`
- Only includes contacts with a scored `reconnect_score` (not NULL)
- Orders by `reconnect_score DESC`, limit applied at query level

**`generate_daily_queue()` modifications:**
- Added `cadence_added: 0` to stats dict
- Cadence candidates fetched after `always_contacts`, before main scored query
- Merge order: always -> cadence re-queues -> fresh scored (deduplication via id sets)
- Cadence candidates pass through existing `is_contact_excluded()` checks (belt-and-suspenders)
- Tracking: `cadence_added` incremented when a cadence candidate is added to queue

**`src/pipeline/daily_pipeline.py`:**
- Added 7-line comment before Step 6 documenting that cadence re-queuing is integrated inside `generate_daily_queue()` and explaining the one-day goals delay behavior

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 (RED) | Failing cadence tests | 3d319c4 | tests/test_phase9_cadence.py |
| 1 (GREEN) | Cadence re-queuing implementation | 3710ea7 | src/pipeline/queue_generator.py |
| 2 | Pipeline wiring comment | 7baa583 | src/pipeline/daily_pipeline.py |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] NULL user_priority excluded by SQL != filter**
- **Found during:** Task 1, TDD GREEN phase (tests failed after initial implementation)
- **Issue:** `Connection.user_priority != "never"` in SQLAlchemy/SQLite excludes rows where `user_priority IS NULL` — this is standard SQL three-value logic. Contacts with no priority set (the majority) were silently excluded from cadence re-queuing.
- **Fix:** Changed filter to `or_(Connection.user_priority.is_(None), Connection.user_priority != "never")` and added `from sqlalchemy import or_` import
- **Files modified:** `src/pipeline/queue_generator.py`
- **Commit:** 3710ea7 (included in GREEN commit)

## Success Criteria Verification

- [x] Contacts with cadence_due_at <= now appear in daily queue
- [x] ARCHIVE contacts (user_priority='never') never re-enter
- [x] Cadence candidates capped at limit // 2 to prevent crowding out fresh candidates
- [x] Re-queuing uses stored cadence_due_at, not re-derived from signals
- [x] cadence_added count tracked in queue generation stats
- [x] All 8 tests pass

## Self-Check: PASSED

Files verified:
- FOUND: src/pipeline/queue_generator.py (contains _get_cadence_expired_candidates, cadence_added)
- FOUND: tests/test_phase9_cadence.py (8 tests, all passing)
- FOUND: src/pipeline/daily_pipeline.py (contains "cadence re-queuing" comment)

Commits verified:
- 3d319c4: test(09-02) RED — failing tests
- 3710ea7: feat(09-02) GREEN — implementation
- 7baa583: chore(09-02) — documentation comment
