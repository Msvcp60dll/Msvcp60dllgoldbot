#!/usr/bin/env python3
"""Check the actual schema of the whitelist table"""

import os
from dotenv import load_dotenv
from supabase import create_client, Client
import asyncpg
import asyncio

load_dotenv()

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_SERVICE_KEY = os.getenv('SUPABASE_SERVICE_KEY')
DATABASE_URL = os.getenv('DATABASE_URL')

async def check_schema():
    """Check whitelist table schema directly"""
    
    # Try with Supabase client first
    print("Checking with Supabase client...")
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        result = supabase.table('whitelist').select('*').limit(1).execute()
        if result.data:
            print("Sample row columns:", list(result.data[0].keys()))
        else:
            print("Table exists but is empty")
    except Exception as e:
        print(f"Supabase error: {e}")
    
    # Check with direct database connection
    print("\nChecking with direct database connection...")
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        
        # Get table structure
        query = """
        SELECT column_name, data_type, is_nullable, column_default 
        FROM information_schema.columns 
        WHERE table_name = 'whitelist' 
        ORDER BY ordinal_position;
        """
        
        rows = await conn.fetch(query)
        
        if rows:
            print("\nWhitelist table schema:")
            print("-" * 60)
            for row in rows:
                print(f"  {row['column_name']:20} {row['data_type']:15} {'NULL' if row['is_nullable'] == 'YES' else 'NOT NULL'}")
        else:
            print("Whitelist table not found!")
            
            # Check if table exists at all
            check_query = """
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name LIKE '%white%';
            """
            tables = await conn.fetch(check_query)
            if tables:
                print("\nTables with 'white' in name:")
                for t in tables:
                    print(f"  - {t['table_name']}")
        
        # Count rows
        count_result = await conn.fetchval("SELECT COUNT(*) FROM whitelist")
        print(f"\nTotal rows in whitelist: {count_result}")
        
        await conn.close()
        
    except Exception as e:
        print(f"Database error: {e}")

if __name__ == "__main__":
    asyncio.run(check_schema())