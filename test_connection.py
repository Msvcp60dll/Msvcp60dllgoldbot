#!/usr/bin/env python3
"""
Test Supabase database connection
Usage: python test_connection.py
"""

import asyncio
import asyncpg
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

async def test_connection():
    """Test database connection with various methods"""
    
    print("=" * 60)
    print("SUPABASE CONNECTION TESTER")
    print("=" * 60)
    print("\nYour credentials:")
    print(f"Project ID: cudmllwhxpamaiqxohse")
    print(f"Password: Msvcp60.dll173323519")
    print(f"SSL Certificate: prod-ca-2021.crt (found)")
    
    print("\n" + "=" * 60)
    print("IMPORTANT: Get your connection string from Supabase")
    print("=" * 60)
    print("\n1. Go to: https://app.supabase.com/project/cudmllwhxpamaiqxohse/settings/database")
    print("2. Find 'Connection string' section")
    print("3. Copy the URI (should be under 'URI' tab)")
    print("4. Paste it below")
    print("\nExample formats:")
    print("  Direct: postgresql://postgres:[PASSWORD]@[HOST]:5432/postgres")
    print("  Pooler: postgresql://postgres.[PROJECT]:[PASSWORD]@[HOST]:5432/postgres")
    
    print("\n" + "-" * 60)
    connection_string = input("\nPaste your connection string here: ").strip()
    
    if not connection_string:
        print("No connection string provided. Exiting.")
        return
    
    # Replace the password placeholder if present
    if "[YOUR-PASSWORD]" in connection_string:
        connection_string = connection_string.replace("[YOUR-PASSWORD]", "Msvcp60.dll173323519")
    elif "YOUR-PASSWORD" in connection_string:
        connection_string = connection_string.replace("YOUR-PASSWORD", "Msvcp60.dll173323519")
    
    print(f"\nTesting connection...")
    print(f"URL: {connection_string[:50]}...")
    
    try:
        # Test without SSL first
        print("\n1. Testing without SSL...")
        try:
            conn = await asyncpg.connect(connection_string, timeout=10)
            print("✅ Connected without SSL!")
            await conn.close()
        except Exception as e:
            print(f"❌ Failed without SSL: {str(e)[:100]}")
        
        # Test with SSL
        print("\n2. Testing with SSL (sslmode=require)...")
        ssl_url = connection_string
        if "?" not in ssl_url:
            ssl_url += "?sslmode=require"
        elif "sslmode=" not in ssl_url:
            ssl_url += "&sslmode=require"
        
        try:
            conn = await asyncpg.connect(ssl_url, timeout=10)
            print("✅ Connected with SSL!")
            
            # Get database info
            print("\n3. Testing database queries...")
            version = await conn.fetchval("SELECT version()")
            print(f"✅ PostgreSQL: {version[:60]}...")
            
            current_db = await conn.fetchval("SELECT current_database()")
            current_user = await conn.fetchval("SELECT current_user")
            print(f"✅ Connected to '{current_db}' as '{current_user}'")
            
            # Check tables
            tables = await conn.fetch("""
                SELECT tablename 
                FROM pg_tables 
                WHERE schemaname = 'public' 
                ORDER BY tablename
                LIMIT 10
            """)
            
            if tables:
                print(f"\n✅ Found {len(tables)} tables:")
                for table in tables:
                    print(f"   - {table['tablename']}")
            else:
                print("\n⚠️ No tables found. Need to run migrations.")
            
            await conn.close()
            
            print("\n" + "=" * 60)
            print("🎉 CONNECTION SUCCESSFUL!")
            print("=" * 60)
            print("\nSave this connection string for deployment:")
            print(ssl_url)
            
            # Extract host for config update
            import re
            if "@" in ssl_url:
                host_part = ssl_url.split("@")[1].split("/")[0]
                print(f"\nHost: {host_part}")
                
                if "pooler.supabase.com" in host_part:
                    print("\n📝 You're using POOLER connection")
                    print("Update app/config.py to use pooler format")
                else:
                    print("\n📝 You're using DIRECT connection")
                    print("Current config should work")
            
        except Exception as e:
            print(f"❌ Failed with SSL: {str(e)}")
            print("\n⚠️ Connection failed. Please check:")
            print("1. Connection string is correct")
            print("2. Database password is correct")
            print("3. IP is whitelisted (if using direct connection)")
    
    except Exception as e:
        print(f"\n❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_connection())