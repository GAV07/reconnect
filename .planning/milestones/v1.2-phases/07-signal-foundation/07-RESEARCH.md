# Phase 7: Signal Foundation - Research

**Researched:** 2026-03-11
**Domain:** SQLModel schema migration, psycopg2-direct PostgreSQL migration, Python service module patterns
**Confidence:** HIGH

## Summary

Phase 7 is an infrastructure-only phase — no user-facing changes. It delivers two new tables (`contact_signals`, `contact_notes`), nullable columns on three existing tables (`connections`, `outreach_queue`, `user_profile`), a canonical Python service module (`signal_service.py`), and a one-time SQL backfill of existing "skipped" queue items.

All patterns for this phase are already established in the codebase. SQLModel table definitions, psycopg2-direct PostgreSQL migrations, the `init_db()` auto-create path for SQLite, `CONNECTION_SYNC_FIELDS` for push sync, and the `dashboard_service.py` module structure are all proven patterns with zero unknown territory. The only decision work is correctly implementing the `SIGNAL_ACTIONS` dict and backfill SQL — both of which have exact specifications in CONTEXT.md.

The unique partial index on `outreach_queue(connection_id) WHERE status IN ('pending_review', 'approved')` is the single technically novel element. It requires PostgreSQL-specific syntax in the migration but is straightforward and tested. SQLite does not support partial indexes via SQLModel metadata, so it must only appear in the Supabase SQL migration file, not in models.py `__table_args__`.

**Primary recommendation:** Follow established patterns exactly. The entire phase is pattern-application, not pattern-discovery. The only new code requiring judgment is `apply_signal()` and the backfill SQL logic for classifying existing skipped items.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Notes storage:** Use BOTH — keep existing `connections.notes` column for simple free-form text AND add new `contact_notes` table for timestamped, structured note entries. `connections.notes` remains the quick-edit field visible on queue cards. `contact_notes` provides queryable history with timestamps per note entry.

**Signal cadence values (canonical source: signal_service.py):**
- WARM_LEAD: 7 days, queue status approved, priority boost +15
- NURTURE: 21 days, queue status pending_review, no boost
- VALUE_DROP: 14 days, queue status skipped, no boost
- SYNERGY: 14 days, queue status approved, priority boost +10
- RECONNECT: 14 days, queue status approved, priority boost +5
- FUTURE_PIVOT: 60 days, queue status pending_review, no boost
- ARCHIVE: never re-queued, queue status skipped, sets user_priority = "never"

**Skipped item backfill strategy:**
- Existing "skipped" items with `skip_reason` containing "Queue reset" or "Auto-expired" → signal RECONNECT
- Existing "skipped" items with explicit user skip (reviewed_at set, no auto-reason) → signal FUTURE_PIVOT
- One-time migration; mapping is intentionally conservative

**Migration approach:**
- Follow established psycopg2-direct pattern (same as `20260305000000_pwa_overhaul.sql`)
- New tables: `contact_signals` (id, connection_id, signal, signal_context, assigned_at, assigned_by), `contact_notes` (id, connection_id, note_text, created_at, updated_at)
- New columns on `connections`: `latest_signal` (text, nullable), `cadence_due_at` (datetime, nullable)
- New columns on `outreach_queue`: `signal` (text, nullable), `signal_context` (text, nullable), `mini_key_factors` (text, nullable)
- New columns on `user_profile`: `current_projects` (text, nullable), `goals_structured` (json, nullable)
- Anon role grants on new tables for PostgREST PWA access
- Unique partial index on `outreach_queue(connection_id) WHERE status IN ('pending_review', 'approved')`

**Signal service design:**
- Single Python module `src/services/signal_service.py`
- `SIGNAL_ACTIONS` dict: maps signal name to {cadence_days, queue_status, priority_boost, description}
- `apply_signal()` function: given connection_id and signal, writes to `contact_signals`, updates `connections.latest_signal` and `connections.cadence_due_at`
- Age-based cadence: `signal_assigned_at + cadence_days <= today` evaluated at query time
- Module is the single source of truth; PWA mirrors values as a JS const

**Migration filename:** `20260311000000_signal_foundation.sql`

### Claude's Discretion
- Exact column types and constraints in migration SQL (within the spec above)
- Index strategy beyond the required unique partial index
- `apply_signal()` internal implementation details
- Whether to add `signal_service.py` to pipeline imports now or defer to Phase 9

### Deferred Ideas (OUT OF SCOPE)
- Signal-based queue exclusion rules — Phase 9 (queue_generator.py changes)
- Signal-informed rescoring — Phase 9 (feedback_processor.py changes)
- PWA signal picker UI — Phase 8
- Draft tone adaptation — Phase 10
- Pull sync for signals/notes — Phase 9
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| CAD-01 | Each signal defines a default cadence (days until contact reappears in queue) | `SIGNAL_ACTIONS` dict in `signal_service.py` defines all 7 cadence values; `connections.cadence_due_at` and `connections.latest_signal` columns make cadence queryable from pipeline |
| SIG-03 (schema precondition) | Each signal assignment is stored with timestamp and persisted to Supabase | `contact_signals` table with `assigned_at` timestamp + push.py sync section; `apply_signal()` writes the record and updates connection denormalized fields |
</phase_requirements>

---

## Standard Stack

### Core (already in project)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| SQLModel | installed | ORM for SQLite + PostgreSQL models | Already used for all tables in models.py |
| SQLAlchemy | installed | Column types (JSON, Text), Index | Backend for SQLModel; JSON/Column pattern established |
| psycopg2 | installed (via supabase_db_url) | PostgreSQL migration execution | Established pattern from 20260305000000_pwa_overhaul.sql |
| pytest | installed | Test framework | 58 tests currently passing with `pytest tests/ -x -q` |

### No new dependencies required
All libraries needed for Phase 7 are already installed. Zero new `pip install` commands needed.

**Quick test run:** `python -m pytest tests/test_phase7_signal_foundation.py -x -q`
**Full suite:** `python -m pytest tests/ -x -q`

## Architecture Patterns

### Recommended Project Structure additions
```
src/
├── services/
│   ├── dashboard_service.py  # existing pattern
│   └── signal_service.py     # NEW: canonical signal definitions + apply_signal()
├── database/
│   └── models.py             # add ContactSignal, ContactNote models; add fields to Connection/OutreachQueueItem/UserProfile
├── sync/
│   └── push.py               # add new fields to CONNECTION_SYNC_FIELDS; add contact_signals/contact_notes sync sections
supabase/
└── migrations/
    └── 20260311000000_signal_foundation.sql  # NEW: PostgreSQL DDL
tests/
└── test_phase7_signal_foundation.py  # NEW: unit tests
```

### Pattern 1: SQLModel Table Definition (existing pattern — apply verbatim)
**What:** New tables follow identical SQLModel class structure
**When to use:** ContactSignal and ContactNote models

```python
# Source: src/database/models.py existing pattern
class ContactSignal(SQLModel, table=True):
    """Track signal assignments for contacts."""

    __tablename__ = "contact_signals"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    connection_id: str = Field(foreign_key="connections.id", index=True)
    signal: str  # WARM_LEAD | NURTURE | VALUE_DROP | SYNERGY | RECONNECT | FUTURE_PIVOT | ARCHIVE
    signal_context: Optional[str] = Field(default=None, sa_column=Column(Text))
    assigned_at: datetime = Field(default_factory=datetime.utcnow)
    assigned_by: str = Field(default="user")  # "user" | "system" | "pipeline"


class ContactNote(SQLModel, table=True):
    """Timestamped, structured note entries per contact."""

    __tablename__ = "contact_notes"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    connection_id: str = Field(foreign_key="connections.id", index=True)
    note_text: str = Field(sa_column=Column(Text))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
```

### Pattern 2: Adding nullable columns to existing models
**What:** Add new Optional fields to Connection, OutreachQueueItem, UserProfile
**When to use:** Three existing model classes need new fields

```python
# Source: existing pattern in Connection model (e.g., user_priority addition in Phase 3)
# In Connection class — add after existing fields:
latest_signal: Optional[str] = None  # WARM_LEAD | NURTURE | etc.
cadence_due_at: Optional[datetime] = Field(default=None)

# In OutreachQueueItem class:
signal: Optional[str] = None
signal_context: Optional[str] = Field(default=None, sa_column=Column(Text))
mini_key_factors: Optional[str] = Field(default=None, sa_column=Column(Text))

# In UserProfile class:
current_projects: Optional[str] = Field(default=None, sa_column=Column(Text))
goals_structured: Optional[dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
```

### Pattern 3: Service module (dashboard_service.py pattern)
**What:** Module-level constants dict + pure functions using `get_session()`
**When to use:** signal_service.py structure

```python
# Source: src/services/dashboard_service.py pattern
"""Signal definitions and assignment service for Reconnect.

SIGNAL_ACTIONS is the canonical source of truth for all signal behavior.
The PWA mirrors these values as a JS const. The pipeline consumes them
for cadence logic (Phase 9).
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Optional

from sqlmodel import select

from src.database.engine import get_session
from src.database.models import Connection, ContactSignal


@dataclass
class SignalAction:
    cadence_days: Optional[int]  # None for ARCHIVE (never re-queued)
    queue_status: str             # pending_review | approved | skipped
    priority_boost: int           # 0-15
    description: str


SIGNAL_ACTIONS: dict[str, SignalAction] = {
    "WARM_LEAD":    SignalAction(cadence_days=7,  queue_status="approved",        priority_boost=15, description="Hot lead — follow up in 7 days"),
    "NURTURE":      SignalAction(cadence_days=21, queue_status="pending_review",  priority_boost=0,  description="Worth nurturing — 21-day cadence"),
    "VALUE_DROP":   SignalAction(cadence_days=14, queue_status="skipped",         priority_boost=0,  description="Share value — reappear in 14 days"),
    "SYNERGY":      SignalAction(cadence_days=14, queue_status="approved",        priority_boost=10, description="Mutual benefit — follow up in 14 days"),
    "RECONNECT":    SignalAction(cadence_days=14, queue_status="approved",        priority_boost=5,  description="Reconnect — follow up in 14 days"),
    "FUTURE_PIVOT": SignalAction(cadence_days=60, queue_status="pending_review",  priority_boost=0,  description="Potential later — 60-day cadence"),
    "ARCHIVE":      SignalAction(cadence_days=None, queue_status="skipped",       priority_boost=0,  description="Archive — never re-queue"),
}


def apply_signal(
    connection_id: str,
    signal: str,
    signal_context: Optional[str] = None,
    assigned_by: str = "user",
) -> ContactSignal:
    """Assign a signal to a contact.

    Writes to contact_signals, updates connections.latest_signal and
    connections.cadence_due_at. For ARCHIVE, also sets user_priority = "never".

    Returns the created ContactSignal record.
    """
    action = SIGNAL_ACTIONS[signal]
    now = datetime.utcnow()

    cadence_due_at = (
        now + timedelta(days=action.cadence_days)
        if action.cadence_days is not None
        else None
    )

    with get_session() as session:
        record = ContactSignal(
            connection_id=connection_id,
            signal=signal,
            signal_context=signal_context,
            assigned_at=now,
            assigned_by=assigned_by,
        )
        session.add(record)

        conn = session.get(Connection, connection_id)
        if conn:
            conn.latest_signal = signal
            conn.cadence_due_at = cadence_due_at
            if signal == "ARCHIVE":
                conn.user_priority = "never"
            session.add(conn)

    return record
```

### Pattern 4: psycopg2-direct PostgreSQL migration (established pattern)
**What:** Raw SQL file executed via psycopg2, not SQLAlchemy DDL
**When to use:** 20260311000000_signal_foundation.sql

```sql
-- Source: supabase/migrations/20260305000000_pwa_overhaul.sql pattern

-- New table: contact_signals
CREATE TABLE IF NOT EXISTS contact_signals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    connection_id TEXT REFERENCES connections(id),
    signal TEXT NOT NULL,  -- WARM_LEAD | NURTURE | VALUE_DROP | SYNERGY | RECONNECT | FUTURE_PIVOT | ARCHIVE
    signal_context TEXT,
    assigned_at TIMESTAMPTZ DEFAULT NOW(),
    assigned_by TEXT NOT NULL DEFAULT 'user'  -- 'user' | 'system' | 'pipeline'
);
CREATE INDEX IF NOT EXISTS idx_contact_signals_connection ON contact_signals(connection_id);
CREATE INDEX IF NOT EXISTS idx_contact_signals_signal ON contact_signals(signal);

-- New table: contact_notes
CREATE TABLE IF NOT EXISTS contact_notes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    connection_id TEXT REFERENCES connections(id),
    note_text TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_contact_notes_connection ON contact_notes(connection_id);

-- New columns on connections
ALTER TABLE connections ADD COLUMN IF NOT EXISTS latest_signal TEXT;
ALTER TABLE connections ADD COLUMN IF NOT EXISTS cadence_due_at TIMESTAMPTZ;

-- New columns on outreach_queue
ALTER TABLE outreach_queue ADD COLUMN IF NOT EXISTS signal TEXT;
ALTER TABLE outreach_queue ADD COLUMN IF NOT EXISTS signal_context TEXT;
ALTER TABLE outreach_queue ADD COLUMN IF NOT EXISTS mini_key_factors TEXT;

-- New columns on user_profile
ALTER TABLE user_profile ADD COLUMN IF NOT EXISTS current_projects TEXT;
ALTER TABLE user_profile ADD COLUMN IF NOT EXISTS goals_structured JSONB;

-- Unique partial index: only one active queue entry per contact
CREATE UNIQUE INDEX IF NOT EXISTS idx_outreach_queue_active_unique
    ON outreach_queue(connection_id)
    WHERE status IN ('pending_review', 'approved');

-- Anon role grants for PostgREST PWA access
GRANT SELECT, INSERT ON contact_signals TO anon;
GRANT SELECT, INSERT, UPDATE ON contact_notes TO anon;
```

### Pattern 5: CONNECTION_SYNC_FIELDS extension
**What:** New Connection columns must be added to the sync list
**When to use:** push.py update

```python
# Source: src/sync/push.py CONNECTION_SYNC_FIELDS
CONNECTION_SYNC_FIELDS = [
    # ... existing fields ...
    # Signal foundation fields (Phase 7)
    "latest_signal",
    "cadence_due_at",
]
```

### Pattern 6: New table sync sections in push.py
**What:** Push ContactSignal and ContactNote records to cloud
**When to use:** push_to_cloud() additions — same incremental pattern as other tables

```python
# Source: push.py sections 6, 7, 8 pattern
# Push ContactSignals (new records only — signals are immutable once written)
with Session(local_engine, expire_on_commit=False) as local_session:
    query = select(ContactSignal)
    if last_push_at:
        query = query.where(ContactSignal.assigned_at > last_push_at)
    signals = local_session.exec(query).all()
    for sig in signals:
        data = _record_to_dict(sig)
        _upsert_record(cloud_session, ContactSignal, data)
        stats["contact_signals"] += 1
```

### Pattern 7: Backfill SQL
**What:** One-time UPDATE to assign signal to existing skipped items
**Where:** At end of migration SQL file, inside a DO block or as plain UPDATE statements

```sql
-- Backfill: Queue reset / Auto-expired skipped items → RECONNECT
UPDATE outreach_queue
SET signal = 'RECONNECT'
WHERE status = 'skipped'
  AND signal IS NULL
  AND (skip_reason LIKE '%Queue reset%' OR skip_reason LIKE '%Auto-expired%');

-- Backfill: Explicit user skips (reviewed_at set, no auto-reason) → FUTURE_PIVOT
UPDATE outreach_queue
SET signal = 'FUTURE_PIVOT'
WHERE status = 'skipped'
  AND signal IS NULL
  AND reviewed_at IS NOT NULL
  AND (skip_reason IS NULL OR (
    skip_reason NOT LIKE '%Queue reset%'
    AND skip_reason NOT LIKE '%Auto-expired%'
  ));
```

### Anti-Patterns to Avoid

- **Partial index in SQLModel __table_args__:** SQLite does not support partial indexes. The unique partial index for `outreach_queue` must ONLY exist in the PostgreSQL migration SQL file, not in the OutreachQueueItem model's `__table_args__`. Adding it there would break `init_db()` on SQLite.
- **Storing cadence_due_at as absolute timestamp computed once at assignment:** The CONTEXT.md specifies age-based evaluation (`signal_assigned_at + cadence_days <= today` at query time). `cadence_due_at` IS stored — computed as `assigned_at + cadence_days` — but the evaluation for re-queuing (Phase 9) will be `cadence_due_at <= today`, not re-computed on the fly. Storing it is correct for efficient querying.
- **Modifying is_contact_excluded() in queue_generator.py:** This is deferred to Phase 9. Phase 7 does NOT touch queue_generator.py at all.
- **Using EngagementSignal as a name for ContactSignal:** These are different: `engagement_signals` tracks LinkedIn engagement (reactions, endorsements). `contact_signals` tracks intent triage decisions. Different tables, different purposes, no naming collision.
- **Multi-statement DDL via SQLAlchemy:** MEMORY.md explicitly notes "Migration applied directly via psycopg2 (SQLAlchemy had issues with multi-statement DDL)." Use the established pattern: read the .sql file and execute via psycopg2.
- **Adding `signal_service.py` to pipeline's `daily_pipeline.py` imports in Phase 7:** CONTEXT.md defers this to Phase 9 as "Claude's Discretion." Safer to defer — Phase 7 creates the module, Phase 9 wires it in.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Upsert to cloud | Custom INSERT/UPDATE logic | `_upsert_record()` in push.py | Already handles both insert and update branches, tested across 10 table types |
| Session management | Manual session open/close | `get_session()` context manager | Handles commit, rollback, and close correctly |
| SQLite table creation | Manual CREATE TABLE | `SQLModel.metadata.create_all()` via `init_db()` | Auto-creates from model definitions, handles IF NOT EXISTS |
| Dict from model | Manual attribute extraction | `_record_to_dict(record, fields)` | Handles optional field filtering, column name mapping |

**Key insight:** All the infrastructure for adding new tables and columns is already written. This phase is entirely pattern-application — the helpers that handle sync, sessions, and table creation are proven and reusable.

## Common Pitfalls

### Pitfall 1: Partial index in SQLModel __table_args__ breaks SQLite
**What goes wrong:** Adding `Index("idx_active_unique", "connection_id", unique=True, postgresql_where=...)` to OutreachQueueItem's `__table_args__` fails when `init_db()` runs on SQLite.
**Why it happens:** SQLite does not support partial (filtered) indexes via SQLAlchemy. The `postgresql_where` kwarg is PostgreSQL-only.
**How to avoid:** Put the partial index ONLY in the PostgreSQL migration SQL file. SQLModel table definition in models.py gets no new `__table_args__`.
**Warning signs:** `OperationalError: near "WHERE"` when running tests or `init_db()` locally.

### Pitfall 2: Signal column name collision with existing EngagementSignal
**What goes wrong:** Confusion between `engagement_signals` table (existing) and `contact_signals` table (new).
**Why it happens:** Both use "signal" terminology but mean different things.
**How to avoid:** Use full table name `contact_signals` consistently. Import the new model as `ContactSignal` not `Signal`. Never import `EngagementSignal` and `ContactSignal` in the same file without aliasing.

### Pitfall 3: Forgetting `__init__.py` export updates
**What goes wrong:** New models (`ContactSignal`, `ContactNote`) fail to import in other modules because they're not in `src/database/__init__.py`.
**Why it happens:** The `__init__.py` has an explicit `__all__` list — new models must be added manually.
**How to avoid:** Update `__init__.py` `__all__` list and import block whenever a new model is added to models.py.

### Pitfall 4: push.py stats dict missing new keys
**What goes wrong:** `push_to_cloud()` returns a stats dict — new table sync sections must add their keys to the initialization dict at the top of the function.
**Why it happens:** The stats dict is initialized explicitly at the top of `push_to_cloud()`, not built dynamically.
**How to avoid:** Add `"contact_signals": 0` and `"contact_notes": 0` to the stats dict initialization alongside adding the sync sections.

### Pitfall 5: Backfill runs on both SQLite and PostgreSQL
**What goes wrong:** If the backfill SQL is in the migration file, it only runs on PostgreSQL (Supabase). The local SQLite database also has skipped items that need backfilling.
**Why it happens:** The migration file is only applied to Supabase. SQLite uses `init_db()` which creates tables from models but doesn't run arbitrary SQL.
**How to avoid:** Implement the backfill as a Python function that runs against the local SQLite session using SQLModel queries. This function executes the same logic as the SQL UPDATE statements but via ORM. It can also be included in the migration SQL for the PostgreSQL side.

### Pitfall 6: `goals_structured` JSON column in UserProfile
**What goes wrong:** `goals_structured` must use `sa_column=Column(JSON)` pattern. Without it, SQLModel will try to store a dict as a plain string on SQLite.
**Why it happens:** SQLite doesn't have a native JSON type — SQLAlchemy handles serialization when `Column(JSON)` is specified.
**How to avoid:** Follow the existing `raw_profile`, `inferred_expertise`, `inferred_interests` pattern in UserProfile:
```python
goals_structured: Optional[dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
```

## Code Examples

### Full signal_service.py structure
```python
# Source: src/services/dashboard_service.py structural pattern
"""Signal definitions and assignment service for Reconnect.

SIGNAL_ACTIONS is the canonical single source of truth for all signal behavior.
Consumed by: pipeline (Phase 9+), PWA (mirrors as JS const), backfill migration.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from src.database.engine import get_session
from src.database.models import Connection, ContactSignal

logger = logging.getLogger(__name__)


@dataclass
class SignalAction:
    cadence_days: Optional[int]  # None = never re-queued (ARCHIVE)
    queue_status: str
    priority_boost: int
    description: str


SIGNAL_ACTIONS: dict[str, SignalAction] = {
    "WARM_LEAD":    SignalAction(7,    "approved",       15, "Hot lead — follow up in 7 days"),
    "NURTURE":      SignalAction(21,   "pending_review", 0,  "Worth nurturing — 21-day cadence"),
    "VALUE_DROP":   SignalAction(14,   "skipped",        0,  "Share value — reappear in 14 days"),
    "SYNERGY":      SignalAction(14,   "approved",       10, "Mutual benefit — follow up in 14 days"),
    "RECONNECT":    SignalAction(14,   "approved",       5,  "Reconnect — follow up in 14 days"),
    "FUTURE_PIVOT": SignalAction(60,   "pending_review", 0,  "Potential later — 60-day cadence"),
    "ARCHIVE":      SignalAction(None, "skipped",        0,  "Archive — never re-queue"),
}


def apply_signal(
    connection_id: str,
    signal: str,
    signal_context: Optional[str] = None,
    assigned_by: str = "user",
) -> ContactSignal:
    """Assign a signal to a contact.

    Writes to contact_signals. Updates connections.latest_signal and
    connections.cadence_due_at. For ARCHIVE, also sets user_priority = "never".
    """
    if signal not in SIGNAL_ACTIONS:
        raise ValueError(f"Unknown signal: {signal}. Must be one of {list(SIGNAL_ACTIONS)}")

    action = SIGNAL_ACTIONS[signal]
    now = datetime.utcnow()
    cadence_due_at = (
        now + timedelta(days=action.cadence_days)
        if action.cadence_days is not None
        else None
    )

    with get_session() as session:
        record = ContactSignal(
            connection_id=connection_id,
            signal=signal,
            signal_context=signal_context,
            assigned_at=now,
            assigned_by=assigned_by,
        )
        session.add(record)

        conn = session.get(Connection, connection_id)
        if conn:
            conn.latest_signal = signal
            conn.cadence_due_at = cadence_due_at
            if signal == "ARCHIVE":
                conn.user_priority = "never"
            session.add(conn)

        logger.info("Applied signal %s to connection %s (by %s)", signal, connection_id, assigned_by)

    return record
```

### Backfill function (Python, for SQLite)
```python
def backfill_skipped_signals() -> dict[str, int]:
    """One-time backfill: assign default signals to existing skipped queue items.

    Strategy (from CONTEXT.md):
    - skip_reason contains "Queue reset" or "Auto-expired" → RECONNECT
    - explicit user skip (reviewed_at set, no auto-reason) → FUTURE_PIVOT
    """
    from sqlmodel import select
    from src.database.models import OutreachQueueItem

    counts = {"reconnect": 0, "future_pivot": 0, "already_set": 0}

    with get_session() as session:
        items = session.exec(
            select(OutreachQueueItem).where(OutreachQueueItem.status == "skipped")
        ).all()

        for item in items:
            if item.signal is not None:
                counts["already_set"] += 1
                continue

            reason = item.skip_reason or ""
            if "Queue reset" in reason or "Auto-expired" in reason:
                item.signal = "RECONNECT"
                counts["reconnect"] += 1
            elif item.reviewed_at is not None:
                item.signal = "FUTURE_PIVOT"
                counts["future_pivot"] += 1
            session.add(item)

    return counts
```

### Test pattern for signal_service.py
```python
# Source: tests/test_phase5_dashboard.py pattern — mock get_session
from contextlib import contextmanager
from unittest.mock import MagicMock, patch
import pytest

from src.services.signal_service import SIGNAL_ACTIONS, apply_signal


def test_signal_actions_all_seven_defined():
    """SIGNAL_ACTIONS contains all 7 required signals."""
    required = {"WARM_LEAD", "NURTURE", "VALUE_DROP", "SYNERGY",
                "RECONNECT", "FUTURE_PIVOT", "ARCHIVE"}
    assert set(SIGNAL_ACTIONS.keys()) == required


def test_warm_lead_cadence():
    """WARM_LEAD has 7-day cadence, approved status, +15 boost."""
    action = SIGNAL_ACTIONS["WARM_LEAD"]
    assert action.cadence_days == 7
    assert action.queue_status == "approved"
    assert action.priority_boost == 15


def test_archive_no_cadence():
    """ARCHIVE has None cadence (never re-queued)."""
    action = SIGNAL_ACTIONS["ARCHIVE"]
    assert action.cadence_days is None
    assert action.queue_status == "skipped"


def test_apply_signal_writes_record(monkeypatch):
    """apply_signal() creates a ContactSignal record and updates connection."""
    mock_session = MagicMock()
    mock_conn = MagicMock()
    mock_conn.id = "conn-123"
    mock_session.get.return_value = mock_conn

    @contextmanager
    def mock_get_session():
        yield mock_session

    monkeypatch.setattr("src.services.signal_service.get_session", mock_get_session)

    result = apply_signal("conn-123", "WARM_LEAD", signal_context="Test", assigned_by="user")

    assert result.signal == "WARM_LEAD"
    assert result.assigned_by == "user"
    assert mock_conn.latest_signal == "WARM_LEAD"
    assert mock_conn.cadence_due_at is not None  # 7 days from now


def test_apply_signal_archive_sets_user_priority_never(monkeypatch):
    """apply_signal() with ARCHIVE sets user_priority = 'never'."""
    mock_session = MagicMock()
    mock_conn = MagicMock()
    mock_session.get.return_value = mock_conn

    @contextmanager
    def mock_get_session():
        yield mock_session

    monkeypatch.setattr("src.services.signal_service.get_session", mock_get_session)

    apply_signal("conn-123", "ARCHIVE")
    assert mock_conn.user_priority == "never"
    assert mock_conn.cadence_due_at is None
```

## State of the Art

| Old Approach | Current Approach | Notes |
|--------------|------------------|-------|
| `skip_reason` text field as only signal state | Typed `signal` column with 7 canonical values | Phase 7 adds the typed column; Phase 9 wires exclusion logic to it |
| `skip_cooldown_days` setting in queue_generator | Signal-specific cadence days in SIGNAL_ACTIONS | Phase 9 replaces the cooldown check with cadence check |
| No per-contact notes table | `contact_notes` table with timestamps | Preserves existing `connections.notes` as quick-edit field |

**Not deprecated — keep as-is:**
- `connections.notes` field: still used for quick-edit notes on queue cards (Phase 8)
- `skip_cooldown_days` setting: still used by queue_generator.py in Phase 7 (Phase 9 replaces it)
- `status = "skipped"` in queue: still valid status; signal column augments it, doesn't replace it

## Open Questions

1. **Whether to add `signal_service.py` to pipeline imports in Phase 7**
   - What we know: CONTEXT.md marks this as "Claude's Discretion"
   - Recommendation: Do NOT import in daily_pipeline.py during Phase 7. The module exists but is not called by the pipeline until Phase 9 (`feedback_processor.py` and cadence re-queue logic). Importing it in Phase 7 creates an unused import. Add it in Phase 9 when it's first called.

2. **Unique partial index behavior when existing duplicates exist**
   - What we know: Existing data in `outreach_queue` may already have multiple "skipped" rows for the same `connection_id`. The partial index only applies to `status IN ('pending_review', 'approved')`.
   - What's clear: Since the index is partial (skipped rows not covered), existing skipped duplicates don't block index creation.
   - Recommendation: No data cleanup needed before running migration. The partial index is safe to add to existing data.

3. **SQLite test coverage for new tables**
   - What we know: Tests run against mocked sessions (no real SQLite DB needed for unit tests). Integration-level tests would require a real SQLite engine.
   - Recommendation: Unit tests use monkeypatched `get_session()` (same as test_phase5_dashboard.py pattern). No integration test setup needed for Phase 7.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (currently 58 tests, 55 pass, 3 skip) |
| Config file | none — runs via `pytest tests/` with no config file |
| Quick run command | `python -m pytest tests/test_phase7_signal_foundation.py -x -q` |
| Full suite command | `python -m pytest tests/ -x -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CAD-01 | SIGNAL_ACTIONS dict has all 7 signals with correct cadence_days | unit | `pytest tests/test_phase7_signal_foundation.py::test_signal_actions_all_seven_defined -x` | Wave 0 |
| CAD-01 | WARM_LEAD has cadence_days=7, approved status, +15 boost | unit | `pytest tests/test_phase7_signal_foundation.py::test_warm_lead_cadence -x` | Wave 0 |
| CAD-01 | ARCHIVE has cadence_days=None, skipped status | unit | `pytest tests/test_phase7_signal_foundation.py::test_archive_no_cadence -x` | Wave 0 |
| CAD-01 | All 7 cadence values match CONTEXT.md spec | unit | `pytest tests/test_phase7_signal_foundation.py::test_all_cadence_values -x` | Wave 0 |
| SIG-03 | apply_signal() creates ContactSignal record with correct fields | unit | `pytest tests/test_phase7_signal_foundation.py::test_apply_signal_writes_record -x` | Wave 0 |
| SIG-03 | apply_signal() updates connection latest_signal and cadence_due_at | unit | `pytest tests/test_phase7_signal_foundation.py::test_apply_signal_updates_connection -x` | Wave 0 |
| SIG-03 | apply_signal(ARCHIVE) sets user_priority="never" | unit | `pytest tests/test_phase7_signal_foundation.py::test_apply_signal_archive_sets_user_priority_never -x` | Wave 0 |
| SIG-03 | apply_signal() raises ValueError for unknown signal | unit | `pytest tests/test_phase7_signal_foundation.py::test_apply_signal_unknown_signal_raises -x` | Wave 0 |
| SIG-03 | backfill_skipped_signals() maps auto-reasons to RECONNECT | unit | `pytest tests/test_phase7_signal_foundation.py::test_backfill_reconnect_mapping -x` | Wave 0 |
| SIG-03 | backfill_skipped_signals() maps explicit skips to FUTURE_PIVOT | unit | `pytest tests/test_phase7_signal_foundation.py::test_backfill_future_pivot_mapping -x` | Wave 0 |
| SIG-03 | ContactSignal and ContactNote models importable, correct __tablename__ | unit | `pytest tests/test_phase7_signal_foundation.py::test_models_importable -x` | Wave 0 |
| SIG-03 | CONNECTION_SYNC_FIELDS includes latest_signal and cadence_due_at | unit | `pytest tests/test_phase7_signal_foundation.py::test_connection_sync_fields_updated -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/test_phase7_signal_foundation.py -x -q`
- **Per wave merge:** `python -m pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_phase7_signal_foundation.py` — covers all CAD-01 and SIG-03 requirements listed above

*(conftest.py and pytest framework are already in place — no new framework setup needed)*

## Sources

### Primary (HIGH confidence)
- Direct codebase inspection — `src/database/models.py`, `src/sync/push.py`, `src/sync/pull.py`, `src/services/dashboard_service.py`, `src/pipeline/queue_generator.py` — all patterns verified line-by-line
- `supabase/migrations/20260305000000_pwa_overhaul.sql` — migration pattern confirmed
- `tests/conftest.py` and `tests/test_phase5_dashboard.py` — test patterns confirmed
- `.planning/phases/07-signal-foundation/07-CONTEXT.md` — all locked decisions sourced from here

### Secondary (MEDIUM confidence)
- `MEMORY.md` note: "Migration applied directly via psycopg2 (SQLAlchemy had issues with multi-statement DDL)" — confirms the established migration execution pattern
- SQLite partial index limitation: standard SQLite behavior, confirmed by absence of `postgresql_where` anywhere in existing `__table_args__`

### Tertiary (LOW confidence)
- None — all findings verified against codebase or official project documentation

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — zero new dependencies; all libraries already installed and in use
- Architecture patterns: HIGH — every pattern has a direct codebase precedent
- Pitfalls: HIGH — all pitfalls identified from direct code inspection (SQLite partial index, __init__.py exports, push.py stats dict, etc.)
- Signal cadence values: HIGH — locked in CONTEXT.md, sourced from v1.2 research reconciliation

**Research date:** 2026-03-11
**Valid until:** This research is based on locked project decisions and static codebase patterns. Valid until models.py or push.py architecture changes (no expiry concern for this phase).
