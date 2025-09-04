#!/usr/bin/env python3
"""
Database setup script for Telegram Stars Membership Bot
Runs migrations and initial setup
"""

import asyncio
import asyncpg
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings

async def setup_database():
    """Run database migrations and setup"""
    print("🔧 Setting up database...")
    
    try:
        # Connect to database
        conn = await asyncpg.connect(settings.database_url)
        print(f"✅ Connected to database")
        
        # Read SQL schema
        schema_path = Path(__file__).parent.parent / "app" / "models.sql"
        with open(schema_path, 'r') as f:
            schema_sql = f.read()
        
        # Execute schema
        print("📝 Running migrations...")
        await conn.execute(schema_sql)
        print("✅ Schema created/updated")
        
        # Verify tables
        tables = await conn.fetch("""
            SELECT tablename FROM pg_tables 
            WHERE schemaname = 'public'
            ORDER BY tablename
        """)
        
        print(f"\n📊 Created {len(tables)} tables:")
        for table in tables:
            print(f"  - {table['tablename']}")
        
        # Check indexes
        indexes = await conn.fetch("""
            SELECT indexname FROM pg_indexes 
            WHERE schemaname = 'public' 
            AND indexname LIKE 'uniq_%'
        """)
        
        print(f"\n🔐 Idempotency indexes:")
        for idx in indexes:
            print(f"  - {idx['indexname']}")
        
        # Create initial owner whitelist if OWNER_IDS set
        if settings.owner_ids:
            print(f"\n👤 Adding {len(settings.owner_ids)} owners to whitelist...")
            for owner_id in settings.owner_ids:
                await conn.execute("""
                    INSERT INTO whitelist (user_id, reason)
                    VALUES ($1, 'Bot owner')
                    ON CONFLICT DO NOTHING
                """, owner_id)
            print("✅ Owners whitelisted")
        
        await conn.close()
        print("\n✨ Database setup complete!")
        
    except asyncpg.PostgresError as e:
        print(f"\n❌ Database error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)

async def verify_connection():
    """Verify database connection"""
    print("🔍 Verifying database connection...")
    
    try:
        conn = await asyncpg.connect(settings.database_url)
        version = await conn.fetchval("SELECT version()")
        print(f"✅ Connected to: {version.split(',')[0]}")
        
        # Test a simple query
        result = await conn.fetchval("SELECT COUNT(*) FROM users")
        print(f"📊 Current users in database: {result}")
        
        await conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False

async def main():
    """Main setup flow"""
    print("=" * 50)
    print("Telegram Stars Membership Bot - Database Setup")
    print("=" * 50)
    
    # Check environment - settings already loaded from config
    if not settings.supabase_url:
        print("\n❌ Error: SUPABASE_URL not configured")
        print("Please configure your .env file first")
        sys.exit(1)
    
    # Verify connection first
    if not await verify_connection():
        sys.exit(1)
    
    # Prompt for confirmation
    print("\n⚠️  This will create/update the database schema")
    response = input("Continue? (yes/no): ")
    
    if response.lower() != 'yes':
        print("Setup cancelled")
        sys.exit(0)
    
    # Run setup
    await setup_database()

if __name__ == "__main__":
    asyncio.run(main())