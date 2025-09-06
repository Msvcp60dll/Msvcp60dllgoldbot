#!/usr/bin/env python3
"""Test the payment SQL fix by simulating the payment flow"""

import asyncio
import sys
import os
from datetime import datetime, timezone, timedelta

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def test_payment_flow():
    """Test that payment processing now works with fixed SQL"""
    
    # Import after path setup 
    from app.config import settings
    from app.db import db
    
    test_user_id = 999999999  # Test user
    
    try:
        await db.connect()
        print("✅ Connected to database")
        
        # Clean up any existing test data
        await db.execute("DELETE FROM subscriptions WHERE user_id = $1", test_user_id)
        await db.execute("DELETE FROM payments WHERE user_id = $1", test_user_id)
        await db.execute("DELETE FROM users WHERE telegram_id = $1", test_user_id)
        print("🧹 Cleaned up test data")
        
        # Test 1: Create user
        await db.upsert_user(
            user_id=test_user_id,
            username="testuser",
            first_name="Test",
            last_name="User",
            language_code="en"
        )
        print("✅ Test user created")
        
        # Test 2: Create payment record
        payment = await db.insert_payment_idempotent(
            user_id=test_user_id,
            charge_id="test_charge_123",
            star_tx_id="test_tx_456",
            amount=30,
            payment_type='one_time',
            is_recurring=False,
            invoice_payload="test_payment"
        )
        print(f"✅ Payment created: {payment['payment_id']}")
        
        # Test 3: Process subscription (this is where the SQL error was)
        print("🔥 Testing process_subscription_payment with fixed SQL...")
        await db.process_subscription_payment(
            user_id=test_user_id,
            payment=payment,
            subscription_expiration=None,  # Will use default 30 days
            is_recurring=False
        )
        print("✅ Subscription processed successfully!")
        
        # Test 4: Check access
        has_access = await db.has_active_access(test_user_id)
        print(f"✅ User has access: {has_access}")
        
        # Test 5: Get subscription details
        subscription = await db.get_active_subscription(test_user_id)
        if subscription:
            print(f"✅ Active subscription found:")
            print(f"   Status: {subscription['status']}")
            print(f"   Expires: {subscription['expires_at']}")
            print(f"   Is Recurring: {subscription['is_recurring']}")
        else:
            print("❌ No active subscription found")
        
        # Verify the fix worked
        if has_access and subscription and subscription['status'] == 'active':
            print("\n🎉 SUCCESS: Payment flow is working correctly!")
            print("   - Payment processed ✅")
            print("   - Subscription created ✅") 
            print("   - User has access ✅")
        else:
            print("\n❌ FAILED: Something is still broken")
            return False
            
        # Cleanup
        await db.execute("DELETE FROM subscriptions WHERE user_id = $1", test_user_id)
        await db.execute("DELETE FROM payments WHERE user_id = $1", test_user_id) 
        await db.execute("DELETE FROM users WHERE telegram_id = $1", test_user_id)
        print("🧹 Test cleanup completed")
        
        await db.disconnect()
        return True
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        try:
            await db.disconnect()
        except:
            pass
        return False

if __name__ == "__main__":
    success = asyncio.run(test_payment_flow())
    print(f"\n{'🎉 PAYMENT FLOW TEST PASSED' if success else '❌ PAYMENT FLOW TEST FAILED'}")
    sys.exit(0 if success else 1)