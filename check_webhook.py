#!/usr/bin/env python3
"""Check the webhook configuration directly via Telegram API"""

import asyncio
import sys
import os

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def check_webhook():
    """Check webhook configuration"""
    from app.config import settings
    from app.bot import bot, setup_bot
    
    try:
        # Initialize bot without setting webhook
        await bot.delete_webhook(drop_pending_updates=False)
        
        # Get current webhook info
        info = await bot.get_webhook_info()
        
        print("=" * 60)
        print("WEBHOOK CONFIGURATION CHECK")
        print("=" * 60)
        
        print(f"\n📍 Webhook URL: {info.url or 'NOT SET'}")
        print(f"🔧 Expected URL: {settings.webhook_url}")
        
        print(f"\n📋 Allowed Updates: {info.allowed_updates or 'DEFAULT (all)'}")
        
        critical_updates = ["chat_join_request", "pre_checkout_query", "successful_payment"]
        if info.allowed_updates:
            print("\n✅ Present:")
            for update in info.allowed_updates:
                status = "⚠️ CRITICAL" if update in critical_updates else ""
                print(f"   - {update} {status}")
            
            print("\n❌ Missing:")
            all_updates = [
                "message", "edited_message", "channel_post", "edited_channel_post",
                "inline_query", "chosen_inline_result", "callback_query",
                "shipping_query", "pre_checkout_query", "poll", "poll_answer",
                "my_chat_member", "chat_member", "chat_join_request", "successful_payment"
            ]
            missing = [u for u in all_updates if u not in info.allowed_updates]
            for update in missing:
                status = "🚨 CRITICAL - REVENUE BLOCKED!" if update in critical_updates else ""
                print(f"   - {update} {status}")
        
        print(f"\n📊 Statistics:")
        print(f"   Pending updates: {info.pending_update_count}")
        print(f"   Max connections: {info.max_connections}")
        
        if info.last_error_date:
            print(f"\n⚠️ Last Error:")
            print(f"   Date: {info.last_error_date}")
            print(f"   Message: {info.last_error_message}")
        
        print("\n" + "=" * 60)
        
        # Now set the webhook correctly
        if not info.url or "chat_join_request" not in (info.allowed_updates or []):
            print("\n🔧 FIXING WEBHOOK CONFIGURATION...")
            
            await bot.set_webhook(
                url=settings.webhook_url,
                allowed_updates=[
                    "message",
                    "callback_query", 
                    "chat_join_request",  # CRITICAL!
                    "chat_member",
                    "pre_checkout_query",
                    "successful_payment"  # CRITICAL!
                ],
                drop_pending_updates=False,
                secret_token=settings.effective_telegram_secret
            )
            
            # Verify fix
            info = await bot.get_webhook_info()
            if "chat_join_request" in (info.allowed_updates or []):
                print("✅ WEBHOOK FIXED! Join requests should now work.")
            else:
                print("❌ WEBHOOK FIX FAILED! Manual intervention needed.")
        
        await bot.session.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(check_webhook())