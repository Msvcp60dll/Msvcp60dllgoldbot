#!/usr/bin/env python3
"""
Automated Telegram Group Member Extractor
Exports all members from a Telegram group to CSV format
"""

import os
import sys
import csv
import asyncio
import argparse
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from telethon import TelegramClient
from telethon.tl.functions.channels import GetParticipantsRequest
from telethon.tl.types import ChannelParticipantsSearch
from telethon.errors import FloodWaitError, SessionPasswordNeededError
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
API_ID = int(os.getenv('TG_API_ID', ''))
API_HASH = os.getenv('TG_API_HASH', '')
PHONE = os.getenv('TG_PHONE', '')

# Validate credentials
if not all([API_ID, API_HASH, PHONE]):
    print("❌ Missing credentials in .env file")
    sys.exit(1)

class MemberExtractor:
    def __init__(self, session_name: str = 'member_extractor'):
        self.client = TelegramClient(session_name, API_ID, API_HASH)
        self.members: List[Dict[str, Any]] = []
        
    async def connect(self) -> bool:
        """Connect to Telegram and authenticate"""
        print(f"📱 Connecting with phone: {PHONE}")
        
        try:
            await self.client.connect()
            
            if not await self.client.is_user_authorized():
                print("\n⚠️  First-time authentication required")
                print("📲 Sending code to your Telegram app...")
                
                await self.client.send_code_request(PHONE)
                
                print("\n" + "="*60)
                print("🔐 CHECK YOUR TELEGRAM APP FOR THE LOGIN CODE")
                print("="*60)
                code = input("Enter the code you received: ")
                
                try:
                    await self.client.sign_in(PHONE, code)
                except SessionPasswordNeededError:
                    print("⚠️  2FA is enabled")
                    password = input("Enter your 2FA password: ")
                    await self.client.sign_in(password=password)
            
            # Verify we're logged in
            me = await self.client.get_me()
            print(f"\n✅ Logged in as: {me.first_name} (@{me.username or 'No username'})")
            return True
            
        except Exception as e:
            print(f"❌ Authentication failed: {e}")
            return False
    
    async def list_groups(self) -> List[Dict[str, Any]]:
        """Get all groups/channels where user is a member"""
        print("\n📋 Fetching your groups...")
        dialogs = await self.client.get_dialogs()
        
        groups = []
        for dialog in dialogs:
            if dialog.is_group or dialog.is_channel:
                entity = dialog.entity
                groups.append({
                    'id': entity.id,
                    'title': entity.title,
                    'type': 'Channel' if dialog.is_channel else 'Group',
                    'members': getattr(entity, 'participants_count', 'Unknown')
                })
        
        return groups
    
    async def extract_members(self, group_id: int, aggressive: bool = False) -> int:
        """Extract all members from a group"""
        try:
            # Get the group entity
            group = await self.client.get_entity(group_id)
            print(f"\n📥 Extracting members from: {group.title}")
            print(f"   Group ID: {group.id}")
            
            # Prepare for extraction
            all_participants = []
            offset = 0
            limit = 100 if not aggressive else 200
            
            while True:
                try:
                    participants = await self.client(GetParticipantsRequest(
                        group, ChannelParticipantsSearch(''), offset, limit,
                        hash=0
                    ))
                    
                    if not participants.users:
                        break
                    
                    all_participants.extend(participants.users)
                    offset += len(participants.users)
                    
                    print(f"   Extracted {offset} members...", end='\r')
                    
                    # Small delay to avoid rate limits
                    if not aggressive:
                        await asyncio.sleep(1)
                    else:
                        await asyncio.sleep(0.5)
                    
                except FloodWaitError as e:
                    print(f"\n⚠️  Rate limited. Waiting {e.seconds} seconds...")
                    await asyncio.sleep(e.seconds)
                    continue
            
            # Process members
            print(f"\n✅ Total members extracted: {len(all_participants)}")
            
            for user in all_participants:
                if not user.deleted and not user.bot:
                    self.members.append({
                        'user_id': user.id,
                        'username': user.username or '',
                        'first_name': user.first_name or '',
                        'last_name': user.last_name or '',
                        'phone': user.phone or '',
                        'is_premium': getattr(user, 'premium', False),
                        'extracted_at': datetime.now().isoformat()
                    })
            
            print(f"   Valid members (excluding bots/deleted): {len(self.members)}")
            return len(self.members)
            
        except Exception as e:
            print(f"❌ Error extracting members: {e}")
            return 0
    
    def save_to_csv(self, filename: str = 'members.csv') -> str:
        """Save extracted members to CSV file"""
        if not self.members:
            print("⚠️  No members to save")
            return ""
        
        # Create exports directory
        exports_dir = Path('exports')
        exports_dir.mkdir(exist_ok=True)
        
        # Generate timestamped filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        timestamped_file = exports_dir / f"members_{timestamp}.csv"
        
        # Write main file
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=self.members[0].keys())
            writer.writeheader()
            writer.writerows(self.members)
        
        # Write timestamped backup
        with open(timestamped_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=self.members[0].keys())
            writer.writeheader()
            writer.writerows(self.members)
        
        print(f"\n💾 Saved to:")
        print(f"   Main file: {filename}")
        print(f"   Backup: {timestamped_file}")
        
        return filename
    
    async def run(self, aggressive: bool = False):
        """Main execution flow"""
        try:
            # Connect to Telegram
            if not await self.connect():
                return
            
            # List available groups
            groups = await self.list_groups()
            
            if not groups:
                print("❌ No groups found")
                return
            
            # Display groups
            print("\n" + "="*60)
            print("AVAILABLE GROUPS")
            print("="*60)
            for i, group in enumerate(groups, 1):
                print(f"[{i}] {group['title']}")
                print(f"    ID: {group['id']}")
                print(f"    Type: {group['type']}")
                print(f"    Members: {group['members']}")
                print()
            
            # Select group
            while True:
                try:
                    choice = input("Select group number (or 'q' to quit): ").strip()
                    if choice.lower() == 'q':
                        print("👋 Exiting...")
                        return
                    
                    idx = int(choice) - 1
                    if 0 <= idx < len(groups):
                        selected_group = groups[idx]
                        break
                    else:
                        print("❌ Invalid selection. Try again.")
                except ValueError:
                    print("❌ Please enter a number or 'q'")
            
            print(f"\n✅ Selected: {selected_group['title']}")
            
            # Extract members
            count = await self.extract_members(selected_group['id'], aggressive)
            
            if count > 0:
                # Save to CSV
                self.save_to_csv()
                print(f"\n🎉 Successfully exported {count} members!")
            else:
                print("\n⚠️  No members extracted")
                
        except Exception as e:
            print(f"\n❌ Fatal error: {e}")
        finally:
            await self.client.disconnect()

async def main():
    parser = argparse.ArgumentParser(description='Extract Telegram group members')
    parser.add_argument('--aggressive', action='store_true', 
                       help='Use aggressive extraction (faster but may hit rate limits)')
    args = parser.parse_args()
    
    print("🚀 Telegram Member Extractor")
    print("="*30)
    
    extractor = MemberExtractor()
    await extractor.run(aggressive=args.aggressive)

if __name__ == '__main__':
    asyncio.run(main())