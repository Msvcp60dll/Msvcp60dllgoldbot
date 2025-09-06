#!/usr/bin/env python3
"""
Database migration CLI for Telegram Stars subscription bot

Usage:
    python -m app.migrate           # Run pending migrations
    python -m app.migrate status     # Show migration status
    python -m app.migrate rollback  # Rollback last migration
    python -m app.migrate list      # List all migrations
"""

import asyncio
import sys
import logging
from pathlib import Path
from app.config import settings
from app.migrations.runner import MigrationRunner

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def run_migrations():
    """Run all pending migrations"""
    runner = MigrationRunner(settings.database_url)
    
    try:
        logger.info("🚀 Running database migrations...")
        count = await runner.run_pending_migrations()
        
        if count > 0:
            logger.info(f"✅ Successfully applied {count} migration(s)")
        else:
            logger.info("✅ Database is up to date")
        
        return 0
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        return 1


async def show_status():
    """Show migration status"""
    runner = MigrationRunner(settings.database_url)
    
    try:
        status = await runner.status()
        
        print("\n" + "=" * 60)
        print("📊 Migration Status")
        print("=" * 60)
        print(f"Total migrations:   {status['total_migrations']}")
        print(f"Applied migrations: {status['applied_migrations']}")
        print(f"Pending migrations: {status['pending_migrations']}")
        
        if status['latest_applied']:
            print(f"\nLatest applied:")
            print(f"  Version: {status['latest_applied']['version']}")
            print(f"  Applied: {status['latest_applied']['applied_at']}")
            print(f"  Time:    {status['latest_applied']['execution_time_ms']}ms")
        
        if status['pending_list']:
            print(f"\nPending migrations:")
            for version, filename in status['pending_list']:
                print(f"  {version}: {filename}")
        
        print("=" * 60)
        return 0
        
    except Exception as e:
        logger.error(f"❌ Failed to get status: {e}")
        return 1


async def rollback_last():
    """Rollback the last migration"""
    runner = MigrationRunner(settings.database_url)
    
    try:
        logger.info("⏪ Rolling back last migration...")
        
        success = await runner.rollback_last()
        
        if success:
            logger.info("✅ Successfully rolled back last migration")
            return 0
        else:
            logger.info("ℹ️ No migrations to rollback")
            return 0
            
    except Exception as e:
        logger.error(f"❌ Rollback failed: {e}")
        return 1


async def list_migrations():
    """List all migration files"""
    migrations_dir = Path(__file__).parent / "migrations"
    
    print("\n" + "=" * 60)
    print("📁 Available Migrations")
    print("=" * 60)
    
    migration_files = sorted(migrations_dir.glob("*.sql"))
    
    if not migration_files:
        print("No migration files found")
    else:
        for file_path in migration_files:
            print(f"  {file_path.name}")
    
    print("=" * 60)
    return 0


async def main():
    """Main CLI entry point"""
    if len(sys.argv) == 1 or sys.argv[1] == "run":
        # Default: run migrations
        return await run_migrations()
    
    command = sys.argv[1].lower()
    
    if command == "status":
        return await show_status()
    elif command == "rollback":
        return await rollback_last()
    elif command == "list":
        return await list_migrations()
    elif command in ("help", "-h", "--help"):
        print(__doc__)
        return 0
    else:
        print(f"❌ Unknown command: {command}")
        print(__doc__)
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)