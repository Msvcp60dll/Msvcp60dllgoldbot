-- Migration: Feature Flags Table for Safety Controls
-- Safe to run multiple times (idempotent)

BEGIN;

-- Create feature_flags table if not exists
CREATE TABLE IF NOT EXISTS feature_flags (
    key TEXT PRIMARY KEY,
    bool_value BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Add updated_at trigger if not exists
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger WHERE tgname = 'update_feature_flags_updated_at'
    ) THEN
        CREATE TRIGGER update_feature_flags_updated_at 
            BEFORE UPDATE ON feature_flags 
            FOR EACH ROW EXECUTE FUNCTION update_updated_at();
    END IF;
END $$;

-- Insert default kick_enabled=false if not exists
INSERT INTO feature_flags (key, bool_value) 
VALUES ('kick_enabled', FALSE)
ON CONFLICT (key) DO NOTHING;

-- Create index if not exists
CREATE INDEX IF NOT EXISTS idx_feature_flags_key ON feature_flags(key);

COMMIT;

-- Verification
SELECT key, bool_value, created_at FROM feature_flags WHERE key = 'kick_enabled';