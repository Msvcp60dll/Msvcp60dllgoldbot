#!/usr/bin/env python3
"""Apply database migrations for whitelist safety system"""

import asyncio
import asyncpg
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

async def apply_migrations():
    """Apply all migrations"""
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("ERROR: DATABASE_URL not found")
        return False
    
    print("Connecting to database...")
    conn = await asyncpg.connect(database_url)
    
    try:
        print("Applying migrations...")
        
        # Execute the entire migration as a transaction
        migration_sql = """
-- Combined Migration Script for Whitelist Safety System
BEGIN;

-- ============= FEATURE FLAGS TABLE =============
CREATE TABLE IF NOT EXISTS feature_flags (
    key TEXT PRIMARY KEY,
    bool_value BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

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

COMMIT;
        """
        
        await conn.execute(migration_sql)
        print("✓ Migration transaction completed")
        
        # Create the view separately (can't be in transaction with DROP TABLE)
        view_sql = """
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
        """
        
        await conn.execute(view_sql)
        print("✓ Whitelist summary view created")
        
        print("\n=== Verification ===")
        
        # Check feature flag
        result = await conn.fetchrow("SELECT * FROM feature_flags WHERE key = 'kick_enabled'")
        if result:
            print(f"✓ Feature flag 'kick_enabled': {result['bool_value']} (created: {result['created_at']})")
        else:
            print("✗ Feature flag not found!")
            
        # Check whitelist summary
        result = await conn.fetchrow("SELECT * FROM v_whitelist_summary")
        if result:
            print(f"✓ Whitelist summary view:")
            print(f"  - Total whitelisted: {result['total_whitelisted']}")
            print(f"  - Revoked: {result['revoked_count']}")
            print(f"  - Active subs whitelisted: {result['subs_active_whitelisted']}")
            print(f"  - Expired subs whitelisted: {result['subs_expired_whitelisted']}")
        
        print("\n✅ Migrations applied successfully!")
        return True
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(apply_migrations())