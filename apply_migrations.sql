-- Combined Migration Script for Whitelist Safety System
-- This script is idempotent - safe to run multiple times

BEGIN;

-- ============= FEATURE FLAGS TABLE =============
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

-- ============= UPDATED WHITELIST TABLE =============
-- Drop old whitelist table if structure is wrong
DROP TABLE IF EXISTS whitelist CASCADE;

-- Create new whitelist table with correct structure
CREATE TABLE IF NOT EXISTS whitelist (
    telegram_id BIGINT PRIMARY KEY,
    granted_at TIMESTAMPTZ DEFAULT NOW(),
    revoked_at TIMESTAMPTZ,
    source TEXT DEFAULT 'manual',
    note TEXT
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_whitelist_revoked ON whitelist(revoked_at);
CREATE INDEX IF NOT EXISTS idx_whitelist_source ON whitelist(source);
CREATE INDEX IF NOT EXISTS idx_whitelist_granted ON whitelist(granted_at);

-- Create view for whitelist summary
CREATE OR REPLACE VIEW v_whitelist_summary AS
SELECT 
    COUNT(*) FILTER (WHERE revoked_at IS NULL) as total_whitelisted,
    COUNT(*) FILTER (WHERE revoked_at IS NOT NULL) as revoked_count,
    COUNT(*) FILTER (WHERE revoked_at IS NULL AND EXISTS (
        SELECT 1 FROM subscriptions s 
        WHERE s.user_id = whitelist.telegram_id 
        AND s.status = 'active'
    )) as subs_active_whitelisted,
    COUNT(*) FILTER (WHERE revoked_at IS NULL AND EXISTS (
        SELECT 1 FROM subscriptions s 
        WHERE s.user_id = whitelist.telegram_id 
        AND s.status IN ('expired', 'grace')
    )) as subs_expired_whitelisted
FROM whitelist;

COMMIT;

-- Verification queries
SELECT 'Feature flags:' as info;
SELECT key, bool_value, created_at FROM feature_flags WHERE key = 'kick_enabled';

SELECT 'Whitelist summary:' as info;
SELECT * FROM v_whitelist_summary;