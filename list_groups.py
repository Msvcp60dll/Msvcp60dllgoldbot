#!/usr/bin/env python3
"""List all available groups"""

import asyncio
from pyrogram import Client

# Configuration
API_ID = 28661564
API_HASH = "177feaf3caf64cd8d89613ce7d5d3a83"

async def list_groups():
    app = Client(
        "member_extractor",
        api_id=API_ID,
        api_hash=API_HASH
    )
    
    await app.start()
    
    me = await app.get_me()
    print(f"✅ Logged in as: {me.first_name} (@{me.username})")
    
    print("\n" + "="*60)
    print("AVAILABLE GROUPS/CHANNELS")
    print("="*60)
    
    groups = []
    async for dialog in app.get_dialogs():
        if dialog.chat.type in ['group', 'supergroup', 'channel']:
            groups.append({
                'title': dialog.chat.title or 'Unknown',
                'id': dialog.chat.id,
                'type': dialog.chat.type,
                'members': getattr(dialog.chat, 'members_count', 'Unknown')
            })
    
    # Sort by member count (if available)
    groups.sort(key=lambda x: x.get('members', 0) if isinstance(x.get('members'), int) else 0, reverse=True)
    
    for i, group in enumerate(groups, 1):
        print(f"\n[{i}] {group['title']}")
        print(f"    ID: {group['id']}")
        print(f"    Type: {group['type']}")
        print(f"    Members: {group['members']}")
    
    print(f"\n📊 Total groups/channels: {len(groups)}")
    
    await app.stop()

if __name__ == "__main__":
    asyncio.run(list_groups())