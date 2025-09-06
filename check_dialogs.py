#!/usr/bin/env python3
"""Check all dialogs"""

import asyncio
from pyrogram import Client

API_ID = 28661564
API_HASH = "177feaf3caf64cd8d89613ce7d5d3a83"

async def check():
    app = Client("member_extractor", api_id=API_ID, api_hash=API_HASH)
    await app.start()
    
    me = await app.get_me()
    print(f"✅ Logged in as: {me.first_name} (@{me.username})")
    print(f"   User ID: {me.id}")
    print(f"   Premium: {me.is_premium}")
    
    print("\n📋 Checking all dialogs...")
    print("="*60)
    
    all_count = 0
    groups = []
    channels = []
    private = []
    bots = []
    
    async for dialog in app.get_dialogs():
        all_count += 1
        chat = dialog.chat
        
        if chat.type == 'private':
            if hasattr(chat, 'is_bot') and chat.is_bot:
                bots.append(chat.title or chat.first_name)
            else:
                private.append(chat.title or chat.first_name)
        elif chat.type == 'group':
            groups.append((chat.title, chat.id))
        elif chat.type == 'supergroup':
            groups.append((chat.title, chat.id))
        elif chat.type == 'channel':
            channels.append((chat.title, chat.id))
        
        # Show first 10 of any type
        if all_count <= 10:
            print(f"{all_count}. {chat.title or chat.first_name} (Type: {chat.type}, ID: {chat.id})")
    
    print(f"\n📊 Summary:")
    print(f"   Total dialogs: {all_count}")
    print(f"   Private chats: {len(private)}")
    print(f"   Bots: {len(bots)}")
    print(f"   Groups/Supergroups: {len(groups)}")
    print(f"   Channels: {len(channels)}")
    
    if groups:
        print(f"\n📌 Groups found:")
        for title, chat_id in groups[:10]:
            print(f"   - {title} (ID: {chat_id})")
    
    if channels:
        print(f"\n📢 Channels found:")
        for title, chat_id in channels[:10]:
            print(f"   - {title} (ID: {chat_id})")
    
    await app.stop()

if __name__ == "__main__":
    asyncio.run(check())