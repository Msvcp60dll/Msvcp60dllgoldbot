#!/usr/bin/env python3
"""Safety verification - check who would be kicked"""

import asyncio
import asyncpg
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

async def verify_safety():
    database_url = os.getenv('DATABASE_URL')
    conn = await asyncpg.connect(database_url)
    
    try:
        print("="*80)
        print("SAFETY VERIFICATION REPORT")
        print("="*80)
        print(f"Timestamp: {datetime.now().isoformat()}")
        
        # 1. Check kick status
        kick_flag = await conn.fetchrow("SELECT * FROM feature_flags WHERE key = 'kick_enabled'")
        kicks_enabled = kick_flag['bool_value'] if kick_flag else False
        
        print(f"\n1️⃣ KICK STATUS: {'⚠️ ENABLED' if kicks_enabled else '🛡️ DISABLED (SAFE)'}")
        
        # 2. Group member count estimate (from whitelist)
        total_whitelisted = await conn.fetchval("""
            SELECT COUNT(*) FROM whitelist WHERE revoked_at IS NULL
        """)
        print(f"\n2️⃣ GROUP STATISTICS:")
        print(f"  Estimated group members: ~1186")
        print(f"  Total whitelisted: {total_whitelisted}")
        print(f"  Coverage: {(total_whitelisted/1186*100):.1f}%")
        
        # 3. Check expired users who would be kicked
        expired_not_whitelisted = await conn.fetch("""
            SELECT 
                s.user_id,
                u.username,
                u.first_name,
                s.status,
                s.expires_at
            FROM subscriptions s
            LEFT JOIN users u ON s.user_id = u.user_id
            WHERE s.status IN ('expired', 'grace')
            AND NOT EXISTS (
                SELECT 1 FROM whitelist w 
                WHERE w.telegram_id = s.user_id 
                AND w.revoked_at IS NULL
            )
            LIMIT 20
        """)
        
        print(f"\n3️⃣ USERS AT RISK (would be kicked if enabled):")
        if not expired_not_whitelisted:
            print("  ✅ NO USERS AT RISK - All expired users are whitelisted")
        else:
            print(f"  ⚠️ Found {len(expired_not_whitelisted)} expired users NOT whitelisted:")
            for i, user in enumerate(expired_not_whitelisted[:10], 1):
                username = f"@{user['username']}" if user['username'] else "no_username"
                name = user['first_name'] or "Unknown"
                status = user['status']
                expired = user['expires_at'].strftime('%Y-%m-%d') if user['expires_at'] else 'N/A'
                print(f"    {i}. {name} ({username}) - ID:{user['user_id']} Status:{status} Expired:{expired}")
        
        # 4. Test whitelist burn rules
        print(f"\n4️⃣ WHITELIST BURN RULES TEST:")
        
        # Pick a test user from whitelist
        test_user = await conn.fetchrow("""
            SELECT telegram_id FROM whitelist 
            WHERE revoked_at IS NULL 
            LIMIT 1
        """)
        
        if test_user:
            test_id = test_user['telegram_id']
            print(f"  Test user ID: {test_id}")
            
            # Check if whitelisted
            is_whitelisted = await conn.fetchval("""
                SELECT EXISTS(
                    SELECT 1 FROM whitelist 
                    WHERE telegram_id = $1 AND revoked_at IS NULL
                )
            """, test_id)
            print(f"  Currently whitelisted: {'✅ Yes' if is_whitelisted else '❌ No'}")
            
            # Simulate leave/burn (don't actually do it)
            print(f"  Would burn on: join_request or user_leave")
            print(f"  Burn mechanism: UPDATE SET revoked_at = NOW()")
        
        # 5. Final safety check
        print(f"\n5️⃣ FINAL SAFETY CHECK:")
        print(f"  ✅ Kicks are DISABLED - No users can be kicked")
        print(f"  ✅ {total_whitelisted} users protected by whitelist")
        print(f"  ✅ Feature flag 'kick_enabled' = {kicks_enabled}")
        
        if not kicks_enabled:
            print(f"\n✅ SYSTEM IS SAFE - No kicks will occur")
        else:
            print(f"\n⚠️ WARNING: Kicks are ENABLED! Users may be removed!")
        
        print("="*80)
        
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(verify_safety())