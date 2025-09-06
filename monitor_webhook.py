#!/usr/bin/env python3
"""Monitor webhook configuration and auto-fix if broken"""

import asyncio
import sys
import os
from datetime import datetime

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def monitor_webhook():
    """Monitor and fix webhook configuration"""
    from app.config import settings
    from app.bot import bot
    from app.webhook_config import REQUIRED_WEBHOOK_UPDATES, validate_webhook_updates, get_critical_updates
    
    print("=" * 60)
    print("WEBHOOK CONFIGURATION MONITOR")
    print("=" * 60)
    print(f"Started at: {datetime.now()}")
    
    try:
        # Get current webhook info
        info = await bot.get_webhook_info()
        
        print(f"\n📍 Current Webhook:")
        print(f"   URL: {info.url or 'NOT SET'}")
        print(f"   Allowed updates: {info.allowed_updates or 'DEFAULT (all)'}")
        print(f"   Pending updates: {info.pending_update_count}")
        
        # Validate configuration
        is_valid, missing = validate_webhook_updates(info.allowed_updates)
        
        if is_valid:
            print(f"\n✅ WEBHOOK CONFIGURATION IS CORRECT")
            print(f"   All {len(REQUIRED_WEBHOOK_UPDATES)} required updates are enabled")
        else:
            print(f"\n❌ WEBHOOK CONFIGURATION IS BROKEN")
            print(f"   Missing updates: {missing}")
            
            # Check for critical revenue-blocking updates
            critical = get_critical_updates()
            critical_missing = [u for u in missing if u in critical]
            
            if critical_missing:
                print(f"\n🚨 CRITICAL REVENUE-BLOCKING UPDATES MISSING: {critical_missing}")
                print("   - chat_join_request: Users can't join the group")
                print("   - successful_payment: Payments won't be processed")
            
            # Auto-fix
            print(f"\n🔧 AUTO-FIXING WEBHOOK...")
            await bot.delete_webhook(drop_pending_updates=False)
            
            result = await bot.set_webhook(
                url=settings.webhook_url,
                allowed_updates=REQUIRED_WEBHOOK_UPDATES,
                drop_pending_updates=False,
                secret_token=settings.effective_telegram_secret
            )
            
            if result:
                # Verify fix
                info = await bot.get_webhook_info()
                is_valid, still_missing = validate_webhook_updates(info.allowed_updates)
                
                if is_valid:
                    print(f"✅ WEBHOOK FIXED SUCCESSFULLY")
                    print(f"   New allowed_updates: {info.allowed_updates}")
                else:
                    print(f"❌ WEBHOOK FIX FAILED")
                    print(f"   Still missing: {still_missing}")
                    print(f"   MANUAL INTERVENTION REQUIRED!")
            else:
                print(f"❌ Failed to set webhook")
        
        # Show required configuration for reference
        print(f"\n📋 Required Webhook Configuration:")
        print(f"   URL: {settings.webhook_url}")
        print(f"   Updates: {REQUIRED_WEBHOOK_UPDATES}")
        print(f"   Critical: {get_critical_updates()}")
        
        await bot.session.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("Starting webhook monitor...")
    asyncio.run(monitor_webhook())