#!/usr/bin/env python3
"""Check whitelist summary and statistics"""

import asyncio
import asyncpg
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

async def check_summary():
    database_url = os.getenv('DATABASE_URL')
    conn = await asyncpg.connect(database_url)
    
    try:
        print("="*80)
        print("WHITELIST SUMMARY")
        print("="*80)
        print(f"Timestamp: {datetime.now().isoformat()}")
        
        # Get summary from view
        result = await conn.fetchrow("SELECT * FROM v_whitelist_summary")
        if result:
            print("\n📊 v_whitelist_summary:")
            print(f"  Total whitelisted: {result['total_whitelisted']}")
            print(f"  Revoked: {result['revoked_count']}")
            print(f"  Active subs whitelisted: {result['subs_active_whitelisted']}")
            print(f"  Expired subs whitelisted: {result['subs_expired_whitelisted']}")
        
        # Get direct counts
        total = await conn.fetchval("SELECT COUNT(*) FROM whitelist WHERE revoked_at IS NULL")
        print(f"\n✓ Direct count (not revoked): {total}")
        
        # Get sample entries
        print("\n📝 Sample whitelist entries (first 10):")
        rows = await conn.fetch("""
            SELECT telegram_id, source, granted_at, note
            FROM whitelist
            WHERE revoked_at IS NULL
            ORDER BY granted_at DESC
            LIMIT 10
        """)
        
        for i, row in enumerate(rows, 1):
            note_preview = row['note'][:50] + "..." if len(row['note']) > 50 else row['note']
            print(f"  {i}. ID:{row['telegram_id']} Source:{row['source']} Note:{note_preview}")
        
        # Check feature flag
        kick_flag = await conn.fetchrow("SELECT * FROM feature_flags WHERE key = 'kick_enabled'")
        print(f"\n🛡️ Kick Status: {'ENABLED ⚠️' if kick_flag['bool_value'] else 'DISABLED ✅'}")
        
        print("="*80)
        
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(check_summary())