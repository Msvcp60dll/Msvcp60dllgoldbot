#!/usr/bin/env python3
"""Check subscriptions table schema"""

import asyncio
import os
from dotenv import load_dotenv
import asyncpg

load_dotenv()
DATABASE_URL = os.getenv('DATABASE_URL')

async def check_schema():
    conn = await asyncpg.connect(DATABASE_URL)
    
    try:
        # Get table columns
        columns = await conn.fetch("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'subscriptions'
            ORDER BY ordinal_position
        """)
        
        print("Subscriptions table columns:")
        for col in columns:
            print(f"  {col['column_name']:20} {col['data_type']:20} {'NULL' if col['is_nullable'] == 'YES' else 'NOT NULL'}")
        
        # Get constraints
        constraints = await conn.fetch("""
            SELECT constraint_name, constraint_type
            FROM information_schema.table_constraints
            WHERE table_name = 'subscriptions'
        """)
        
        print("\nConstraints:")
        for con in constraints:
            print(f"  {con['constraint_name']:30} {con['constraint_type']}")
        
        # Get indexes
        indexes = await conn.fetch("""
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE tablename = 'subscriptions'
        """)
        
        print("\nIndexes:")
        for idx in indexes:
            print(f"  {idx['indexname']}")
            
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(check_schema())