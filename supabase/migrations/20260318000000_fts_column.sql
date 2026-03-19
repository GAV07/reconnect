-- Full-text search generated column (Phase 14: Search Bar)
-- Creates a tsvector column that automatically updates when source columns change.
-- Queried via PostgREST .textSearch('fts', query, {type:'plain', config:'english'})

ALTER TABLE connections
  ADD COLUMN IF NOT EXISTS fts tsvector
  GENERATED ALWAYS AS (
    to_tsvector('english',
      coalesce(name, '') || ' ' ||
      coalesce(current_role, '') || ' ' ||
      coalesce(current_company, '') || ' ' ||
      coalesce(enriched_city, '') || ' ' ||
      coalesce(enriched_school, '')
    )
  ) STORED;

CREATE INDEX IF NOT EXISTS idx_connections_fts ON connections USING GIN (fts);
