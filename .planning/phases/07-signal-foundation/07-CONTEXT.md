# Phase 7: Signal Foundation - Context

**Gathered:** 2026-03-11
**Status:** Ready for planning
**Source:** Research synthesis (discuss-phase skipped — infrastructure phase with decisions from v1.2 research)

<domain>
## Phase Boundary

Database schema migration (two new tables, nullable columns on three existing tables), canonical signal service module (`signal_service.py`), and backfill of existing "skipped" queue items. This phase delivers the stable foundation consumed by all subsequent v1.2 phases. No user-facing changes.

</domain>

<decisions>
## Implementation Decisions

### Notes storage
- Use BOTH: keep existing `connections.notes` column for simple free-form text (already synced, already in CONNECTION_SYNC_FIELDS) AND add new `contact_notes` table for timestamped, structured note entries
- `connections.notes` remains the quick-edit field visible on queue cards
- `contact_notes` table provides queryable history with timestamps per note entry
- This avoids a breaking change to existing notes while adding richer note tracking for Phase 8

### Signal cadence values (canonical source: signal_service.py)
- WARM_LEAD: 7 days, queue status approved, priority boost +15
- NURTURE: 21 days, queue status pending_review, no boost
- VALUE_DROP: 14 days, queue status skipped, no boost
- SYNERGY: 14 days, queue status approved, priority boost +10
- RECONNECT: 14 days, queue status approved, priority boost +5
- FUTURE_PIVOT: 60 days, queue status pending_review, no boost
- ARCHIVE: never re-queued, queue status skipped, sets user_priority = "never"

### Skipped item backfill strategy
- Existing "skipped" items with `skip_reason` containing "Queue reset" or "Auto-expired" get signal RECONNECT (they were timed out, not intentionally dismissed)
- Existing "skipped" items with explicit user skip (reviewed_at set, no auto-reason) get signal FUTURE_PIVOT (conservative — don't permanently archive, but don't re-queue soon)
- This is a one-time migration; the mapping is intentionally conservative

### Migration approach
- Follow established psycopg2-direct pattern (same as `20260305000000_pwa_overhaul.sql`)
- New tables: `contact_signals` (id, connection_id, signal, signal_context, assigned_at, assigned_by), `contact_notes` (id, connection_id, note_text, created_at, updated_at)
- New columns on `connections`: `latest_signal` (text, nullable), `cadence_due_at` (datetime, nullable)
- New columns on `outreach_queue`: `signal` (text, nullable), `signal_context` (text, nullable), `mini_key_factors` (text, nullable)
- New columns on `user_profile`: `current_projects` (text, nullable), `goals_structured` (json, nullable)
- Anon role grants on new tables for PostgREST PWA access
- Unique partial index on `outreach_queue(connection_id) WHERE status IN ('pending_review', 'approved')` to prevent duplicate active queue entries

### Signal service design
- Single Python module `src/services/signal_service.py`
- `SIGNAL_ACTIONS` dict: maps signal name to {cadence_days, queue_status, priority_boost, description}
- `apply_signal()` function: given a connection_id and signal, writes to `contact_signals`, updates `connections.latest_signal` and `connections.cadence_due_at`
- Age-based cadence: `signal_assigned_at + cadence_days <= today` evaluated at query time, not stored as absolute timestamp
- This module is the single source of truth; PWA mirrors the values as a JS const

### Claude's Discretion
- Exact column types and constraints in migration SQL (within the spec above)
- Index strategy beyond the required unique partial index
- `apply_signal()` internal implementation details
- Whether to add `signal_service.py` to pipeline imports now or defer to Phase 9

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `src/database/models.py`: All existing SQLModel definitions; new models follow identical patterns (UUID pk, Field defaults, JSON columns via sa_column)
- `src/sync/push.py`: `CONNECTION_SYNC_FIELDS` list — new connection fields must be added here in Phase 7
- `src/pipeline/queue_generator.py`: `is_contact_excluded()` — Phase 7 does NOT modify this; exclusion rules are Phase 9
- `_record_to_dict()` and `_upsert_record()` in push.py: reusable for new table sync

### Established Patterns
- psycopg2-direct migration: see `supabase/migrations/20260305000000_pwa_overhaul.sql` for pattern
- SQLModel table definition: `class Foo(SQLModel, table=True)` with `__tablename__`, UUID pk via `Field(default_factory=lambda: str(uuid.uuid4()))`
- JSON columns: `sa_column=Column(JSON)` pattern used throughout
- Service modules: `src/services/dashboard_service.py` is the existing pattern for `signal_service.py`

### Integration Points
- `src/database/models.py` — add ContactSignal and ContactNote models, add fields to Connection/OutreachQueueItem/UserProfile
- `src/database/__init__.py` — export new models
- `src/sync/push.py` — add new fields to CONNECTION_SYNC_FIELDS, add new table sync sections
- `supabase/migrations/` — new migration file for PostgreSQL schema
- `src/database/engine.py` — `init_db()` auto-creates SQLite tables from models via `SQLModel.metadata.create_all()`

</code_context>

<specifics>
## Specific Ideas

- Cadence day values from FEATURES.md research table (reconciled where STACK.md disagreed)
- `contact_signals.assigned_by` field should distinguish "user" (PWA triage) from "system" (backfill migration) from "pipeline" (future auto-signal)
- Migration filename: `20260311000000_signal_foundation.sql`

</specifics>

<deferred>
## Deferred Ideas

- Signal-based queue exclusion rules — Phase 9 (queue_generator.py changes)
- Signal-informed rescoring — Phase 9 (feedback_processor.py changes)
- PWA signal picker UI — Phase 8
- Draft tone adaptation — Phase 10
- Pull sync for signals/notes — Phase 9

</deferred>

---

*Phase: 07-signal-foundation*
*Context gathered: 2026-03-11 via research synthesis*
