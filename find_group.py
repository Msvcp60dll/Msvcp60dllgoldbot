#!/usr/bin/env python3
"""Find a specific group by searching for keywords"""

import asyncio
from pyrogram import Client

API_ID = 28661564
API_HASH = "177feaf3caf64cd8d89613ce7d5d3a83"

async def find_group():
    app = Client("member_extractor", api_id=API_ID, api_hash=API_HASH)
    await app.start()
    
    me = await app.get_me()
    print(f"✅ Logged in as: {me.first_name} (@{me.username})")
    
    print("\n📋 Looking for premium/paid groups...")
    print("="*60)
    
    count = 0
    target_keywords = ['premium', 'paid', 'vip', 'gold', 'star', 'member', 'exclusive']
    
    async for dialog in app.get_dialogs(limit=50):  # Only check first 50
        if dialog.chat.type in ['group', 'supergroup', 'channel']:
            title = (dialog.chat.title or '').lower()
            
            # Check if title contains any target keywords
            if any(keyword in title for keyword in target_keywords) or count < 10:
                count += 1
                print(f"\n[{count}] {dialog.chat.title}")
                print(f"    ID: {dialog.chat.id}")
                print(f"    Type: {dialog.chat.type}")
                print(f"    Members: {getattr(dialog.chat, 'members_count', 'Unknown')}")
                
                if count >= 15:  # Stop after finding 15 groups
                    break
    
    print(f"\n📊 Found {count} potential groups")
    print("\nWhich group ID would you like to extract members from?")
    print("Copy the ID from above and use it in the extraction script.")
    
    await app.stop()

if __name__ == "__main__":
    asyncio.run(find_group())