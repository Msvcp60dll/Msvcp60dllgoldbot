#!/usr/bin/env python3
"""
Check which indexes are currently present/missing in the database
"""

import asyncio
import asyncpg
from app.config import settings

# List of indexes we expect to have after migrations
EXPECTED_INDEXES = [
    # From migration 001
    'idx_subscriptions_user_status',
    'idx_subscriptions_expires_at',
    'idx_subscriptions_grace_until',
    'idx_subscriptions_status_expires',
    'idx_payments_created_at',
    'idx_payments_user_id',
    'idx_payments_recurring',
    'idx_payments_user_type',
    'idx_funnel_events_created_type',
    'idx_funnel_events_user',
    'idx_funnel_events_type_created',
    'idx_whitelist_active',
    'idx_users_last_seen',
    
    # From migration 002
    'idx_users_no_payment',
    'idx_subscriptions_expired_cleanup',
    'idx_payments_dashboard_summary',
    'idx_subscriptions_mrr',
    'idx_payments_star_tx_lookup',
    'idx_payments_charge_lookup',
    'idx_whitelist_pending_burn',
    
    # Existing unique constraints (should already be there)
    'uniq_payments_charge_id',
    'uniq_payments_star_tx',
]


async def check_indexes():
    """Check which indexes exist in the database"""
    conn = await asyncpg.connect(settings.database_url)
    
    try:
        # Query to get all indexes
        indexes = await conn.fetch("""
            SELECT 
                indexname,
                tablename,
                indexdef
            FROM pg_indexes
            WHERE schemaname = 'public'
            ORDER BY tablename, indexname;
        """)
        
        # Get index names
        existing_names = {idx['indexname'] for idx in indexes}
        
        print("=" * 70)
        print("📊 DATABASE INDEX ANALYSIS")
        print("=" * 70)
        
        # Check expected indexes
        print("\n✅ EXISTING INDEXES:")
        found = []
        for expected in EXPECTED_INDEXES:
            if expected in existing_names:
                found.append(expected)
                # Find the table for this index
                table = next((idx['tablename'] for idx in indexes if idx['indexname'] == expected), 'unknown')
                print(f"  ✓ {expected} (on {table})")
        
        print(f"\nTotal: {len(found)}/{len(EXPECTED_INDEXES)} expected indexes exist")
        
        # Check missing indexes
        missing = [idx for idx in EXPECTED_INDEXES if idx not in existing_names]
        if missing:
            print("\n❌ MISSING INDEXES:")
            for idx_name in missing:
                print(f"  ✗ {idx_name}")
            print(f"\nTotal: {len(missing)} indexes missing")
            print("\n💡 Run migrations to create missing indexes:")
            print("   python -m app.migrate")
        else:
            print("\n🎉 All expected indexes are present!")
        
        # Show other indexes (not in our expected list)
        other_indexes = [idx for idx in existing_names if idx not in EXPECTED_INDEXES and not idx.endswith('_pkey')]
        if other_indexes:
            print("\n📦 OTHER INDEXES (not managed by migrations):")
            for idx_name in sorted(other_indexes):
                table = next((idx['tablename'] for idx in indexes if idx['indexname'] == idx_name), 'unknown')
                print(f"  • {idx_name} (on {table})")
        
        # Table statistics
        print("\n📈 TABLE STATISTICS:")
        tables = {}
        for idx in indexes:
            table = idx['tablename']
            if table not in tables:
                tables[table] = []
            tables[table].append(idx['indexname'])
        
        for table in sorted(tables.keys()):
            non_pkey_indexes = [idx for idx in tables[table] if not idx.endswith('_pkey')]
            print(f"  {table}: {len(non_pkey_indexes)} indexes (+1 primary key)")
        
        print("\n" + "=" * 70)
        
        # Check if migrations table exists
        migrations_exist = await conn.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables 
                WHERE table_name = 'schema_migrations'
            )
        """)
        
        if migrations_exist:
            # Get migration status
            applied = await conn.fetch("""
                SELECT version, applied_at, execution_time_ms 
                FROM schema_migrations 
                ORDER BY version
            """)
            
            if applied:
                print("\n🔄 APPLIED MIGRATIONS:")
                for migration in applied:
                    print(f"  Version {migration['version']}: "
                          f"Applied {migration['applied_at'].strftime('%Y-%m-%d %H:%M:%S')} "
                          f"({migration['execution_time_ms']}ms)")
            else:
                print("\n⚠️ No migrations have been applied yet")
        else:
            print("\n⚠️ Migration tracking table does not exist")
            print("Run 'python -m app.migrate' to initialize the migration system")
        
        print("=" * 70)
        
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(check_indexes())