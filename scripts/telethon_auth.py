#!/usr/bin/env python3
"""
Interactive Telethon authentication helper
Run this first to create a session file, then use the main seeding script
"""

import asyncio
import os
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from dotenv import load_dotenv

load_dotenv()

async def authenticate():
    api_id = os.getenv('TELETHON_API_ID', '28661564')
    api_hash = os.getenv('TELETHON_API_HASH', '177feaf3caf64cd8d89613ce7d5d3a83')
    phone = os.getenv('TELETHON_PHONE', '+447859838833')
    
    session_file = 'scripts/whitelist_seeder.session'
    
    print("="*60)
    print("TELETHON AUTHENTICATION")
    print("="*60)
    print(f"API ID: {api_id}")
    print(f"API Hash: {api_hash[:10]}...")
    print(f"Phone: {phone[:6]}***{phone[-2:]}")
    print(f"Session file: {session_file}")
    print("="*60)
    
    client = TelegramClient(session_file, api_id, api_hash)
    
    await client.start(phone=phone)
    
    if await client.is_user_authorized():
        me = await client.get_me()
        print(f"\n✅ Already authorized as: {me.first_name} (@{me.username or 'no_username'})")
        print(f"User ID: {me.id}")
    else:
        print("\n⚠️ New authorization required")
        print("Check your Telegram app for the login code")
    
    await client.disconnect()
    print("\nSession saved. You can now run the seeding script.")

if __name__ == "__main__":
    asyncio.run(authenticate())