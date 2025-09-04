#!/usr/bin/env python3
"""
Seed whitelist with existing group members using Telethon
This script fetches all current members from the group and adds them to the whitelist
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timezone
import logging

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings
from app.db import db

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Check if telethon is installed
try:
    from telethon import TelegramClient
    from telethon.tl.functions.channels import GetParticipantsRequest
    from telethon.tl.types import ChannelParticipantsSearch
except ImportError:
    print("Telethon is required for this script. Install it with:")
    print("pip install telethon")
    sys.exit(1)

async def seed_whitelist_from_group():
    """Fetch group members and add them to whitelist"""
    
    # You need to create a Telegram app and get api_id and api_hash from:
    # https://my.telegram.org/apps
    print("\n=== Telethon Whitelist Seeder ===")
    print("\nTo use this script, you need:")
    print("1. Go to https://my.telegram.org/apps")
    print("2. Create an app (or use existing)")
    print("3. Get your api_id and api_hash")
    print()
    
    api_id = input("Enter your api_id: ").strip()
    api_hash = input("Enter your api_hash: ").strip()
    
    if not api_id or not api_hash:
        print("Error: api_id and api_hash are required")
        return
    
    try:
        api_id = int(api_id)
    except ValueError:
        print("Error: api_id must be a number")
        return
    
    # Create client
    client = TelegramClient('whitelist_seeder_session', api_id, api_hash)
    
    try:
        # Connect and authorize
        await client.start()
        logger.info("Connected to Telegram")
        
        # Get the group/channel entity
        group_id = settings.group_chat_id
        try:
            # For supergroups, the ID is negative and starts with -100
            entity = await client.get_entity(group_id)
            logger.info(f"Found group: {entity.title}")
        except Exception as e:
            logger.error(f"Failed to get group entity: {e}")
            logger.error("Make sure you are a member of the group and have the correct group_chat_id")
            return
        
        # Fetch all participants
        logger.info("Fetching group members...")
        participants = []
        offset = 0
        limit = 100
        
        while True:
            result = await client(GetParticipantsRequest(
                entity,
                ChannelParticipantsSearch(''),
                offset,
                limit,
                hash=0
            ))
            
            if not result.participants:
                break
                
            participants.extend(result.participants)
            offset += len(result.participants)
            
            logger.info(f"Fetched {len(participants)} members so far...")
            
            if len(result.participants) < limit:
                break
        
        logger.info(f"Total members found: {len(participants)}")
        
        # Connect to database
        await db.init()
        
        # Add members to whitelist
        added_count = 0
        skipped_count = 0
        
        for participant in participants:
            user_id = participant.user_id if hasattr(participant, 'user_id') else participant.id
            
            # Skip bots
            user = await client.get_entity(user_id)
            if user.bot:
                logger.debug(f"Skipping bot: {user_id}")
                continue
            
            # Check if already whitelisted
            existing = await db.fetchrow(
                "SELECT * FROM whitelist WHERE user_id = $1 AND burned_at IS NULL",
                user_id
            )
            
            if existing:
                skipped_count += 1
                logger.debug(f"User {user_id} already whitelisted")
                continue
            
            # Add to whitelist
            try:
                await db.execute("""
                    INSERT INTO whitelist (user_id, reason, created_at)
                    VALUES ($1, $2, $3)
                """, user_id, "Existing member - bulk import", datetime.now(timezone.utc))
                
                added_count += 1
                logger.info(f"Added user {user_id} ({user.first_name}) to whitelist")
                
            except Exception as e:
                logger.error(f"Failed to add user {user_id}: {e}")
        
        logger.info(f"\n=== Summary ===")
        logger.info(f"Total members processed: {len(participants)}")
        logger.info(f"Added to whitelist: {added_count}")
        logger.info(f"Already whitelisted: {skipped_count}")
        logger.info(f"Skipped (bots): {len(participants) - added_count - skipped_count}")
        
    except Exception as e:
        logger.error(f"Error: {e}")
        
    finally:
        await client.disconnect()
        await db.close()

async def seed_whitelist_manual():
    """Manually add specific users to whitelist"""
    print("\n=== Manual Whitelist Entry ===")
    print("Enter user IDs to whitelist (comma-separated):")
    print("Example: 123456789,987654321")
    
    user_ids_str = input("> ").strip()
    
    if not user_ids_str:
        print("No user IDs provided")
        return
    
    user_ids = []
    for uid_str in user_ids_str.split(','):
        try:
            user_ids.append(int(uid_str.strip()))
        except ValueError:
            print(f"Invalid user ID: {uid_str}")
            return
    
    reason = input("Enter reason for whitelisting (optional): ").strip() or "Manual whitelist"
    
    # Connect to database
    await db.init()
    
    try:
        added_count = 0
        for user_id in user_ids:
            # Check if already whitelisted
            existing = await db.fetchrow(
                "SELECT * FROM whitelist WHERE user_id = $1 AND burned_at IS NULL",
                user_id
            )
            
            if existing:
                print(f"User {user_id} already whitelisted")
                continue
            
            # Add to whitelist
            await db.execute("""
                INSERT INTO whitelist (user_id, reason, created_at)
                VALUES ($1, $2, $3)
            """, user_id, reason, datetime.now(timezone.utc))
            
            added_count += 1
            print(f"✓ Added user {user_id} to whitelist")
        
        print(f"\nSummary: Added {added_count} users to whitelist")
        
    except Exception as e:
        logger.error(f"Error: {e}")
    finally:
        await db.close()

async def main():
    """Main entry point"""
    print("\n=== Whitelist Seeder ===")
    print("1. Import all members from Telegram group (requires Telethon)")
    print("2. Manually add specific user IDs")
    print("3. Exit")
    
    choice = input("\nSelect option (1-3): ").strip()
    
    if choice == '1':
        await seed_whitelist_from_group()
    elif choice == '2':
        await seed_whitelist_manual()
    elif choice == '3':
        print("Exiting...")
    else:
        print("Invalid choice")

if __name__ == "__main__":
    asyncio.run(main())