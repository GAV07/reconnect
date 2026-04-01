ALTER TABLE connections ADD COLUMN IF NOT EXISTS acquisition_role TEXT;
ALTER TABLE connections ADD COLUMN IF NOT EXISTS pipeline_stage TEXT;
ALTER TABLE connections ADD COLUMN IF NOT EXISTS pipeline_notes TEXT;
ALTER TABLE connections ADD COLUMN IF NOT EXISTS pipeline_updated_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_connections_acquisition_role ON connections(acquisition_role);
CREATE INDEX IF NOT EXISTS idx_connections_pipeline_stage ON connections(pipeline_stage);
CREATE INDEX IF NOT EXISTS idx_connections_in_pipeline
    ON connections(pipeline_stage, acquisition_role)
    WHERE pipeline_stage IS NOT NULL OR acquisition_role IS NOT NULL;
