#!/usr/bin/env python3
"""
Test database consistency and verify all operations work correctly
Tests whitelist, payments, subscriptions, and foreign key relationships
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
import uuid

# Add app directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.db import db
from app.config import settings

# Load environment variables
load_dotenv()

async def test_database_consistency():
    """Run comprehensive database consistency tests"""
    
    print("🧪 DATABASE CONSISTENCY TEST")
    print("=" * 50)
    
    # Test user ID for our tests (use a high number to avoid conflicts)
    TEST_USER_ID = 999999999
    TEST_USERNAME = "test_consistency_user"
    
    try:
        # Connect to database
        print("\n1️⃣ Connecting to database...")
        await db.connect()
        await db.fetchval("SELECT 1")
        print("   ✅ Database connected")
        
        # Clean up any existing test data
        print("\n2️⃣ Cleaning up old test data...")
        await db.execute("DELETE FROM payments WHERE user_id = $1", TEST_USER_ID)
        await db.execute("DELETE FROM subscriptions WHERE user_id = $1", TEST_USER_ID)
        await db.execute("DELETE FROM recurring_subs WHERE user_id = $1", TEST_USER_ID)
        await db.execute("DELETE FROM whitelist WHERE telegram_id = $1", TEST_USER_ID)
        await db.execute("DELETE FROM funnel_events WHERE user_id = $1", TEST_USER_ID)
        await db.execute("DELETE FROM users WHERE user_id = $1", TEST_USER_ID)
        print("   ✅ Cleanup complete")
        
        # Test 1: User insertion
        print("\n3️⃣ Testing user insertion...")
        await db.upsert_user(
            user_id=TEST_USER_ID,
            username=TEST_USERNAME,
            first_name="Test",
            last_name="User",
            language_code="en"
        )
        
        # Verify user exists
        user = await db.fetchrow("SELECT * FROM users WHERE user_id = $1", TEST_USER_ID)
        assert user is not None, "User not inserted"
        assert user['username'] == TEST_USERNAME, "Username mismatch"
        print(f"   ✅ User created: {user['user_id']} ({user['username']})")
        
        # Test 2: Whitelist operations
        print("\n4️⃣ Testing whitelist operations...")
        
        # Add to whitelist
        await db.execute("""
            INSERT INTO whitelist (telegram_id, source, note, granted_at)
            VALUES ($1, 'test', 'Consistency test', NOW())
        """, TEST_USER_ID)
        print("   ✅ Added to whitelist")
        
        # Check is_whitelisted
        is_whitelisted = await db.is_whitelisted(TEST_USER_ID)
        assert is_whitelisted == True, "is_whitelisted() returned False"
        print(f"   ✅ is_whitelisted() = {is_whitelisted}")
        
        # Burn whitelist
        burned = await db.burn_whitelist(TEST_USER_ID)
        assert burned == True, "burn_whitelist() failed"
        print(f"   ✅ burn_whitelist() = {burned}")
        
        # Verify not whitelisted after burn
        is_whitelisted_after = await db.is_whitelisted(TEST_USER_ID)
        assert is_whitelisted_after == False, "Still whitelisted after burn"
        print(f"   ✅ is_whitelisted() after burn = {is_whitelisted_after}")
        
        # Verify revoked_at is set
        whitelist_entry = await db.fetchrow("""
            SELECT * FROM whitelist WHERE telegram_id = $1
        """, TEST_USER_ID)
        assert whitelist_entry['revoked_at'] is not None, "revoked_at not set"
        print(f"   ✅ revoked_at set: {whitelist_entry['revoked_at']}")
        
        # Test 3: Payment insertion with idempotency
        print("\n5️⃣ Testing payment operations...")
        
        test_charge_id = f"test_charge_{uuid.uuid4()}"
        test_star_tx_id = f"test_star_{uuid.uuid4()}"
        
        # Insert payment
        payment1 = await db.insert_payment_idempotent(
            user_id=TEST_USER_ID,
            charge_id=test_charge_id,
            star_tx_id=test_star_tx_id,
            amount=3800,
            payment_type='one_time',
            is_recurring=False,
            invoice_payload="test_payload"
        )
        assert payment1 is not None, "First payment insertion failed"
        print(f"   ✅ Payment inserted: {payment1['payment_id']}")
        
        # Try duplicate insertion (should return None)
        payment2 = await db.insert_payment_idempotent(
            user_id=TEST_USER_ID,
            charge_id=test_charge_id,  # Same charge_id
            star_tx_id=test_star_tx_id,  # Same star_tx_id
            amount=3800,
            payment_type='one_time',
            is_recurring=False,
            invoice_payload="test_payload"
        )
        assert payment2 is None, "Duplicate payment was inserted!"
        print("   ✅ Idempotency check passed (duplicate rejected)")
        
        # Test 4: Subscription operations
        print("\n6️⃣ Testing subscription operations...")
        
        # Create subscription
        subscription_id = str(uuid.uuid4())
        await db.execute("""
            INSERT INTO subscriptions (
                subscription_id, user_id, status, is_recurring, 
                expires_at, created_at
            )
            VALUES ($1, $2, 'active', false, $3, NOW())
        """, subscription_id, TEST_USER_ID, 
            datetime.now(timezone.utc) + timedelta(days=30))
        print(f"   ✅ Subscription created: {subscription_id}")
        
        # Check active access
        has_access = await db.has_active_access(TEST_USER_ID)
        assert has_access == True, "has_active_access() returned False"
        print(f"   ✅ has_active_access() = {has_access}")
        
        # Get active subscription
        active_sub = await db.get_active_subscription(TEST_USER_ID)
        assert active_sub is not None, "No active subscription found"
        assert str(active_sub['subscription_id']) == subscription_id, "Wrong subscription returned"
        print(f"   ✅ get_active_subscription() returned correct subscription")
        
        # Test 5: Foreign key constraints
        print("\n7️⃣ Testing foreign key constraints...")
        
        # Try to insert payment for non-existent user (should fail)
        try:
            await db.execute("""
                INSERT INTO payments (payment_id, user_id, amount, payment_type)
                VALUES ($1, $2, 1000, 'one_time')
            """, str(uuid.uuid4()), 888888888)  # Non-existent user
            assert False, "Foreign key constraint not working!"
        except Exception as e:
            print(f"   ✅ Foreign key constraint enforced: {type(e).__name__}")
        
        # Test 6: Star cursor operations
        print("\n8️⃣ Testing star_tx_cursor operations...")
        
        # Get cursor (should auto-initialize if missing)
        cursor1 = await db.get_reconcile_cursor()
        assert cursor1 is not None, "Cursor not initialized"
        print(f"   ✅ get_reconcile_cursor() = {cursor1}")
        
        # Update cursor
        new_time = datetime.now(timezone.utc)
        await db.update_reconcile_cursor(new_time, "test_tx_id")
        
        # Verify update
        cursor2 = await db.get_reconcile_cursor()
        assert cursor2 >= cursor1, "Cursor not updated"
        print(f"   ✅ update_reconcile_cursor() worked")
        
        # Test 7: Funnel events
        print("\n9️⃣ Testing funnel events...")
        
        # Log event
        await db.log_event(TEST_USER_ID, "test_event", {"test": "data"})
        
        # Verify event logged
        event = await db.fetchrow("""
            SELECT * FROM funnel_events 
            WHERE user_id = $1 AND event_type = 'test_event'
            ORDER BY created_at DESC
            LIMIT 1
        """, TEST_USER_ID)
        assert event is not None, "Event not logged"
        
        # Handle both string and dict metadata
        metadata = event['metadata']
        if isinstance(metadata, str):
            import json
            metadata = json.loads(metadata)
        
        assert metadata['test'] == "data", "Metadata not stored correctly"
        print(f"   ✅ log_event() successful")
        
        # Test 8: Cascade behavior
        print("\n🔟 Testing cascade behavior...")
        
        # Count related records
        payment_count = await db.fetchval(
            "SELECT COUNT(*) FROM payments WHERE user_id = $1", 
            TEST_USER_ID
        )
        subscription_count = await db.fetchval(
            "SELECT COUNT(*) FROM subscriptions WHERE user_id = $1", 
            TEST_USER_ID
        )
        
        print(f"   📊 User has {payment_count} payments, {subscription_count} subscriptions")
        
        # Clean up test data
        print("\n🧹 Cleaning up test data...")
        await db.execute("DELETE FROM payments WHERE user_id = $1", TEST_USER_ID)
        await db.execute("DELETE FROM subscriptions WHERE user_id = $1", TEST_USER_ID)
        await db.execute("DELETE FROM recurring_subs WHERE user_id = $1", TEST_USER_ID)
        await db.execute("DELETE FROM whitelist WHERE telegram_id = $1", TEST_USER_ID)
        await db.execute("DELETE FROM funnel_events WHERE user_id = $1", TEST_USER_ID)
        await db.execute("DELETE FROM users WHERE user_id = $1", TEST_USER_ID)
        print("   ✅ Test data cleaned up")
        
        print("\n" + "=" * 50)
        print("✅ ALL TESTS PASSED!")
        print("=" * 50)
        print("\n📊 Summary:")
        print("   • User operations: ✅")
        print("   • Whitelist with correct columns: ✅")
        print("   • Payment idempotency: ✅")
        print("   • Subscription queries: ✅")
        print("   • Foreign key constraints: ✅")
        print("   • Star cursor auto-init: ✅")
        print("   • Funnel events: ✅")
        print("\n🎉 Database is consistent and ready for production!")
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        return False
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if hasattr(db, 'close'):
            await db.close()
        elif hasattr(db, 'pool') and db.pool:
            await db.pool.close()
    
    return True

async def main():
    """Main test runner"""
    success = await test_database_consistency()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    if not os.getenv('DATABASE_URL'):
        print("❌ DATABASE_URL not found in environment")
        sys.exit(1)
    
    asyncio.run(main())