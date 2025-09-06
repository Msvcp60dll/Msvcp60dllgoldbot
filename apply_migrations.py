#!/usr/bin/env python3
"""Apply database migrations for whitelist safety system"""

import asyncio
import asyncpg
import os
from pathlib import Path
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
        # Read migration SQL
        migration_sql = Path('apply_migrations.sql').read_text()
        
        print("Applying migrations...")
        # Split by statement and execute
        statements = [s.strip() for s in migration_sql.split(';') if s.strip() and not s.strip().startswith('--')]
        
        for stmt in statements:
            if 'SELECT' in stmt.upper() and 'info' in stmt.lower():
                # Skip info statements
                continue
            try:
                await conn.execute(stmt)
                print(f"✓ Executed: {stmt[:50]}...")
            except Exception as e:
                if 'already exists' in str(e).lower() or 'duplicate' in str(e).lower():
                    print(f"  (Already exists, skipping)")
                else:
                    print(f"  Warning: {e}")
        
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
        return False
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(apply_migrations())