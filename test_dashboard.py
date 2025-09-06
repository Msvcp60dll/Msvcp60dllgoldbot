#!/usr/bin/env python3
"""
Test script for enhanced dashboard functionality
Creates test data with various subscription states
"""

import asyncio
import os
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
import asyncpg
from typing import List, Dict, Any

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL')

async def create_test_data():
    """Create test data with various subscription states"""
    
    conn = await asyncpg.connect(DATABASE_URL)
    
    try:
        print("🔧 Creating test data for dashboard...")
        
        # Current time
        now = datetime.now(timezone.utc)
        
        # Test users data
        test_users = [
            # Active subscriptions
            {"user_id": 100001, "username": "active_user_1", "first_name": "Alice", "status": "active", 
             "expires_at": now + timedelta(days=15), "is_recurring": True},
            {"user_id": 100002, "username": "active_user_2", "first_name": "Bob", "status": "active",
             "expires_at": now + timedelta(days=7), "is_recurring": False},
            
            # Expiring soon (within 3 days)
            {"user_id": 100003, "username": "expiring_soon_1", "first_name": "Charlie", "status": "active",
             "expires_at": now + timedelta(hours=48), "is_recurring": True},
            {"user_id": 100004, "username": "expiring_soon_2", "first_name": "Diana", "status": "active",
             "expires_at": now + timedelta(hours=12), "is_recurring": False},
            
            # Grace period members
            {"user_id": 100005, "username": "grace_user_1", "first_name": "Eve", "status": "grace",
             "expires_at": now - timedelta(hours=24), "is_recurring": True},
            {"user_id": 100006, "username": "grace_user_2", "first_name": "Frank", "status": "grace",
             "expires_at": now - timedelta(hours=36), "is_recurring": False},
            
            # Overdue but not kicked (WARNING: < 3 days)
            {"user_id": 100007, "username": "overdue_warning_1", "first_name": "Grace", "status": "expired",
             "expires_at": now - timedelta(days=2), "is_recurring": False},
            {"user_id": 100008, "username": "overdue_warning_2", "first_name": "Henry", "status": "expired",
             "expires_at": now - timedelta(days=1.5), "is_recurring": True},
            
            # Overdue but not kicked (CRITICAL: > 3 days)
            {"user_id": 100009, "username": "overdue_critical_1", "first_name": "Iris", "status": "expired",
             "expires_at": now - timedelta(days=5), "is_recurring": False},
            {"user_id": 100010, "username": "overdue_critical_2", "first_name": "Jack", "status": "expired",
             "expires_at": now - timedelta(days=7), "is_recurring": True},
            
            # Properly banned
            {"user_id": 100011, "username": "banned_user", "first_name": "Kate", "status": "banned",
             "expires_at": now - timedelta(days=10), "is_recurring": False},
        ]
        
        # Insert test users
        print("📝 Inserting test users...")
        for user in test_users:
            await conn.execute("""
                INSERT INTO users (user_id, username, first_name, created_at)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (user_id) DO UPDATE
                SET username = EXCLUDED.username,
                    first_name = EXCLUDED.first_name
            """, user['user_id'], user['username'], user['first_name'], now)
        
        # Insert test subscriptions
        print("📝 Inserting test subscriptions...")
        for user in test_users:
            # Check if subscription exists
            existing = await conn.fetchval("""
                SELECT subscription_id FROM subscriptions WHERE user_id = $1
            """, user['user_id'])
            
            if existing:
                # Update existing subscription
                await conn.execute("""
                    UPDATE subscriptions
                    SET status = $2, expires_at = $3, is_recurring = $4, updated_at = $5
                    WHERE user_id = $1
                """, user['user_id'], user['status'], user['expires_at'], user['is_recurring'], now)
            else:
                # Insert new subscription
                import uuid
                await conn.execute("""
                    INSERT INTO subscriptions (subscription_id, user_id, status, expires_at, is_recurring, created_at, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $6)
                """, str(uuid.uuid4()), user['user_id'], user['status'], user['expires_at'], user['is_recurring'], now)
        
        # Add test payments for revenue metrics
        print("📝 Adding test payments...")
        test_payments = [
            # Today's payments
            {"user_id": 100001, "amount": 3800, "created_at": now, "type": "one_time"},
            {"user_id": 100002, "amount": 2500, "created_at": now - timedelta(hours=2), "type": "recurring_initial"},
            
            # This week's payments
            {"user_id": 100003, "amount": 3800, "created_at": now - timedelta(days=2), "type": "one_time"},
            {"user_id": 100004, "amount": 2500, "created_at": now - timedelta(days=4), "type": "recurring_renewal"},
            
            # This month's payments
            {"user_id": 100005, "amount": 3800, "created_at": now - timedelta(days=10), "type": "one_time"},
            {"user_id": 100006, "amount": 2500, "created_at": now - timedelta(days=15), "type": "recurring_renewal"},
            {"user_id": 100007, "amount": 3800, "created_at": now - timedelta(days=20), "type": "one_time"},
        ]
        
        for i, payment in enumerate(test_payments):
            import uuid
            payment_id = str(uuid.uuid4())
            charge_id = f"test_charge_{i}_{int(now.timestamp())}"
            
            # Check if payment already exists
            existing = await conn.fetchval("""
                SELECT payment_id FROM payments WHERE charge_id = $1
            """, charge_id)
            
            if not existing:
                await conn.execute("""
                    INSERT INTO payments (
                        payment_id, user_id, charge_id, amount, currency, payment_type, 
                        is_recurring, created_at
                    )
                    VALUES ($1, $2, $3, $4, 'XTR', $5, $6, $7)
                """, payment_id, payment['user_id'], charge_id, payment['amount'], payment['type'],
                    payment['type'].startswith('recurring'), payment['created_at'])
        
        # Add test funnel events
        print("📝 Adding test funnel events...")
        test_events = [
            {"user_id": 100001, "event": "offer_shown", "created_at": now - timedelta(hours=1)},
            {"user_id": 100002, "event": "offer_shown", "created_at": now - timedelta(hours=2)},
            {"user_id": 100003, "event": "offer_shown", "created_at": now - timedelta(hours=3)},
            {"user_id": 100001, "event": "invoice_sent", "created_at": now - timedelta(minutes=50)},
            {"user_id": 100002, "event": "invoice_sent", "created_at": now - timedelta(minutes=110)},
            {"user_id": 100001, "event": "payment_success", "created_at": now - timedelta(minutes=45)},
            {"user_id": 100002, "event": "payment_success", "created_at": now - timedelta(minutes=100)},
            {"user_id": 100001, "event": "auto_approved", "created_at": now - timedelta(minutes=40)},
            {"user_id": 100002, "event": "auto_approved", "created_at": now - timedelta(minutes=95)},
        ]
        
        for event in test_events:
            await conn.execute("""
                INSERT INTO funnel_events (user_id, event_type, metadata, created_at)
                VALUES ($1, $2, '{}', $3)
            """, event['user_id'], event['event'], event['created_at'])
        
        # Add one whitelisted overdue member
        print("📝 Adding whitelisted member...")
        await conn.execute("""
            INSERT INTO whitelist (telegram_id, source, granted_at)
            VALUES (100009, 'test_whitelist', $1)
            ON CONFLICT (telegram_id) DO UPDATE
            SET granted_at = EXCLUDED.granted_at
        """, now)
        
        print("\n✅ Test data created successfully!")
        
        # Verify the data
        print("\n📊 Verifying test data:")
        
        # Count subscriptions by status
        status_counts = await conn.fetch("""
            SELECT status, COUNT(*) as count
            FROM subscriptions
            WHERE user_id >= 100000 AND user_id < 200000
            GROUP BY status
            ORDER BY status
        """)
        
        print("\nSubscription Status Summary:")
        for row in status_counts:
            print(f"  {row['status']}: {row['count']} members")
        
        # Count overdue members
        overdue_count = await conn.fetchval("""
            SELECT COUNT(*)
            FROM subscriptions
            WHERE user_id >= 100000 AND user_id < 200000
                AND expires_at < $1
                AND status != 'banned'
        """, now)
        
        print(f"\nOverdue but not kicked: {overdue_count} members")
        
        # Show critical overdue (> 3 days)
        critical_overdue = await conn.fetch("""
            SELECT s.user_id, u.username, 
                   EXTRACT(EPOCH FROM ($1 - s.expires_at))/86400 as days_overdue
            FROM subscriptions s
            JOIN users u ON s.user_id = u.user_id
            WHERE s.user_id >= 100000 AND s.user_id < 200000
                AND s.expires_at < $1 - INTERVAL '3 days'
                AND s.status != 'banned'
            ORDER BY days_overdue DESC
        """, now)
        
        if critical_overdue:
            print("\n🚨 Critical Overdue Members (> 3 days):")
            for row in critical_overdue:
                print(f"  {row['username']} (ID: {row['user_id']}): {row['days_overdue']:.1f} days overdue")
        
        # Calculate test revenue
        revenue_today = await conn.fetchval("""
            SELECT COALESCE(SUM(amount), 0)
            FROM payments
            WHERE user_id >= 100000 AND user_id < 200000
                AND created_at >= $1
        """, now.replace(hour=0, minute=0, second=0, microsecond=0))
        
        revenue_week = await conn.fetchval("""
            SELECT COALESCE(SUM(amount), 0)
            FROM payments
            WHERE user_id >= 100000 AND user_id < 200000
                AND created_at >= $1
        """, now - timedelta(days=7))
        
        print(f"\n💰 Test Revenue:")
        print(f"  Today: {revenue_today} Stars")
        print(f"  This Week: {revenue_week} Stars")
        
        print("\n🎯 Dashboard Test Data Ready!")
        print("Visit /admin/dashboard to see the enhanced dashboard with test data")
        
    except Exception as e:
        print(f"❌ Error creating test data: {e}")
        raise
    finally:
        await conn.close()

async def cleanup_test_data():
    """Remove test data"""
    conn = await asyncpg.connect(DATABASE_URL)
    
    try:
        print("\n🧹 Cleaning up test data...")
        
        # Delete test payments
        await conn.execute("""
            DELETE FROM payments 
            WHERE user_id >= 100000 AND user_id < 200000
        """)
        
        # Delete test funnel events
        await conn.execute("""
            DELETE FROM funnel_events 
            WHERE user_id >= 100000 AND user_id < 200000
        """)
        
        # Delete test subscriptions
        await conn.execute("""
            DELETE FROM subscriptions 
            WHERE user_id >= 100000 AND user_id < 200000
        """)
        
        # Delete test whitelist entries
        await conn.execute("""
            DELETE FROM whitelist 
            WHERE telegram_id >= 100000 AND telegram_id < 200000
        """)
        
        # Delete test users
        await conn.execute("""
            DELETE FROM users 
            WHERE user_id >= 100000 AND user_id < 200000
        """)
        
        print("✅ Test data cleaned up successfully!")
        
    except Exception as e:
        print(f"❌ Error cleaning up test data: {e}")
        raise
    finally:
        await conn.close()

async def main():
    """Main function"""
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "cleanup":
        await cleanup_test_data()
    else:
        # Clean up any existing test data first
        await cleanup_test_data()
        # Create fresh test data
        await create_test_data()

if __name__ == "__main__":
    if not DATABASE_URL:
        print("❌ DATABASE_URL not found in environment")
        exit(1)
    
    asyncio.run(main())