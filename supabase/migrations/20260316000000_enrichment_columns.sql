-- Enrichment extracted columns (Phase 12: v1.3 Contact Discovery)
-- Promotes fields from raw_enrichment JSON into queryable first-class columns.
-- Applied alongside SQLite model changes in src/database/models.py.

ALTER TABLE connections ADD COLUMN IF NOT EXISTS enriched_industry TEXT;
ALTER TABLE connections ADD COLUMN IF NOT EXISTS enriched_headline TEXT;
ALTER TABLE connections ADD COLUMN IF NOT EXISTS enriched_city TEXT;
ALTER TABLE connections ADD COLUMN IF NOT EXISTS enriched_country TEXT;
ALTER TABLE connections ADD COLUMN IF NOT EXISTS enriched_school TEXT;
ALTER TABLE connections ADD COLUMN IF NOT EXISTS enriched_seniority TEXT;
ALTER TABLE connections ADD COLUMN IF NOT EXISTS education_text TEXT;

-- Indexes for Phase 13 browse filters (PostgREST eq/ilike performance)
CREATE INDEX IF NOT EXISTS idx_connections_enriched_industry ON connections(enriched_industry);
CREATE INDEX IF NOT EXISTS idx_connections_enriched_city ON connections(enriched_city);
CREATE INDEX IF NOT EXISTS idx_connections_enriched_country ON connections(enriched_country);
CREATE INDEX IF NOT EXISTS idx_connections_enriched_seniority ON connections(enriched_seniority);

-- NOTE: fts tsvector generated column is deferred to Phase 14 migration
