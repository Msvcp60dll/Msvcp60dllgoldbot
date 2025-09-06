#!/usr/bin/env python3
"""
Simple Telegram Member Exporter - Waits for manual code input
"""

import os
import sys
import csv
from datetime import datetime
from pathlib import Path
from telethon.sync import TelegramClient
from telethon.tl.functions.channels import GetParticipantsRequest
from telethon.tl.types import ChannelParticipantsSearch
from dotenv import load_dotenv

# Load environment
load_dotenv()

API_ID = int(os.getenv('TG_API_ID', ''))
API_HASH = os.getenv('TG_API_HASH', '')
PHONE = os.getenv('TG_PHONE', '')

print("🚀 Simple Telegram Member Exporter")
print("="*40)
print(f"Phone: {PHONE}")
print(f"API ID: {API_ID}")
print()

# Create client
client = TelegramClient('telethon_session', API_ID, API_HASH)

# Start client
client.connect()

if not client.is_user_authorized():
    print("📲 Sending authentication code...")
    client.send_code_request(PHONE)
    
    print("\n" + "="*60)
    print("⚠️  CHECK YOUR TELEGRAM APP FOR THE LOGIN CODE")
    print("="*60)
    print("\nThe script will now wait for you to enter the code.")
    print("Please enter the code when ready.\n")
    
    # This will block waiting for input
    code = input("Enter code: ")
    
    try:
        client.sign_in(PHONE, code)
        print("✅ Authentication successful!")
    except Exception as e:
        print(f"❌ Authentication failed: {e}")
        client.disconnect()
        sys.exit(1)

# Get current user
me = client.get_me()
print(f"\n✅ Logged in as: {me.first_name} (@{me.username or 'No username'})")

# Get all dialogs
print("\n📋 Fetching your groups...")
dialogs = client.get_dialogs()

groups = []
for dialog in dialogs:
    if dialog.is_group or dialog.is_channel:
        entity = dialog.entity
        groups.append({
            'idx': len(groups) + 1,
            'id': entity.id,
            'title': entity.title,
            'type': 'Channel' if dialog.is_channel else 'Group',
            'members': getattr(entity, 'participants_count', 'Unknown')
        })

# Display groups
print("\n" + "="*60)
print("AVAILABLE GROUPS")
print("="*60)
for group in groups:
    print(f"[{group['idx']}] {group['title']}")
    print(f"    ID: {group['id']}")
    print(f"    Type: {group['type']}")
    print(f"    Members: {group['members']}")
    print()

# Select group
while True:
    choice = input("Select group number: ").strip()
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(groups):
            selected = groups[idx]
            break
    except:
        pass
    print("Invalid selection. Try again.")

print(f"\n✅ Selected: {selected['title']}")

# Get the group
group = client.get_entity(selected['id'])

# Extract members
print(f"\n📥 Extracting members from: {group.title}")
all_participants = []
offset = 0
limit = 200

while True:
    participants = client(GetParticipantsRequest(
        group, ChannelParticipantsSearch(''), offset, limit, hash=0
    ))
    
    if not participants.users:
        break
    
    all_participants.extend(participants.users)
    offset += len(participants.users)
    print(f"   Extracted {offset} members...", end='\r')

print(f"\n✅ Total members extracted: {len(all_participants)}")

# Process members
members = []
for user in all_participants:
    if not user.deleted and not user.bot:
        members.append({
            'user_id': user.id,
            'username': user.username or '',
            'first_name': user.first_name or '',
            'last_name': user.last_name or '',
            'phone': user.phone or '',
            'is_premium': getattr(user, 'premium', False),
            'extracted_at': datetime.now().isoformat()
        })

print(f"   Valid members (excluding bots/deleted): {len(members)}")

# Save to CSV
if members:
    # Create exports directory
    Path('exports').mkdir(exist_ok=True)
    
    # Main file
    filename = 'members.csv'
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=members[0].keys())
        writer.writeheader()
        writer.writerows(members)
    
    # Timestamped backup
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = f"exports/members_{timestamp}.csv"
    with open(backup_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=members[0].keys())
        writer.writeheader()
        writer.writerows(members)
    
    print(f"\n💾 Saved to:")
    print(f"   Main: {filename}")
    print(f"   Backup: {backup_file}")
    print(f"\n🎉 Successfully exported {len(members)} members!")

# Disconnect
client.disconnect()
print("\n👋 Done!")