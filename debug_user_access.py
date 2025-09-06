#!/usr/bin/env python3
"""Debug user access for user 306145881"""

import asyncio
import os
import sys
from datetime import datetime, timezone

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def debug_user_access():
    """Debug user access issue"""
    
    # Import after adding to path
    from app.config import settings
    
    # Import database module
    try:
        from app.db import db
    except ImportError as e:
        print(f"Failed to import db: {e}")
        return
    
    user_id = 306145881
    print(f"=== DEBUGGING USER ACCESS FOR {user_id} ===\n")
    
    try:
        # Connect to database
        await db.connect()
        print("✅ Database connected")
        
        # Check raw subscriptions data
        print("\n--- RAW SUBSCRIPTIONS DATA ---")
        subs_query = """
            SELECT id, user_id, status, created_at, expires_at, grace_until, is_recurring
            FROM subscriptions 
            WHERE user_id = $1
            ORDER BY created_at DESC
        """
        subscriptions = await db.fetch(subs_query, user_id)
        
        if subscriptions:
            print(f"Found {len(subscriptions)} subscription records:")
            for i, sub in enumerate(subscriptions, 1):
                print(f"  {i}. ID: {sub['id']}")
                print(f"     Status: {sub['status']}")
                print(f"     Created: {sub['created_at']}")
                print(f"     Expires: {sub['expires_at']}")
                print(f"     Grace Until: {sub['grace_until']}")
                print(f"     Is Recurring: {sub['is_recurring']}")
                print()
        else:
            print("❌ No subscriptions found")
        
        # Check raw payments data
        print("\n--- RAW PAYMENTS DATA ---")
        payments_query = """
            SELECT id, user_id, charge_id, amount, status, payment_type, is_recurring, created_at
            FROM payments 
            WHERE user_id = $1
            ORDER BY created_at DESC
            LIMIT 5
        """
        payments = await db.fetch(payments_query, user_id)
        
        if payments:
            print(f"Found {len(payments)} payment records (last 5):")
            for i, payment in enumerate(payments, 1):
                print(f"  {i}. ID: {payment['id']}")
                print(f"     Charge ID: {payment['charge_id']}")
                print(f"     Amount: {payment['amount']}")
                print(f"     Status: {payment['status']}")
                print(f"     Type: {payment['payment_type']}")
                print(f"     Is Recurring: {payment['is_recurring']}")
                print(f"     Created: {payment['created_at']}")
                print()
        else:
            print("❌ No payments found")
        
        # Test access functions
        print("\n--- TESTING ACCESS FUNCTIONS ---")
        
        # Test has_active_access
        has_access = await db.has_active_access(user_id)
        print(f"has_active_access(): {has_access}")
        
        # Test get_active_subscription
        active_sub = await db.get_active_subscription(user_id)
        if active_sub:
            print(f"get_active_subscription(): Found subscription")
            print(f"  Status: {active_sub['status']}")
            print(f"  Expires: {active_sub.get('expires_at')}")
            print(f"  Grace Until: {active_sub.get('grace_until')}")
        else:
            print(f"get_active_subscription(): No active subscription")
        
        # Manual check with current timestamp
        print(f"\n--- MANUAL TIME CHECK ---")
        current_time = datetime.now(timezone.utc)
        print(f"Current time: {current_time}")
        
        # Check if any subscription is valid right now
        manual_check_query = """
            SELECT id, status, expires_at, grace_until,
                   (expires_at > NOW()) as expires_valid,
                   (grace_until > NOW()) as grace_valid,
                   (expires_at > NOW() OR grace_until > NOW()) as has_access
            FROM subscriptions
            WHERE user_id = $1 
                AND status IN ('active', 'grace')
        """
        manual_results = await db.fetch(manual_check_query, user_id)
        
        if manual_results:
            print("Manual access check results:")
            for result in manual_results:
                print(f"  Subscription {result['id']}:")
                print(f"    Status: {result['status']}")
                print(f"    Expires: {result['expires_at']}")
                print(f"    Grace Until: {result['grace_until']}")
                print(f"    Expires Valid: {result['expires_valid']}")
                print(f"    Grace Valid: {result['grace_valid']}")
                print(f"    Has Access: {result['has_access']}")
        else:
            print("No active/grace subscriptions found")
        
        # Check if user exists in users table
        print(f"\n--- USER TABLE CHECK ---")
        user_exists = await db.fetchrow("SELECT * FROM users WHERE telegram_id = $1", user_id)
        if user_exists:
            print(f"✅ User exists in users table:")
            print(f"  Username: {user_exists.get('username')}")
            print(f"  First Name: {user_exists.get('first_name')}")
            print(f"  Created: {user_exists.get('created_at')}")
        else:
            print("❌ User not found in users table")
        
        await db.disconnect()
        print("\n✅ Database disconnected")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        try:
            await db.disconnect()
        except:
            pass

if __name__ == "__main__":
    asyncio.run(debug_user_access())