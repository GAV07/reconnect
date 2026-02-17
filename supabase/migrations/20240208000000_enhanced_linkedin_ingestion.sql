-- Enhanced LinkedIn data ingestion tables and fields
-- Adds engagement signals, user content, and extended profile fields

-- Engagement signals table for tracking reactions, comments, endorsements
CREATE TABLE IF NOT EXISTS engagement_signals (
    id TEXT PRIMARY KEY,
    connection_id TEXT REFERENCES connections(id),
    connection_name TEXT NOT NULL,
    signal_type TEXT NOT NULL,  -- "reaction" | "comment" | "endorsement_given" | "endorsement_received" | "recommendation_given" | "recommendation_received"
    signal_strength INTEGER DEFAULT 1,  -- 1-5 scale
    content_snippet TEXT,
    signal_date TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_engagement_signals_connection ON engagement_signals(connection_id);
CREATE INDEX IF NOT EXISTS idx_engagement_signals_type ON engagement_signals(signal_type);

-- User content table for storing user's posts/shares
CREATE TABLE IF NOT EXISTS user_content (
    id TEXT PRIMARY KEY,
    content_type TEXT NOT NULL,  -- "post" | "article" | "share"
    content_text TEXT,
    topics JSONB,  -- LLM-extracted themes
    posted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_content_type ON user_content(content_type);
CREATE INDEX IF NOT EXISTS idx_user_content_posted ON user_content(posted_at);

-- Extend user_profile with persona fields
ALTER TABLE user_profile ADD COLUMN IF NOT EXISTS headline TEXT;
ALTER TABLE user_profile ADD COLUMN IF NOT EXISTS about_summary TEXT;
ALTER TABLE user_profile ADD COLUMN IF NOT EXISTS posting_themes JSONB;
ALTER TABLE user_profile ADD COLUMN IF NOT EXISTS public_persona_summary TEXT;

-- Extend connections with engagement metrics
ALTER TABLE connections ADD COLUMN IF NOT EXISTS engagement_score REAL;
ALTER TABLE connections ADD COLUMN IF NOT EXISTS last_engagement_date TIMESTAMPTZ;
ALTER TABLE connections ADD COLUMN IF NOT EXISTS engagement_direction TEXT;  -- "user_to_contact" | "contact_to_user" | "mutual"
ALTER TABLE connections ADD COLUMN IF NOT EXISTS endorsement_count INTEGER DEFAULT 0;
ALTER TABLE connections ADD COLUMN IF NOT EXISTS has_recommendation BOOLEAN DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS idx_connections_engagement ON connections(engagement_score);
CREATE INDEX IF NOT EXISTS idx_connections_engagement_date ON connections(last_engagement_date);
