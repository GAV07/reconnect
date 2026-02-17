-- Initial schema for Reconnect CRM
-- Generated from SQLModel definitions

-- User profile (singleton table)
CREATE TABLE IF NOT EXISTS user_profile (
    id INTEGER PRIMARY KEY DEFAULT 1,
    name TEXT NOT NULL,
    "current_role" TEXT,
    company TEXT,
    industry TEXT,
    interests TEXT,
    goals TEXT,
    raw_profile JSONB,
    inferred_industry TEXT,
    inferred_seniority TEXT,
    inferred_expertise JSONB,
    inferred_interests JSONB,
    profile_auto_updated_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Connections (core contact model)
CREATE TABLE IF NOT EXISTS connections (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT,
    linkedin_url TEXT UNIQUE,
    "current_role" TEXT,
    current_company TEXT,
    location TEXT,
    connection_source TEXT DEFAULT 'linkedin_export',
    relationship_strength INTEGER,
    tags TEXT,
    notes TEXT,
    raw_enrichment JSONB,
    activity_log JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    enriched_at TIMESTAMPTZ,
    last_contacted_at TIMESTAMPTZ,
    cached_summary TEXT,
    cached_summary_at TIMESTAMPTZ,
    reconnect_score REAL,
    score_reasoning TEXT,
    scored_at TIMESTAMPTZ,
    last_message_date TIMESTAMPTZ,
    message_count INTEGER DEFAULT 0,
    initiated_by TEXT,
    conversation_summary TEXT,
    conversation_status TEXT,
    pre_score REAL,
    pre_score_tier INTEGER,
    pre_scored_at TIMESTAMPTZ,
    import_batch_id TEXT,
    is_new_connection BOOLEAN DEFAULT FALSE,
    connected_on TIMESTAMPTZ
);

-- Indexes for connections
CREATE INDEX IF NOT EXISTS idx_connections_name ON connections(name);
CREATE INDEX IF NOT EXISTS idx_connections_email ON connections(email);
CREATE INDEX IF NOT EXISTS idx_connections_current_role ON connections("current_role");
CREATE INDEX IF NOT EXISTS idx_connections_current_company ON connections(current_company);
CREATE INDEX IF NOT EXISTS idx_connections_location ON connections(location);
CREATE INDEX IF NOT EXISTS idx_connections_reconnect_score ON connections(reconnect_score);
CREATE INDEX IF NOT EXISTS idx_connections_last_message_date ON connections(last_message_date);
CREATE INDEX IF NOT EXISTS idx_connections_pre_score ON connections(pre_score);
CREATE INDEX IF NOT EXISTS idx_connections_import_batch_id ON connections(import_batch_id);
CREATE INDEX IF NOT EXISTS idx_connection_search ON connections(name, current_company, "current_role");
CREATE INDEX IF NOT EXISTS idx_connection_freshness ON connections(enriched_at, updated_at);

-- Outreach log
CREATE TABLE IF NOT EXISTS outreach_log (
    id SERIAL PRIMARY KEY,
    connection_id TEXT NOT NULL REFERENCES connections(id),
    channel TEXT NOT NULL,
    generated_prose TEXT,
    sent_at TIMESTAMPTZ,
    outcome TEXT,
    outcome_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_outreach_log_connection_id ON outreach_log(connection_id);

-- Outreach queue
CREATE TABLE IF NOT EXISTS outreach_queue (
    id SERIAL PRIMARY KEY,
    connection_id TEXT NOT NULL REFERENCES connections(id),
    channel TEXT NOT NULL,
    draft_message TEXT,
    draft_subject TEXT,
    status TEXT DEFAULT 'pending_review',
    priority_score REAL,
    skip_reason TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    reviewed_at TIMESTAMPTZ,
    sent_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_outreach_queue_connection_id ON outreach_queue(connection_id);
CREATE INDEX IF NOT EXISTS idx_outreach_queue_status ON outreach_queue(status);

-- Import batches
CREATE TABLE IF NOT EXISTS import_batches (
    id TEXT PRIMARY KEY,
    source_type TEXT NOT NULL,
    file_hash TEXT,
    total_rows INTEGER DEFAULT 0,
    imported_count INTEGER DEFAULT 0,
    updated_count INTEGER DEFAULT 0,
    skipped_count INTEGER DEFAULT 0,
    new_connection_ids JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

-- Gmail credentials (singleton table)
CREATE TABLE IF NOT EXISTS gmail_credentials (
    id INTEGER PRIMARY KEY DEFAULT 1,
    access_token TEXT,
    refresh_token TEXT,
    token_uri TEXT DEFAULT 'https://oauth2.googleapis.com/token',
    client_id TEXT,
    client_secret TEXT,
    scopes JSONB,
    expiry TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);

-- Sync metadata (singleton table)
CREATE TABLE IF NOT EXISTS sync_metadata (
    id INTEGER PRIMARY KEY DEFAULT 1,
    last_push_at TIMESTAMPTZ,
    last_pull_at TIMESTAMPTZ,
    last_push_connections INTEGER DEFAULT 0,
    last_push_queue_items INTEGER DEFAULT 0,
    last_pull_actions INTEGER DEFAULT 0,
    last_error TEXT,
    last_error_at TIMESTAMPTZ
);

-- Pipeline runs
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id TEXT PRIMARY KEY,
    run_type TEXT NOT NULL,
    status TEXT DEFAULT 'running',
    input_params JSONB,
    steps_completed JSONB,
    step_results JSONB,
    error_message TEXT,
    error_step TEXT,
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_pipeline_runs_status ON pipeline_runs(status);
