#!/usr/bin/env python3
"""
Whitelist Seeding Script using Telethon (User Account)
Seeds whitelist with all current group members to protect them from being kicked.

Requirements:
    pip install telethon asyncpg python-dotenv

Usage:
    1. First run (will prompt for phone and code):
       python scripts/seed_whitelist.py
    
    2. Subsequent runs (uses saved session):
       python scripts/seed_whitelist.py --auto
    
    3. Dry-run mode (no database changes):
       python scripts/seed_whitelist.py --dry-run

Environment variables needed:
    TELETHON_API_ID     - Get from https://my.telegram.org
    TELETHON_API_HASH   - Get from https://my.telegram.org
    DATABASE_URL        - PostgreSQL connection string
    GROUP_CHAT_ID       - Target group ID (e.g., -1001234567890)
"""

import os
import sys
import asyncio
import argparse
import logging
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path

# Add parent directory to path for imports
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

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class WhitelistSeeder:
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.api_id = os.getenv('TELETHON_API_ID')
        self.api_hash = os.getenv('TELETHON_API_HASH')
        self.database_url = os.getenv('DATABASE_URL')
        self.group_chat_id = int(os.getenv('GROUP_CHAT_ID', '0'))
        
        if not all([self.api_id, self.api_hash, self.database_url, self.group_chat_id]):
            raise ValueError(
                "Missing required environment variables. Needed:\n"
                "- TELETHON_API_ID\n"
                "- TELETHON_API_HASH\n"
                "- DATABASE_URL\n"
                "- GROUP_CHAT_ID"
            )
        
        # Session file for persistence
        self.session_file = 'whitelist_seeder.session'
        self.client: Optional[TelegramClient] = None
        self.db_pool: Optional[asyncpg.Pool] = None
        
    async def connect_telegram(self, auto_login: bool = False):
        """Connect to Telegram as user account"""
        self.client = TelegramClient(self.session_file, self.api_id, self.api_hash)
        await self.client.start()
        
        if not await self.client.is_user_authorized():
            if auto_login:
                logger.error("Not authorized and auto-login requested. Run without --auto first.")
                return False
            
            phone = input("Enter your phone number (with country code): ")
            await self.client.send_code_request(phone)
            
            try:
                code = input("Enter the code you received: ")
                await self.client.sign_in(phone, code)
            except SessionPasswordNeededError:
                password = input("Two-factor authentication enabled. Enter password: ")
                await self.client.sign_in(password=password)
        
        logger.info("Successfully connected to Telegram")
        return True
    
    async def connect_database(self):
        """Connect to database"""
        self.db_pool = await asyncpg.create_pool(
            self.database_url,
            min_size=1,
            max_size=5,
            command_timeout=60
        )
        logger.info("Connected to database")
    
    async def get_all_members(self) -> List[Dict]:
        """Fetch all members from the group"""
        logger.info(f"Fetching members from group {self.group_chat_id}")
        
        # Get the group entity
        group = await self.client.get_entity(self.group_chat_id)
        
        # Fetch all participants
        all_members = []
        offset = 0
        limit = 200  # Telegram's limit per request
        
        while True:
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
                if not user.bot:  # Skip bots
                    member_info = {
                        'user_id': user.id,
                        'username': user.username,
                        'first_name': user.first_name,
                        'last_name': user.last_name,
                        'is_bot': user.bot,
                        'is_deleted': user.deleted,
                        'is_premium': getattr(user, 'premium', False)
                    }
                    all_members.append(member_info)
            
            offset += len(participants.users)
            
            # Progress update
            logger.info(f"Fetched {len(all_members)} members so far...")
            
            if len(participants.users) < limit:
                break
            
            # Small delay to avoid rate limits
            await asyncio.sleep(0.5)
        
        logger.info(f"Total members fetched: {len(all_members)}")
        return all_members
    
    async def check_existing_whitelist(self, user_ids: List[int]) -> Dict[int, bool]:
        """Check which users are already whitelisted"""
        if self.dry_run:
            return {}
        
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT telegram_id 
                FROM whitelist 
                WHERE telegram_id = ANY($1::bigint[]) 
                AND revoked_at IS NULL
            """, user_ids)
            
            return {row['telegram_id']: True for row in rows}
    
    async def seed_whitelist(self, members: List[Dict]) -> Dict:
        """Seed the whitelist with group members"""
        stats = {
            'total_members': len(members),
            'already_whitelisted': 0,
            'newly_whitelisted': 0,
            'failed': 0,
            'bots_skipped': 0,
            'deleted_skipped': 0
        }
        
        # Filter out bots and deleted accounts
        valid_members = []
        for member in members:
            if member['is_bot']:
                stats['bots_skipped'] += 1
            elif member['is_deleted']:
                stats['deleted_skipped'] += 1
            else:
                valid_members.append(member)
        
        logger.info(f"Processing {len(valid_members)} valid members")
        
        # Check existing whitelist
        user_ids = [m['user_id'] for m in valid_members]
        existing = await self.check_existing_whitelist(user_ids)
        
        # Process each member
        for member in valid_members:
            user_id = member['user_id']
            
            if user_id in existing:
                stats['already_whitelisted'] += 1
                continue
            
            # Add to whitelist
            if not self.dry_run:
                try:
                    async with self.db_pool.acquire() as conn:
                        # Build note with member info
                        note_parts = []
                        if member['username']:
                            note_parts.append(f"@{member['username']}")
                        if member['first_name']:
                            note_parts.append(member['first_name'])
                        if member['is_premium']:
                            note_parts.append("Premium")
                        
                        note = f"Seed: {' - '.join(note_parts)}" if note_parts else "Seed: Group member"
                        
                        await conn.execute("""
                            INSERT INTO whitelist (telegram_id, source, note, revoked_at)
                            VALUES ($1, $2, $3, NULL)
                            ON CONFLICT (telegram_id) DO UPDATE
                            SET revoked_at = NULL,
                                source = COALESCE(whitelist.source, $2),
                                note = COALESCE($3, whitelist.note)
                        """, user_id, 'telethon_seed', note)
                        
                        stats['newly_whitelisted'] += 1
                        
                        # Log progress every 50 users
                        if stats['newly_whitelisted'] % 50 == 0:
                            logger.info(f"Progress: {stats['newly_whitelisted']} newly whitelisted")
                        
                except Exception as e:
                    logger.error(f"Failed to whitelist user {user_id}: {e}")
                    stats['failed'] += 1
            else:
                # Dry-run mode
                stats['newly_whitelisted'] += 1
        
        return stats
    
    async def run(self, auto_login: bool = False):
        """Main execution"""
        try:
            # Connect to Telegram
            if not await self.connect_telegram(auto_login):
                return
            
            # Connect to database
            await self.connect_database()
            
            # Get group info
            group = await self.client.get_entity(self.group_chat_id)
            logger.info(f"Target group: {group.title} (ID: {self.group_chat_id})")
            
            if self.dry_run:
                logger.info("🔍 DRY-RUN MODE - No database changes will be made")
            
            # Fetch all members
            members = await self.get_all_members()
            
            if not members:
                logger.warning("No members found in group")
                return
            
            # Seed whitelist
            stats = await self.seed_whitelist(members)
            
            # Print results
            print("\n" + "="*50)
            print("WHITELIST SEEDING COMPLETE")
            print("="*50)
            print(f"Mode: {'DRY-RUN' if self.dry_run else 'LIVE'}")
            print(f"Total members found: {stats['total_members']}")
            print(f"Bots skipped: {stats['bots_skipped']}")
            print(f"Deleted accounts skipped: {stats['deleted_skipped']}")
            print(f"Already whitelisted: {stats['already_whitelisted']}")
            print(f"Newly whitelisted: {stats['newly_whitelisted']}")
            print(f"Failed: {stats['failed']}")
            print("="*50)
            
            if self.dry_run:
                print("\n⚠️ This was a dry-run. Run without --dry-run to apply changes.")
            else:
                print("\n✅ Whitelist has been updated in the database.")
                
                # Log event in database
                async with self.db_pool.acquire() as conn:
                    await conn.execute("""
                        INSERT INTO funnel_events (user_id, event_type, metadata)
                        VALUES (NULL, 'whitelist_bulk_seed', $1)
                    """, stats)
            
        except Exception as e:
            logger.error(f"Error during execution: {e}")
            raise
        finally:
            if self.client:
                await self.client.disconnect()
            if self.db_pool:
                await self.db_pool.close()

def main():
    parser = argparse.ArgumentParser(description='Seed whitelist with group members')
    parser.add_argument('--auto', action='store_true', 
                       help='Use saved session without prompting for login')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be done without making changes')
    
    args = parser.parse_args()
    
    seeder = WhitelistSeeder(dry_run=args.dry_run)
    asyncio.run(seeder.run(auto_login=args.auto))

if __name__ == "__main__":
    main()