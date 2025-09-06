-- Migration: Whitelist Table for Protected Members
-- Safe to run multiple times (idempotent)

BEGIN;

-- Create whitelist table if not exists
CREATE TABLE IF NOT EXISTS whitelist (
    telegram_id BIGINT PRIMARY KEY,
    granted_at TIMESTAMPTZ DEFAULT NOW(),
    revoked_at TIMESTAMPTZ,
    source TEXT DEFAULT 'manual',
    note TEXT
);

-- Add columns if missing (for existing installations)
DO $$ 
BEGIN
    -- Add source column if missing
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'whitelist' AND column_name = 'source'
    ) THEN
        ALTER TABLE whitelist ADD COLUMN source TEXT DEFAULT 'manual';
    END IF;
    
    -- Add note column if missing
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'whitelist' AND column_name = 'note'
    ) THEN
        ALTER TABLE whitelist ADD COLUMN note TEXT;
    END IF;
END $$;

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

-- Verification
SELECT * FROM v_whitelist_summary;