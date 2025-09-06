#!/usr/bin/env python3
"""Show all groups/channels"""

import asyncio
from pyrogram import Client

API_ID = 28661564
API_HASH = "177feaf3caf64cd8d89613ce7d5d3a83"

async def show_all():
    app = Client("member_extractor", api_id=API_ID, api_hash=API_HASH)
    await app.start()
    
    me = await app.get_me()
    print(f"✅ Logged in as: {me.first_name} (@{me.username})")
    
    print("\n📋 ALL GROUPS/CHANNELS:")
    print("="*60)
    
    count = 0
    groups_list = []
    
    async for dialog in app.get_dialogs(limit=100):
        if dialog.chat.type in ['group', 'supergroup', 'channel']:
            count += 1
            info = {
                'num': count,
                'title': dialog.chat.title or 'Unknown',
                'id': dialog.chat.id,
                'type': dialog.chat.type,
                'members': getattr(dialog.chat, 'members_count', None)
            }
            groups_list.append(info)
            
            print(f"\n[{count}] {info['title']}")
            print(f"    ID: {info['id']}")
            print(f"    Type: {info['type']}")
            if info['members']:
                print(f"    Members: {info['members']}")
    
    print(f"\n📊 Total: {count} groups/channels")
    
    # Save to file for reference
    with open('groups_list.txt', 'w', encoding='utf-8') as f:
        f.write("TELEGRAM GROUPS/CHANNELS LIST\n")
        f.write("="*60 + "\n\n")
        for g in groups_list:
            f.write(f"[{g['num']}] {g['title']}\n")
            f.write(f"    ID: {g['id']}\n")
            f.write(f"    Type: {g['type']}\n")
            if g['members']:
                f.write(f"    Members: {g['members']}\n")
            f.write("\n")
    
    print("\n💾 Saved full list to: groups_list.txt")
    
    await app.stop()

if __name__ == "__main__":
    asyncio.run(show_all())