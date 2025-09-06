#!/usr/bin/env python3
"""Extract members from Msvcp60dll group"""

import asyncio
from pyrogram import Client
import csv
from datetime import datetime

API_ID = 28661564
API_HASH = "177feaf3caf64cd8d89613ce7d5d3a83"
GROUP_ID = -1002384619733  # Msvcp60dll group

async def extract():
    app = Client("member_extractor", api_id=API_ID, api_hash=API_HASH)
    await app.start()
    
    me = await app.get_me()
    print(f"✅ Logged in as: {me.first_name} (@{me.username})")
    
    # Get group info
    try:
        chat = await app.get_chat(GROUP_ID)
        print(f"\n📋 Group: {chat.title}")
        print(f"   ID: {chat.id}")
        print(f"   Type: {chat.type}")
        print(f"   Members: {getattr(chat, 'members_count', 'Unknown')}")
        
        # Extract members
        print("\n📥 Extracting members...")
        members = []
        count = 0
        
        async for member in app.get_chat_members(GROUP_ID):
            count += 1
            if count % 100 == 0:
                print(f"   Processing {count} members...", end='\r')
            
            user = member.user
            if user and not user.is_bot and not user.is_deleted:
                members.append({
                    'user_id': user.id,
                    'username': user.username or '',
                    'first_name': user.first_name or '',
                    'last_name': user.last_name or '',
                    'is_premium': user.is_premium or False,
                    'status': member.status.value if hasattr(member.status, 'value') else str(member.status),
                    'joined_date': member.joined_date.isoformat() if member.joined_date else '',
                    'extracted_at': datetime.now().isoformat()
                })
        
        print(f"\n✅ Total processed: {count}")
        print(f"   Valid members: {len(members)}")
        print(f"   Bots/deleted skipped: {count - len(members)}")
        
        # Save to CSV
        if members:
            # Main file
            filename = 'members.csv'
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=members[0].keys())
                writer.writeheader()
                writer.writerows(members)
            
            # Timestamped backup
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup = f"members_{timestamp}.csv"
            with open(backup, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=members[0].keys())
                writer.writeheader()
                writer.writerows(members)
            
            print(f"\n💾 Files saved:")
            print(f"   Main: {filename}")
            print(f"   Backup: {backup}")
            
            # Show sample
            print(f"\n📊 Sample of extracted members:")
            for i, m in enumerate(members[:5], 1):
                print(f"   {i}. {m['first_name']} {m['last_name']} (@{m['username']}) - ID: {m['user_id']}")
            
            print(f"\n🎉 Successfully exported {len(members)} members!")
            
    except Exception as e:
        print(f"❌ Error: {e}")
    
    await app.stop()

if __name__ == "__main__":
    asyncio.run(extract())