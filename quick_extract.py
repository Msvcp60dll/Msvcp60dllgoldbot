#!/usr/bin/env python3
"""Quick member extraction with provided code"""

import asyncio
from pyrogram import Client
from pyrogram.errors import SessionPasswordNeeded
import csv
from datetime import datetime

# Configuration
API_ID = 28661564
API_HASH = "177feaf3caf64cd8d89613ce7d5d3a83"
PHONE = "+447859838833"
GROUP_ID = -1002384609739
AUTH_CODE = "26769"

async def extract():
    app = Client(
        "member_extractor",
        api_id=API_ID,
        api_hash=API_HASH,
        phone_number=PHONE
    )
    
    await app.start()
    
    # If we need to authenticate
    if not await app.get_me():
        print("Authenticating with code:", AUTH_CODE)
        try:
            await app.sign_in(PHONE, AUTH_CODE)
        except SessionPasswordNeeded:
            print("2FA password required - skipping for now")
            return
    
    # Get current user
    me = await app.get_me()
    print(f"✅ Logged in as: {me.first_name} (@{me.username})")
    
    # Get group
    try:
        chat = await app.get_chat(GROUP_ID)
        print(f"\n📋 Group: {chat.title}")
        print(f"   ID: {chat.id}")
        print(f"   Members: {chat.members_count}")
        
        # Extract members
        print("\n📥 Extracting members...")
        members = []
        async for member in app.get_chat_members(GROUP_ID):
            if member.user and not member.user.is_bot and not member.user.is_deleted:
                members.append({
                    'user_id': member.user.id,
                    'username': member.user.username or '',
                    'first_name': member.user.first_name or '',
                    'last_name': member.user.last_name or '',
                    'is_premium': member.user.is_premium or False,
                    'extracted_at': datetime.now().isoformat()
                })
                if len(members) % 100 == 0:
                    print(f"   Extracted {len(members)} members...", end='\r')
        
        print(f"\n✅ Extracted {len(members)} valid members")
        
        # Save to CSV
        if members:
            filename = 'members.csv'
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=members[0].keys())
                writer.writeheader()
                writer.writerows(members)
            
            # Backup
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup = f"members_{timestamp}.csv"
            with open(backup, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=members[0].keys())
                writer.writeheader()
                writer.writerows(members)
            
            print(f"\n💾 Saved to:")
            print(f"   Main: {filename}")
            print(f"   Backup: {backup}")
            print(f"\n🎉 Successfully exported {len(members)} members!")
            
    except Exception as e:
        print(f"❌ Error: {e}")
    
    await app.stop()

if __name__ == "__main__":
    asyncio.run(extract())