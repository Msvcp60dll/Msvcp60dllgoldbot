#!/usr/bin/env python3
"""
Apply database optimization indexes to Supabase
Run this script to improve query performance
"""

import asyncio
import asyncpg
import sys
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Optimization indexes to apply
INDEXES = [
    # Composite index for frequently used query pattern in get_active_subscription()
    """CREATE INDEX IF NOT EXISTS idx_subscriptions_user_status 
       ON subscriptions(user_id, status)""",
    
    # Index for payment queries filtered by user and date
    """CREATE INDEX IF NOT EXISTS idx_payments_user_created 
       ON payments(user_id, created_at DESC)""",
    
    # Index for recent payment analytics (last 30 days)
    """CREATE INDEX IF NOT EXISTS idx_payments_created_amount 
       ON payments(created_at, amount) 
       WHERE created_at > NOW() - INTERVAL '30 days'""",
    
    # Index for reconciliation queries
    """CREATE INDEX IF NOT EXISTS idx_payments_star_tx_created
       ON payments(star_tx_id, created_at)
       WHERE star_tx_id IS NOT NULL""",
    
    # Composite index for whitelist queries
    """CREATE INDEX IF NOT EXISTS idx_whitelist_user_burned 
       ON whitelist(user_id, burned_at)""",
    
    # Index for grace period queries
    """CREATE INDEX IF NOT EXISTS idx_subscriptions_status_grace
       ON subscriptions(status, grace_until)
       WHERE status = 'grace'""",
    
    # Index for expiring subscriptions
    """CREATE INDEX IF NOT EXISTS idx_subscriptions_status_expires
       ON subscriptions(status, expires_at)
       WHERE status IN ('active', 'grace')"""
]

async def apply_optimizations():
    """Apply database optimization indexes"""
    try:
        # Connect to database
        logger.info(f"Connecting to database...")
        conn = await asyncpg.connect(settings.database_url)
        
        logger.info("Applying optimization indexes...")
        
        for index_sql in INDEXES:
            index_name = index_sql.split('CREATE INDEX IF NOT EXISTS ')[1].split(' ')[0]
            logger.info(f"Creating index: {index_name}")
            try:
                await conn.execute(index_sql)
                logger.info(f"  ✓ {index_name} created successfully")
            except Exception as e:
                logger.error(f"  ✗ Failed to create {index_name}: {e}")
        
        # Analyze tables to update statistics for query planner
        logger.info("\nUpdating table statistics...")
        tables = ['users', 'subscriptions', 'payments', 'whitelist', 'funnel_events']
        for table in tables:
            logger.info(f"Analyzing {table}...")
            await conn.execute(f"ANALYZE {table}")
            logger.info(f"  ✓ {table} analyzed")
        
        # Check existing indexes
        logger.info("\nVerifying indexes...")
        result = await conn.fetch("""
            SELECT schemaname, tablename, indexname 
            FROM pg_indexes 
            WHERE schemaname = 'public' 
            AND tablename IN ('users', 'subscriptions', 'payments', 'whitelist', 'funnel_events')
            ORDER BY tablename, indexname
        """)
        
        current_table = None
        for row in result:
            if row['tablename'] != current_table:
                current_table = row['tablename']
                logger.info(f"\n{current_table}:")
            logger.info(f"  - {row['indexname']}")
        
        await conn.close()
        logger.info("\n✅ Database optimizations applied successfully!")
        
    except Exception as e:
        logger.error(f"Error applying optimizations: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(apply_optimizations())