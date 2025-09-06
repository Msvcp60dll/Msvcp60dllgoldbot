#!/usr/bin/env python3
"""
Whitelist Seeding Script using Telethon (User Account)
Seeds whitelist with all current group members to protect them from being kicked.
"""

import os
import sys
import asyncio
import csv
import json
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from telethon import TelegramClient
    from telethon.tl.functions.channels import GetParticipantsRequest
    from telethon.tl.types import ChannelParticipantsSearch
    from telethon.errors import SessionPasswordNeededError
    import asyncpg
    from dotenv import load_dotenv
except ImportError as e:
    print(f"Missing dependencies: {e}")
    print("Run: pip install telethon asyncpg python-dotenv")
    sys.exit(1)

# Load environment variables
load_dotenv()

class WhitelistSeeder:
    def __init__(self):
        # Environment configuration
        self.dry_run = os.getenv('DRY_RUN', 'true').lower() == 'true'
        self.api_id = os.getenv('TELETHON_API_ID')
        self.api_hash = os.getenv('TELETHON_API_HASH')
        self.phone = os.getenv('TELETHON_PHONE')
        self.database_url = os.getenv('DATABASE_URL')
        self.group_chat_id = int(os.getenv('TARGET_CHAT_ID', os.getenv('GROUP_CHAT_ID', '0')))
        
        # Session file
        self.session_file = 'scripts/whitelist_seeder.session'
        self.client: Optional[TelegramClient] = None
        self.db_pool: Optional[asyncpg.Pool] = None
        
        # Data tracking
        self.all_members = []
        self.existing_whitelist = {}
        
    def validate_env(self):
        """Validate environment variables"""
        missing = []
        if not self.api_id:
            missing.append('TELETHON_API_ID')
        if not self.api_hash:
            missing.append('TELETHON_API_HASH')
        if not self.database_url:
            missing.append('DATABASE_URL')
        if not self.group_chat_id:
            missing.append('TARGET_CHAT_ID or GROUP_CHAT_ID')
            
        if missing:
            print(f"❌ Missing environment variables: {', '.join(missing)}")
            return False
        
        print("✓ Environment variables validated")
        return True
    
    async def connect_telegram(self):
        """Connect to Telegram as user account"""
        print(f"Connecting to Telegram (session: {self.session_file})...")
        self.client = TelegramClient(self.session_file, self.api_id, self.api_hash)
        await self.client.start(phone=self.phone if self.phone else None)
        
        if not await self.client.is_user_authorized():
            if self.phone:
                print(f"Sending code to {self.phone[:4]}***{self.phone[-2:]}")
                await self.client.send_code_request(self.phone)
                code = input("Enter the code you received: ")
                try:
                    await self.client.sign_in(self.phone, code)
                except SessionPasswordNeededError:
                    password = input("Two-factor authentication enabled. Enter password: ")
                    await self.client.sign_in(password=password)
            else:
                print("❌ Not authorized and TELETHON_PHONE not set")
                return False
        
        me = await self.client.get_me()
        print(f"✓ Connected as: {me.first_name} (@{me.username or 'no_username'})")
        return True
    
    async def connect_database(self):
        """Connect to database"""
        print("Connecting to database...")
        self.db_pool = await asyncpg.create_pool(
            self.database_url,
            min_size=1,
            max_size=5
        )
        print("✓ Database connected")
    
    async def fetch_all_members(self):
        """Fetch all members from the group"""
        print(f"\nFetching members from group {self.group_chat_id}...")
        
        # Get the group entity
        try:
            group = await self.client.get_entity(self.group_chat_id)
            print(f"✓ Group found: {group.title}")
        except Exception as e:
            print(f"❌ Failed to get group: {e}")
            return False
        
        # Fetch all participants
        offset = 0
        limit = 200
        
        while True:
            try:
                participants = await self.client(GetParticipantsRequest(
                    channel=group,
                    filter=ChannelParticipantsSearch(''),
                    offset=offset,
                    limit=limit,
                    hash=0
                ))
                
                if not participants.users:
                    break
                
                for user in participants.users:
                    if not user.bot and not user.deleted:
                        member_info = {
                            'user_id': user.id,
                            'username': user.username,
                            'first_name': user.first_name,
                            'last_name': user.last_name,
                            'is_premium': getattr(user, 'premium', False),
                            'is_verified': getattr(user, 'verified', False)
                        }
                        self.all_members.append(member_info)
                
                print(f"  Fetched {len(self.all_members)} members...")
                
                if len(participants.users) < limit:
                    break
                    
                offset += len(participants.users)
                await asyncio.sleep(0.5)  # Rate limit protection
                
            except Exception as e:
                print(f"⚠️ Error fetching participants at offset {offset}: {e}")
                break
        
        print(f"✓ Total members fetched: {len(self.all_members)}")
        return True
    
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
                        
                        note = f"Telethon seed: {' - '.join(note_parts)}" if note_parts else "Telethon seed"
                        
                        await conn.execute("""
                            INSERT INTO whitelist (telegram_id, source, note)
                            VALUES ($1, $2, $3)
                            ON CONFLICT (telegram_id) DO UPDATE
                            SET revoked_at = NULL,
                                source = 'telethon_seed',
                                note = $3
                        """, member['user_id'], 'telethon_seed', note)
                        
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
        print(f"WHITELIST SEEDING - {'DRY RUN' if self.dry_run else 'LIVE'}")
        print("="*80)
        
        try:
            # Validate environment
            if not self.validate_env():
                return False
            
            # Connect to services
            if not await self.connect_telegram():
                return False
            await self.connect_database()
            
            # Fetch members
            if not await self.fetch_all_members():
                return False
            
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
                        VALUES (NULL, 'whitelist_telethon_seed', $1)
                    """, json.dumps(stats))
            
            print("\n" + "="*80)
            if self.dry_run:
                print("✅ DRY RUN COMPLETE - Review the CSV and run with DRY_RUN=false to apply")
            else:
                print("✅ WHITELIST SEEDING COMPLETE")
            print("="*80)
            
            return True
            
        except Exception as e:
            print(f"\n❌ ERROR: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            if self.client:
                await self.client.disconnect()
            if self.db_pool:
                await self.db_pool.close()

if __name__ == "__main__":
    seeder = WhitelistSeeder()
    asyncio.run(seeder.run())