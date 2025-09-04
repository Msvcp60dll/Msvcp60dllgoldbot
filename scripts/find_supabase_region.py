#!/usr/bin/env python3
"""
Find the correct Supabase pooler region for your project
"""

import asyncio
import asyncpg
import sys
import time
from pathlib import Path

# Add parent directory
sys.path.insert(0, str(Path(__file__).parent.parent))

async def find_region():
    """Test all possible Supabase pooler regions"""
    
    password = 'Msvcp60.dll173323519'
    project_id = 'cudmllwhxpamaiqxohse'
    
    # All possible AWS regions where Supabase has poolers
    regions = [
        # US regions
        'us-west-1', 'us-west-2', 
        'us-east-1', 'us-east-2',
        
        # Europe regions  
        'eu-west-1', 'eu-west-2', 'eu-west-3',
        'eu-central-1', 'eu-north-1',
        
        # Asia Pacific regions
        'ap-southeast-1', 'ap-southeast-2',
        'ap-northeast-1', 'ap-northeast-2', 'ap-northeast-3',
        'ap-south-1', 'ap-east-1',
        
        # Other regions
        'sa-east-1',  # South America
        'ca-central-1',  # Canada
        'me-south-1',  # Middle East
        'af-south-1',  # Africa
    ]
    
    print("=" * 60)
    print("SUPABASE POOLER REGION FINDER")
    print("=" * 60)
    print(f"\nProject ID: {project_id}")
    print(f"Testing {len(regions)} regions...")
    print("-" * 60)
    
    found_regions = []
    
    for i, region in enumerate(regions, 1):
        print(f"\n[{i}/{len(regions)}] Testing {region}...", end="")
        
        # Test both session and transaction ports
        for port_name, port in [("session", 5432), ("transaction", 6543)]:
            host = f'aws-0-{region}.pooler.supabase.com'
            
            # Use pooler format: postgres.project_id as username
            url = f'postgresql://postgres.{project_id}:{password}@{host}:{port}/postgres?sslmode=require'
            
            try:
                # Quick timeout to speed up testing
                conn = await asyncpg.connect(url, timeout=2)
                
                print(f"\n✅ FOUND! Region: {region} (Port: {port}/{port_name})")
                
                # Get more details
                db = await conn.fetchval('SELECT current_database()')
                version = await conn.fetchval('SELECT version()')
                
                print(f"   Database: {db}")
                print(f"   Version: {version[:50]}...")
                
                # Check tables
                tables = await conn.fetch(
                    "SELECT COUNT(*) as count FROM pg_tables WHERE schemaname = 'public'"
                )
                table_count = tables[0]['count'] if tables else 0
                print(f"   Tables: {table_count}")
                
                await conn.close()
                
                found_regions.append({
                    'region': region,
                    'port': port,
                    'port_name': port_name,
                    'host': host,
                    'url': url
                })
                
                # Found working connection, no need to test other port
                break
                
            except asyncio.TimeoutError:
                print(".", end="")
                continue
            except Exception as e:
                if "Tenant or user" not in str(e):
                    print(f" ({str(e)[:30]})", end="")
                continue
    
    print("\n" + "=" * 60)
    
    if found_regions:
        print("🎉 SUCCESS! Found working connections:")
        print("=" * 60)
        
        for conn in found_regions:
            print(f"\nRegion: {conn['region']}")
            print(f"Port: {conn['port']} ({conn['port_name']} mode)")
            print(f"Host: {conn['host']}")
            print(f"\nConnection string:")
            print(conn['url'])
            
        # Save the working connection
        print("\n" + "-" * 60)
        print("NEXT STEPS:")
        print("-" * 60)
        print("1. Update your .env file with:")
        print(f"   SUPABASE_DB_REGION={found_regions[0]['region']}")
        print(f"   SUPABASE_DB_PORT={found_regions[0]['port']}")
        print("\n2. Update app/config.py to use pooler format:")
        print("   return f\"postgresql://postgres.{project_id}:{password}@aws-0-{region}.pooler.supabase.com:{port}/postgres\"")
        
        # Write to file for reference
        with open('supabase_connection.txt', 'w') as f:
            f.write(f"Working Supabase Connection\n")
            f.write(f"=" * 40 + "\n")
            f.write(f"Region: {found_regions[0]['region']}\n")
            f.write(f"Port: {found_regions[0]['port']}\n")
            f.write(f"Connection String:\n{found_regions[0]['url']}\n")
        
        print("\n✅ Connection details saved to: supabase_connection.txt")
        
    else:
        print("❌ No working pooler region found")
        print("=" * 60)
        print("\nThis could mean:")
        print("1. Your Supabase project uses a custom/enterprise configuration")
        print("2. Connection pooling is disabled")
        print("3. There are IP restrictions in place")
        print("\nYou MUST get the connection string from Supabase dashboard:")
        print("https://app.supabase.com/project/cudmllwhxpamaiqxohse/settings/database")

if __name__ == "__main__":
    print("Starting region scan... This may take 1-2 minutes.\n")
    start_time = time.time()
    asyncio.run(find_region())
    print(f"\nScan completed in {time.time() - start_time:.1f} seconds")