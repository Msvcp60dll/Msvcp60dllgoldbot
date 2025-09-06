#!/usr/bin/env python3
"""Verify that kicks are disabled"""

import asyncio
import asyncpg
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

async def verify_kicks_disabled():
    database_url = os.getenv('DATABASE_URL')
    conn = await asyncpg.connect(database_url)
    
    try:
        # Check feature flag
        result = await conn.fetchrow("""
            SELECT key, bool_value, created_at, updated_at 
            FROM feature_flags 
            WHERE key = 'kick_enabled'
        """)
        
        print("="*60)
        print("KICK SYSTEM STATUS VERIFICATION")
        print("="*60)
        print(f"Timestamp: {datetime.now().isoformat()}")
        print(f"\nFeature Flag: kick_enabled")
        
        if result:
            status = "🛡️ DISABLED (SAFE)" if not result['bool_value'] else "⚠️ ENABLED (DANGEROUS)"
            print(f"Value: {result['bool_value']}")
            print(f"Status: {status}")
            print(f"Created: {result['created_at']}")
            print(f"Updated: {result['updated_at']}")
            
            if not result['bool_value']:
                print("\n✅ CONFIRMATION: Kicks are DISABLED. No users can be kicked.")
            else:
                print("\n⚠️ WARNING: Kicks are ENABLED! Users may be kicked!")
        else:
            print("❌ ERROR: Feature flag 'kick_enabled' not found!")
            
        print("="*60)
        
        # Log this verification
        await conn.execute("""
            INSERT INTO funnel_events (user_id, event_type, metadata)
            VALUES (NULL, 'kick_status_verified', $1)
        """, {
            'kick_enabled': result['bool_value'] if result else None,
            'timestamp': datetime.now().isoformat(),
            'source': 'verify_kicks_status.py'
        })
        
        return result['bool_value'] if result else None
        
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(verify_kicks_disabled())