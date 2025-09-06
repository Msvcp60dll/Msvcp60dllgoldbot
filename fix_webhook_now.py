#!/usr/bin/env python3
"""EMERGENCY: Fix the webhook configuration NOW"""

import asyncio
import os
import sys

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def fix_webhook_now():
    """Fix webhook configuration immediately"""
    from app.config import settings
    from app.bot import bot
    
    print("🚨 EMERGENCY WEBHOOK FIX")
    print("=" * 60)
    
    try:
        # Get current status
        info = await bot.get_webhook_info()
        print(f"Current webhook URL: {info.url}")
        print(f"Current allowed_updates: {info.allowed_updates}")
        
        # Delete and reset webhook with ALL required updates
        print("\n🔧 Fixing webhook configuration...")
        await bot.delete_webhook(drop_pending_updates=False)
        
        # Set webhook with ALL critical updates
        result = await bot.set_webhook(
            url=settings.webhook_url,
            allowed_updates=[
                "message",
                "callback_query",
                "chat_join_request",     # CRITICAL for join requests
                "chat_member", 
                "pre_checkout_query",
                "successful_payment"     # CRITICAL for payments
            ],
            drop_pending_updates=False,  # Don't lose pending updates
            secret_token=settings.effective_telegram_secret
        )
        
        print(f"Set webhook result: {result}")
        
        # Verify the fix
        info = await bot.get_webhook_info()
        print(f"\n✅ NEW webhook URL: {info.url}")
        print(f"✅ NEW allowed_updates: {info.allowed_updates}")
        
        # Check critical updates
        critical = ["chat_join_request", "successful_payment"]
        missing = [u for u in critical if u not in (info.allowed_updates or [])]
        
        if missing:
            print(f"\n❌ STILL MISSING CRITICAL UPDATES: {missing}")
            print("MANUAL INTERVENTION REQUIRED!")
        else:
            print("\n✅ ALL CRITICAL UPDATES ENABLED!")
            print("✅ Join requests will now trigger handlers")
            print("✅ Payments will now be processed")
            
        await bot.session.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(fix_webhook_now())