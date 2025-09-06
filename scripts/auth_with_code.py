#!/usr/bin/env python3
"""
Authenticate with Telethon using provided code
"""

import asyncio
import os
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from dotenv import load_dotenv

load_dotenv()

async def authenticate_with_code():
    api_id = 28661564
    api_hash = '177feaf3caf64cd8d89613ce7d5d3a83'
    phone = '+447859838833'
    code = '17195'
    
    session_file = 'scripts/whitelist_seeder.session'
    
    print("="*60)
    print("TELETHON AUTHENTICATION WITH CODE")
    print("="*60)
    
    client = TelegramClient(session_file, api_id, api_hash)
    
    await client.connect()
    
    if not await client.is_user_authorized():
        try:
            print(f"Signing in with code: {code}")
            await client.sign_in(phone, code)
            print("✅ Successfully authenticated!")
        except SessionPasswordNeededError:
            print("⚠️ Two-factor authentication is enabled")
            # Would need password here
        except Exception as e:
            print(f"❌ Authentication failed: {e}")
    
    if await client.is_user_authorized():
        me = await client.get_me()
        print(f"\n✅ Authorized as: {me.first_name} (@{me.username or 'no_username'})")
        print(f"User ID: {me.id}")
        print("\nSession saved successfully! You can now run the seeding script.")
    
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(authenticate_with_code())