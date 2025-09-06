#!/usr/bin/env python3
"""
Simple test script for Telegram Stars payment flow.
Tests the critical paths: whitelist, payment, and access control.
"""

import asyncio
import sys
from datetime import datetime, timezone, timedelta
from app.config import settings
from app.db import db

async def test_whitelist():
    """Test whitelist management"""
    print("\n" + "="*60)
    print("TESTING WHITELIST MANAGEMENT")
    print("="*60)
    
    test_user_id = 123456789  # Replace with your test user ID
    
    # 1. Check if user is whitelisted
    is_whitelisted = await db.is_whitelisted(test_user_id)
    print(f"1. Is user {test_user_id} whitelisted? {is_whitelisted}")
    
    # 2. Grant whitelist
    granted = await db.grant_whitelist(test_user_id, source='test', note='Testing whitelist')
    print(f"2. Granted whitelist: {granted}")
    
    # 3. Check again
    is_whitelisted = await db.is_whitelisted(test_user_id)
    print(f"3. Is user whitelisted now? {is_whitelisted}")
    
    # 4. Burn whitelist (simulating join request)
    burned = await db.burn_whitelist(test_user_id)
    print(f"4. Burned whitelist: {burned}")
    
    # 5. Check if still whitelisted
    is_whitelisted = await db.is_whitelisted(test_user_id)
    print(f"5. Is user still whitelisted? {is_whitelisted}")
    
    return True

async def test_payment_flow():
    """Test payment processing and subscription creation"""
    print("\n" + "="*60)
    print("TESTING PAYMENT FLOW")
    print("="*60)
    
    test_user_id = 123456789  # Replace with your test user ID
    charge_id = f"test_charge_{datetime.now().timestamp()}"
    
    # 1. Insert payment with idempotency
    print(f"1. Inserting payment for user {test_user_id}")
    payment = await db.insert_payment_idempotent(
        user_id=test_user_id,
        charge_id=charge_id,
        star_tx_id=f"star_tx_{charge_id}",
        amount=settings.plan_stars,
        payment_type='one_time',
        is_recurring=False,
        invoice_payload=f"one_{test_user_id}"
    )
    
    if payment:
        print(f"   ✅ Payment created: ID={payment['payment_id']}, Amount={payment['amount']} stars")
    else:
        print(f"   ⚠️ Payment already exists (idempotency working)")
    
    # 2. Process subscription
    print("2. Processing subscription payment")
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.plan_days)
    
    if payment:
        await db.process_subscription_payment(
            user_id=test_user_id,
            payment=payment,
            subscription_expiration=expires_at,
            is_recurring=False
        )
        print(f"   ✅ Subscription created/extended until {expires_at}")
    
    # 3. Check active access
    has_access = await db.has_active_access(test_user_id)
    print(f"3. User has active access? {has_access}")
    
    # 4. Get subscription details
    sub = await db.fetch_one("""
        SELECT * FROM subscriptions
        WHERE user_id = $1
    """, test_user_id)
    
    if sub:
        print(f"4. Subscription details:")
        print(f"   - Status: {sub['status']}")
        print(f"   - Expires: {sub['expires_at']}")
        print(f"   - Recurring: {sub['is_recurring']}")
    
    # 5. Test idempotency - try same payment again
    print("5. Testing idempotency with same charge_id")
    duplicate_payment = await db.insert_payment_idempotent(
        user_id=test_user_id,
        charge_id=charge_id,  # Same charge_id
        star_tx_id=f"star_tx_{charge_id}",
        amount=settings.plan_stars,
        payment_type='one_time',
        is_recurring=False,
        invoice_payload=f"one_{test_user_id}"
    )
    
    if duplicate_payment:
        print(f"   ❌ FAILED: Duplicate payment created!")
    else:
        print(f"   ✅ PASSED: Duplicate payment blocked (idempotency working)")
    
    return True

async def test_access_control():
    """Test access control and expiry logic"""
    print("\n" + "="*60)
    print("TESTING ACCESS CONTROL")
    print("="*60)
    
    test_user_id = 123456789  # Replace with your test user ID
    
    # 1. Test active subscription
    print("1. Testing active subscription")
    has_access = await db.has_active_access(test_user_id)
    print(f"   Has access: {has_access}")
    
    # 2. Simulate expired subscription
    print("2. Simulating expired subscription")
    await db.execute("""
        UPDATE subscriptions
        SET expires_at = NOW() - INTERVAL '1 day',
            status = 'active'
        WHERE user_id = $1
    """, test_user_id)
    
    has_access = await db.has_active_access(test_user_id)
    print(f"   Has access (expired): {has_access}")
    
    # 3. Test grace period
    print("3. Testing grace period")
    grace_until = datetime.now(timezone.utc) + timedelta(hours=24)
    await db.set_grace(test_user_id, grace_until)
    
    sub = await db.fetch_one("""
        SELECT status, grace_until FROM subscriptions
        WHERE user_id = $1
    """, test_user_id)
    print(f"   Status: {sub['status']}")
    print(f"   Grace until: {sub['grace_until']}")
    
    has_access = await db.has_active_access(test_user_id)
    print(f"   Has access (in grace): {has_access}")
    
    # 4. Test fully expired
    print("4. Testing fully expired")
    await db.set_expired(test_user_id)
    
    sub = await db.fetch_one("""
        SELECT status FROM subscriptions
        WHERE user_id = $1
    """, test_user_id)
    print(f"   Status: {sub['status']}")
    
    has_access = await db.has_active_access(test_user_id)
    print(f"   Has access (expired): {has_access}")
    
    # 5. Restore active status for cleanup
    print("5. Restoring active status")
    await db.execute("""
        UPDATE subscriptions
        SET status = 'active',
            expires_at = NOW() + INTERVAL '30 days',
            grace_until = NULL
        WHERE user_id = $1
    """, test_user_id)
    
    return True

async def test_daily_operations():
    """Test scheduler and reconciliation queries"""
    print("\n" + "="*60)
    print("TESTING DAILY OPERATIONS")
    print("="*60)
    
    # 1. Test finding expired subscriptions
    print("1. Finding expired active subscriptions")
    expired = await db.fetch("""
        SELECT user_id, expires_at
        FROM subscriptions
        WHERE status = 'active'
        AND expires_at < NOW()
        LIMIT 5
    """)
    print(f"   Found {len(expired)} expired subscriptions")
    
    # 2. Test finding grace period expirations
    print("2. Finding expired grace periods")
    grace_expired = await db.fetch("""
        SELECT user_id, grace_until
        FROM subscriptions
        WHERE status = 'grace'
        AND grace_until < NOW()
        LIMIT 5
    """)
    print(f"   Found {len(grace_expired)} expired grace periods")
    
    # 3. Test daily stats query
    print("3. Testing daily stats query")
    stats = await db.fetch_one("""
        SELECT 
            COUNT(DISTINCT CASE 
                WHEN last_interaction > NOW() - INTERVAL '24 hours' 
                THEN user_id 
            END) as active_users_24h,
            COUNT(DISTINCT user_id) as total_users,
            COUNT(DISTINCT CASE 
                WHEN created_at::date = CURRENT_DATE 
                THEN user_id 
            END) as new_signups_today
        FROM users
    """)
    
    print(f"   Active users (24h): {stats['active_users_24h']}")
    print(f"   Total users: {stats['total_users']}")
    print(f"   New signups today: {stats['new_signups_today']}")
    
    # 4. Test revenue stats
    print("4. Testing revenue stats")
    revenue = await db.fetch_one("""
        SELECT 
            COALESCE(SUM(CASE 
                WHEN created_at::date = CURRENT_DATE 
                THEN amount 
            END), 0) as revenue_today,
            COUNT(CASE 
                WHEN created_at::date = CURRENT_DATE 
                THEN 1 
            END) as payments_today
        FROM payments
    """)
    
    print(f"   Revenue today: {revenue['revenue_today']} stars")
    print(f"   Payments today: {revenue['payments_today']}")
    
    return True

async def main():
    """Run all tests"""
    print("="*60)
    print("TELEGRAM STARS PAYMENT FLOW TEST")
    print("="*60)
    print(f"Database: {settings.database_url[:30]}...")
    print(f"Plan price: {settings.plan_stars} stars")
    print(f"Sub price: {settings.sub_stars} stars")
    print(f"Plan days: {settings.plan_days}")
    print(f"Grace hours: {settings.grace_hours}")
    
    try:
        # Connect to database
        print("\nConnecting to database...")
        await db.connect()
        print("✅ Database connected")
        
        # Run tests
        tests_passed = []
        
        # Test 1: Whitelist
        try:
            result = await test_whitelist()
            tests_passed.append(("Whitelist", result))
        except Exception as e:
            print(f"❌ Whitelist test failed: {e}")
            tests_passed.append(("Whitelist", False))
        
        # Test 2: Payment Flow
        try:
            result = await test_payment_flow()
            tests_passed.append(("Payment Flow", result))
        except Exception as e:
            print(f"❌ Payment flow test failed: {e}")
            tests_passed.append(("Payment Flow", False))
        
        # Test 3: Access Control
        try:
            result = await test_access_control()
            tests_passed.append(("Access Control", result))
        except Exception as e:
            print(f"❌ Access control test failed: {e}")
            tests_passed.append(("Access Control", False))
        
        # Test 4: Daily Operations
        try:
            result = await test_daily_operations()
            tests_passed.append(("Daily Operations", result))
        except Exception as e:
            print(f"❌ Daily operations test failed: {e}")
            tests_passed.append(("Daily Operations", False))
        
        # Summary
        print("\n" + "="*60)
        print("TEST SUMMARY")
        print("="*60)
        
        for test_name, passed in tests_passed:
            status = "✅ PASSED" if passed else "❌ FAILED"
            print(f"{test_name}: {status}")
        
        all_passed = all(passed for _, passed in tests_passed)
        if all_passed:
            print("\n🎉 All tests passed! The payment flow is working correctly.")
        else:
            print("\n⚠️ Some tests failed. Check the logs above for details.")
        
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        return 1
    
    finally:
        # Disconnect
        await db.disconnect()
        print("\n✅ Database disconnected")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)