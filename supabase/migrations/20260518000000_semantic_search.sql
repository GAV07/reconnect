-- Semantic search: pgvector embeddings for natural-language people search
-- Enables queries like "fintech founder in NYC" or "ex-Google designer who posts about AI"

-- 1. Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA extensions;

-- 2. Add profile_text (human-readable search blob) and embedding column
ALTER TABLE connections
  ADD COLUMN IF NOT EXISTS profile_text text,
  ADD COLUMN IF NOT EXISTS profile_embedding vector(1536);

-- 3. HNSW index for fast cosine similarity search
CREATE INDEX IF NOT EXISTS idx_connections_embedding
  ON connections
  USING hnsw (profile_embedding vector_cosine_ops)
  WITH (m = 16, ef_construction = 64);

-- 4. Semantic search function called by edge function
CREATE OR REPLACE FUNCTION semantic_search(
  query_embedding vector(1536),
  match_limit int DEFAULT 20,
  similarity_threshold float DEFAULT 0.3
)
RETURNS TABLE (
  "id" text,
  "name" text,
  "current_role" text,
  "current_company" text,
  "enriched_industry" text,
  "enriched_city" text,
  "enriched_headline" text,
  "enriched_seniority" text,
  "enriched_school" text,
  "profile_text" text,
  "reconnect_score" double precision,
  "similarity" double precision
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  SELECT
    c.id,
    c.name,
    c.current_role,
    c.current_company,
    c.enriched_industry,
    c.enriched_city,
    c.enriched_headline,
    c.enriched_seniority,
    c.enriched_school,
    c.profile_text,
    c.reconnect_score,
    (1 - (c.profile_embedding <=> query_embedding))::double precision AS similarity
  FROM connections c
  WHERE c.profile_embedding IS NOT NULL
    AND (c.user_priority IS NULL OR c.user_priority != 'never')
    AND 1 - (c.profile_embedding <=> query_embedding) > similarity_threshold
  ORDER BY c.profile_embedding <=> query_embedding
  LIMIT match_limit;
END;
$$;
