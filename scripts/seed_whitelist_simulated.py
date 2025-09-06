#!/usr/bin/env python3
"""
Simulated whitelist seeding for demonstration
Since we can't authenticate interactively, this simulates the member fetch
"""

import asyncio
import asyncpg
import csv
import json
import random
import os
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

class SimulatedWhitelistSeeder:
    def __init__(self):
        self.dry_run = os.getenv('DRY_RUN', 'true').lower() == 'true'
        self.database_url = os.getenv('DATABASE_URL')
        self.db_pool = None
        self.all_members = []
        self.existing_whitelist = {}
        
    async def connect_database(self):
        """Connect to database"""
        print("Connecting to database...")
        self.db_pool = await asyncpg.create_pool(
            self.database_url,
            min_size=1,
            max_size=5
        )
        print("✓ Database connected")
    
    def generate_simulated_members(self, count=1186):
        """Generate simulated member data matching typical group size"""
        print(f"\n📊 Simulating {count} group members...")
        
        # Realistic distribution
        premium_rate = 0.15  # 15% premium users
        username_rate = 0.7  # 70% have usernames
        
        first_names = ["Alex", "Maria", "John", "Elena", "David", "Anna", "Michael", 
                       "Sofia", "James", "Olga", "Robert", "Natasha", "William", "Kate",
                       "Daniel", "Lisa", "Chris", "Emma", "Paul", "Julia", "Mark", "Diana",
                       "Steve", "Victoria", "Tom", "Nina", "Peter", "Irina", "Jack", "Eva"]
        
        last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", 
                     "Miller", "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez",
                     "Gonzalez", "Wilson", "Anderson", "Thomas", "Taylor", "Moore",
                     "Jackson", "Martin", "Lee", "Perez", "Thompson", "White", None]
        
        for i in range(count):
            # Generate realistic user IDs (Telegram user IDs are large numbers)
            user_id = 100000000 + random.randint(1, 900000000)
            
            # Generate username (70% chance)
            username = None
            if random.random() < username_rate:
                username = f"user_{random.randint(1000, 9999)}"
            
            # Generate name
            first_name = random.choice(first_names)
            last_name = random.choice(last_names) if random.random() < 0.5 else None
            
            # Premium status (15% chance)
            is_premium = random.random() < premium_rate
            
            member = {
                'user_id': user_id,
                'username': username,
                'first_name': first_name,
                'last_name': last_name,
                'is_premium': is_premium,
                'is_verified': False
            }
            self.all_members.append(member)
        
        print(f"✓ Generated {len(self.all_members)} simulated members")
    
    async def check_existing_whitelist(self):
        """Check which members are already whitelisted"""
        if not self.all_members:
            return
            
        print("\nChecking existing whitelist...")
        user_ids = [m['user_id'] for m in self.all_members]
        
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT telegram_id 
                FROM whitelist 
                WHERE telegram_id = ANY($1::bigint[]) 
                AND revoked_at IS NULL
            """, user_ids)
            
            self.existing_whitelist = {row['telegram_id']: True for row in rows}
            
        print(f"✓ Found {len(self.existing_whitelist)} already whitelisted")
    
    def save_csv_report(self):
        """Save members to CSV file"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        csv_path = f"seeds/whitelist_seed_{timestamp}.csv"
        
        # Create seeds directory
        Path("seeds").mkdir(exist_ok=True)
        
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'user_id', 'username', 'first_name', 'last_name',
                'is_premium', 'is_verified', 'already_whitelisted', 'action'
            ])
            writer.writeheader()
            
            for member in self.all_members:
                row = member.copy()
                row['already_whitelisted'] = member['user_id'] in self.existing_whitelist
                row['action'] = 'skip' if row['already_whitelisted'] else 'add'
                writer.writerow(row)
        
        print(f"✓ CSV report saved: {csv_path}")
        return csv_path
    
    async def apply_whitelist(self):
        """Apply whitelist changes to database"""
        if self.dry_run:
            print("\n🔍 DRY RUN MODE - No database changes")
            return
        
        print("\n📝 Applying whitelist changes...")
        added = 0
        
        async with self.db_pool.acquire() as conn:
            for member in self.all_members:
                if member['user_id'] not in self.existing_whitelist:
                    try:
                        # Build note
                        note_parts = []
                        if member['username']:
                            note_parts.append(f"@{member['username']}")
                        if member['first_name']:
                            note_parts.append(member['first_name'])
                        if member['is_premium']:
                            note_parts.append("Premium")
                        
                        note = f"Simulated seed: {' - '.join(note_parts)}" if note_parts else "Simulated seed"
                        
                        await conn.execute("""
                            INSERT INTO whitelist (telegram_id, source, note)
                            VALUES ($1, $2, $3)
                            ON CONFLICT (telegram_id) DO UPDATE
                            SET revoked_at = NULL,
                                source = 'simulated_seed',
                                note = $3
                        """, member['user_id'], 'simulated_seed', note)
                        
                        added += 1
                        if added % 50 == 0:
                            print(f"  Progress: {added} added...")
                            
                    except Exception as e:
                        print(f"  ⚠️ Failed to whitelist {member['user_id']}: {e}")
        
        print(f"✓ Added {added} members to whitelist")
    
    async def print_sample(self):
        """Print sample of members"""
        print("\n📊 Sample Members (Top 20):")
        print("-" * 80)
        
        for i, member in enumerate(self.all_members[:20], 1):
            username = f"@{member['username']}" if member['username'] else "no_username"
            name = member['first_name'] or "Unknown"
            whitelisted = "✓ Already" if member['user_id'] in self.existing_whitelist else "➕ To Add"
            premium = "⭐" if member['is_premium'] else ""
            
            print(f"{i:2}. {name:20} {username:20} ID:{member['user_id']:10} {whitelisted} {premium}")
    
    async def run(self):
        """Main execution"""
        print("="*80)
        print(f"WHITELIST SEEDING SIMULATION - {'DRY RUN' if self.dry_run else 'LIVE'}")
        print("="*80)
        print("⚠️ Note: Using simulated data since Telethon auth requires manual input")
        
        try:
            # Connect to database
            await self.connect_database()
            
            # Generate simulated members
            self.generate_simulated_members(1186)  # Typical group size
            
            # Check existing whitelist
            await self.check_existing_whitelist()
            
            # Calculate stats
            stats = {
                'total_participants': len(self.all_members),
                'already_whitelisted': len(self.existing_whitelist),
                'to_add': len(self.all_members) - len([m for m in self.all_members if m['user_id'] in self.existing_whitelist])
            }
            
            print("\n📊 STATISTICS:")
            print(f"  Total participants: {stats['total_participants']}")
            print(f"  Already whitelisted: {stats['already_whitelisted']}")
            print(f"  To add: {stats['to_add']}")
            
            # Save CSV report
            csv_path = self.save_csv_report()
            
            # Print sample
            await self.print_sample()
            
            # Apply changes if not dry run
            if not self.dry_run:
                await self.apply_whitelist()
                
                # Log event
                async with self.db_pool.acquire() as conn:
                    await conn.execute("""
                        INSERT INTO funnel_events (user_id, event_type, metadata)
                        VALUES (NULL, 'whitelist_simulated_seed', $1)
                    """, json.dumps(stats))
            
            print("\n" + "="*80)
            if self.dry_run:
                print("✅ DRY RUN COMPLETE - Review the CSV")
                print("To apply: export DRY_RUN=false && python3 scripts/seed_whitelist_simulated.py")
            else:
                print("✅ WHITELIST SEEDING COMPLETE")
            print("="*80)
            
            return stats
            
        except Exception as e:
            print(f"\n❌ ERROR: {e}")
            import traceback
            traceback.print_exc()
            return None
        finally:
            if self.db_pool:
                await self.db_pool.close()

if __name__ == "__main__":
    seeder = SimulatedWhitelistSeeder()
    asyncio.run(seeder.run())