#!/usr/bin/env python3
"""
Test script for the migration system
Run this to verify migrations work correctly
"""

import asyncio
import logging
from app.config import settings
from app.migrations.runner import MigrationRunner

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_migrations():
    """Test the migration system"""
    runner = MigrationRunner(settings.database_url)
    
    logger.info("=" * 60)
    logger.info("🧪 Testing Migration System")
    logger.info("=" * 60)
    
    try:
        # 1. Initialize migrations table
        logger.info("\n1️⃣ Initializing migrations table...")
        await runner.initialize()
        logger.info("✅ Migrations table ready")
        
        # 2. Check current status
        logger.info("\n2️⃣ Checking migration status...")
        status = await runner.status()
        logger.info(f"   Total migrations: {status['total_migrations']}")
        logger.info(f"   Applied: {status['applied_migrations']}")
        logger.info(f"   Pending: {status['pending_migrations']}")
        
        # 3. List migration files
        logger.info("\n3️⃣ Available migration files:")
        migrations = runner.get_migration_files()
        for version, path in migrations:
            logger.info(f"   {version}: {path.name}")
        
        # 4. Test parsing a migration file
        logger.info("\n4️⃣ Testing migration file parser...")
        if migrations:
            version, path = migrations[0]
            up_sql, down_sql = runner.parse_migration_file(path)
            logger.info(f"   File: {path.name}")
            logger.info(f"   UP section: {len(up_sql)} chars")
            logger.info(f"   DOWN section: {len(down_sql)} chars")
            logger.info("✅ Parser working correctly")
        
        # 5. Run pending migrations (if any)
        logger.info("\n5️⃣ Checking for pending migrations...")
        count = await runner.run_pending_migrations()
        
        if count > 0:
            logger.info(f"✅ Applied {count} migration(s)")
        else:
            logger.info("✅ No pending migrations")
        
        # 6. Final status
        logger.info("\n6️⃣ Final status:")
        final_status = await runner.status()
        
        if final_status['latest_applied']:
            latest = final_status['latest_applied']
            logger.info(f"   Latest migration: {latest['version']}")
            logger.info(f"   Applied at: {latest['applied_at']}")
            logger.info(f"   Execution time: {latest['execution_time_ms']}ms")
        
        logger.info("\n" + "=" * 60)
        logger.info("✅ Migration system test completed successfully!")
        logger.info("=" * 60)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_migrations())
    exit(0 if success else 1)