-- Signal Foundation: contact_signals table, contact_notes table,
-- new columns on connections/outreach_queue/user_profile,
-- backfill of skipped items

-- ---------------------------------------------------------------------------
-- contact_signals: records triage signals applied to contacts
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS contact_signals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    connection_id TEXT REFERENCES connections(id),
    signal TEXT NOT NULL,           -- WARM_LEAD | NURTURE | VALUE_DROP | SYNERGY | RECONNECT | FUTURE_PIVOT | ARCHIVE
    signal_context TEXT,            -- Optional freeform context for the signal
    assigned_at TIMESTAMPTZ DEFAULT NOW(),
    assigned_by TEXT NOT NULL DEFAULT 'user'  -- 'user' | 'system' | 'pipeline'
);
CREATE INDEX IF NOT EXISTS idx_contact_signals_connection ON contact_signals(connection_id);
CREATE INDEX IF NOT EXISTS idx_contact_signals_signal ON contact_signals(signal);

-- ---------------------------------------------------------------------------
-- contact_notes: timestamped notes attached to a contact
-- Complements connections.notes (free-form); provides queryable history
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS contact_notes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    connection_id TEXT REFERENCES connections(id),
    note_text TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_contact_notes_connection ON contact_notes(connection_id);

-- ---------------------------------------------------------------------------
-- New columns on connections
-- ---------------------------------------------------------------------------

ALTER TABLE connections ADD COLUMN IF NOT EXISTS latest_signal TEXT;          -- Last applied signal name
ALTER TABLE connections ADD COLUMN IF NOT EXISTS cadence_due_at TIMESTAMPTZ;  -- Next re-queue date

-- ---------------------------------------------------------------------------
-- New columns on outreach_queue
-- ---------------------------------------------------------------------------

ALTER TABLE outreach_queue ADD COLUMN IF NOT EXISTS signal TEXT;              -- Applied triage signal
ALTER TABLE outreach_queue ADD COLUMN IF NOT EXISTS signal_context TEXT;      -- Context for the signal
ALTER TABLE outreach_queue ADD COLUMN IF NOT EXISTS mini_key_factors TEXT;    -- LLM-generated key factors (Phase 10)

-- ---------------------------------------------------------------------------
-- New columns on user_profile
-- ---------------------------------------------------------------------------

ALTER TABLE user_profile ADD COLUMN IF NOT EXISTS current_projects TEXT;      -- User's active projects context
ALTER TABLE user_profile ADD COLUMN IF NOT EXISTS goals_structured JSONB;     -- Structured goals for LLM context

-- ---------------------------------------------------------------------------
-- Unique partial index on outreach_queue
-- Prevents duplicate active queue entries per connection
-- NOTE: PostgreSQL-only syntax — NOT added to SQLModel models.py (would break SQLite)
-- ---------------------------------------------------------------------------

CREATE UNIQUE INDEX IF NOT EXISTS idx_outreach_queue_active_unique
    ON outreach_queue(connection_id)
    WHERE status IN ('pending_review', 'approved');

-- ---------------------------------------------------------------------------
-- Anon role grants (PostgREST PWA access)
-- ---------------------------------------------------------------------------

GRANT SELECT, INSERT ON contact_signals TO anon;
GRANT SELECT, INSERT, UPDATE ON contact_notes TO anon;

-- ---------------------------------------------------------------------------
-- Backfill: assign signals to existing skipped outreach_queue items
-- Maps auto-skips (Queue reset / Auto-expired) to RECONNECT
-- Maps explicit user skips (reviewed_at set, no auto-reason) to FUTURE_PIVOT
-- Only runs on items that don't already have a signal
-- ---------------------------------------------------------------------------

UPDATE outreach_queue
    SET signal = 'RECONNECT'
    WHERE status = 'skipped'
      AND signal IS NULL
      AND (skip_reason LIKE '%Queue reset%' OR skip_reason LIKE '%Auto-expired%');

UPDATE outreach_queue
    SET signal = 'FUTURE_PIVOT'
    WHERE status = 'skipped'
      AND signal IS NULL
      AND reviewed_at IS NOT NULL
      AND (skip_reason IS NULL
           OR (skip_reason NOT LIKE '%Queue reset%' AND skip_reason NOT LIKE '%Auto-expired%'));
