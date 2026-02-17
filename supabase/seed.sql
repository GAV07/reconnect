-- Seed data for Reconnect CRM
-- This file runs after migrations during `supabase db reset`

-- Initialize singleton tables with default rows
INSERT INTO sync_metadata (id) VALUES (1) ON CONFLICT (id) DO NOTHING;

-- Note: user_profile and gmail_credentials are created by the app when needed
