---
phase: 07-signal-foundation
plan: 01
subsystem: database
tags: [sqlmodel, sqlite, postgresql, signals, migration, python]

# Dependency graph
requires: []
provides:
  - ContactSignal SQLModel (contact_signals table) with UUID pk, signal, signal_context, assigned_at, assigned_by
  - ContactNote SQLModel (contact_notes table) with UUID pk, note_text, created_at, updated_at
  - Connection.latest_signal and Connection.cadence_due_at nullable fields
  - OutreachQueueItem.signal, signal_context, mini_key_factors nullable fields
  - UserProfile.current_projects and goals_structured nullable fields
  - SIGNAL_ACTIONS canonical dict with all 7 signals (WARM_LEAD, NURTURE, VALUE_DROP, SYNERGY, RECONNECT, FUTURE_PIVOT, ARCHIVE)
  - apply_signal() function creating ContactSignal and updating Connection fields
  - backfill_skipped_signals() mapping existing skipped items to RECONNECT or FUTURE_PIVOT
  - PostgreSQL migration SQL with DDL, indexes, anon grants, and backfill statements
affects:
  - 07-02 (PWA signal UI — consumes SIGNAL_ACTIONS and new models)
  - 07-03 (push sync — needs new CONNECTION_SYNC_FIELDS and table sync for contact_signals)
  - 09-queue-intelligence (pipeline wiring for signal_service)
  - 10-draft-enhancement (tone adaptation reads latest_signal)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - SQLModel UUID pk via Field(default_factory=lambda: str(uuid.uuid4())) — same as Connection
    - Signal service as canonical Python source of truth; PWA mirrors as JS const
    - Lazy import of OutreachQueueItem in backfill_skipped_signals to avoid circular imports

key-files:
  created:
    - src/services/signal_service.py
    - supabase/migrations/20260311000000_signal_foundation.sql
    - tests/test_phase7_signal_foundation.py
  modified:
    - src/database/models.py
    - src/database/__init__.py

key-decisions:
  - "SIGNAL_ACTIONS defined once in signal_service.py as canonical source; never duplicated in pipeline or migration"
  - "No __table_args__ partial index in OutreachQueueItem SQLModel — PostgreSQL-only syntax stays in migration SQL only"
  - "signal_service.py NOT wired into daily_pipeline.py — deferred to Phase 9 queue intelligence"
  - "ContactNote table added alongside connections.notes field — structured history vs. quick free-form field"

patterns-established:
  - "Signal service pattern: single Python module is canonical SSOT; PWA mirrors as JS const"
  - "Backfill strategy: conservative FUTURE_PIVOT for explicit user skips, RECONNECT for auto-timeouts"

requirements-completed: [CAD-01, SIG-03]

# Metrics
duration: 5min
completed: 2026-03-12
---

# Phase 7 Plan 01: Signal Foundation Summary

**SQLModel signal data layer with 7-signal SIGNAL_ACTIONS dict, apply_signal() and backfill functions, ContactSignal and ContactNote models, and idempotent PostgreSQL migration SQL**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-03-12T02:34:34Z
- **Completed:** 2026-03-12T02:39:01Z
- **Tasks:** 3 (2 TDD, 1 auto)
- **Files modified:** 5

## Accomplishments
- ContactSignal and ContactNote SQLModel models with UUID pk, FK to connections, and correct tablenames
- New nullable fields on three existing models: Connection (latest_signal, cadence_due_at), OutreachQueueItem (signal, signal_context, mini_key_factors), UserProfile (current_projects, goals_structured)
- signal_service.py with SIGNAL_ACTIONS canonical dict (7 signals, exact values per CONTEXT.md), apply_signal() creating ContactSignal records and updating Connection fields, backfill_skipped_signals() mapping existing skipped items
- PostgreSQL migration SQL with all DDL, indexes, unique partial index, anon grants, and backfill UPDATE statements
- 47 new passing tests; all 102 tests pass (55 pre-existing + 47 new)

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: Test file** - `74c03c0` (test)
2. **Task 1 GREEN: Models + __init__.py** - `46875bc` (feat)
3. **Task 2 GREEN: signal_service.py** - `acc6627` (feat)
4. **Task 3: Migration SQL** - `d42d509` (feat)

_Note: TDD tasks have separate test (RED) and implementation (GREEN) commits_

## Files Created/Modified
- `src/database/models.py` - Added ContactSignal, ContactNote models; new fields on Connection, OutreachQueueItem, UserProfile
- `src/database/__init__.py` - Added ContactSignal and ContactNote to imports and __all__
- `src/services/signal_service.py` - New: SIGNAL_ACTIONS, SignalAction dataclass, apply_signal(), backfill_skipped_signals()
- `supabase/migrations/20260311000000_signal_foundation.sql` - New: full DDL migration for signal foundation
- `tests/test_phase7_signal_foundation.py` - New: 47 tests covering all models, service functions, and exports

## Decisions Made
- SIGNAL_ACTIONS defined once in signal_service.py as canonical source — never duplicated in pipeline or migration
- No `__table_args__` partial index in OutreachQueueItem SQLModel — PostgreSQL-only UNIQUE partial index stays only in migration SQL to avoid breaking SQLite init_db()
- signal_service.py is NOT wired into daily_pipeline.py — deferred to Phase 9 per plan instruction
- ContactNote table added alongside existing connections.notes field — provides queryable timestamped history while preserving free-form field for PWA quick edit

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
Migration SQL is ready but must be applied manually to Supabase PostgreSQL:
```bash
# Apply via psql or Supabase dashboard SQL editor
psql $DATABASE_URL -f supabase/migrations/20260311000000_signal_foundation.sql
```
No new environment variables required.

## Next Phase Readiness
- All models, service module, and migration SQL are ready for subsequent v1.2 phases
- Phase 7 Plan 02 (if any) or Phase 8 (PWA signal UI) can import from src.services.signal_service immediately
- Phase 9 (queue intelligence) wires signal_service into daily_pipeline.py
- Migration SQL must be applied to Supabase before PWA features can write signals

---
*Phase: 07-signal-foundation*
*Completed: 2026-03-12*
