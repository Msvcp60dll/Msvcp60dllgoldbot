#!/usr/bin/env python3
"""Test the join request DM functionality directly"""

import asyncio
import sys
import os
from datetime import datetime

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def test_join_request_dm():
    """Test sending payment DM to a user"""
    
    # Import after path setup
    from app.config import settings
    from app.bot import bot, setup_bot
    from app.routers.join import send_payment_offer
    from aiogram.types import User
    
    # Test user - you can change this to your test account
    test_user_id = 306145881  # Or use a test account ID
    
    try:
        # Setup bot
        await setup_bot()
        print("✅ Bot initialized")
        
        # Create a mock user object
        test_user = User(
            id=test_user_id,
            is_bot=False,
            first_name="Test",
            username="testuser",
            language_code="en"
        )
        
        print(f"\n🔧 Testing DM send to user {test_user_id}...")
        print(f"Bot username: @{(await bot.get_me()).username}")
        
        # Try to send the payment offer
        print("\n📤 Attempting to send payment offer DM...")
        
        try:
            await send_payment_offer(test_user)
            print("✅ Payment offer DM sent successfully!")
            print("\n✨ The user should have received:")
            print("   - Welcome message")
            print("   - Two payment options (one-time and subscription)")
            print("   - Instructions to use /enter after payment")
            
        except Exception as e:
            print(f"❌ Failed to send DM: {e}")
            print("\nPossible reasons:")
            print("1. Bot is blocked by the user")
            print("2. User has never interacted with the bot")
            print("3. Network/API issue")
            
        # Test direct message send
        print("\n📨 Testing direct message send...")
        try:
            await bot.send_message(
                chat_id=test_user_id,
                text="🧪 Test message from join request handler debug"
            )
            print("✅ Direct test message sent!")
        except Exception as e:
            print(f"❌ Direct message failed: {e}")
            
        # Close bot session
        await bot.session.close()
        print("\n✅ Test completed")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        try:
            await bot.session.close()
        except:
            pass

if __name__ == "__main__":
    print("🚀 Testing Join Request DM Functionality")
    print("=" * 50)
    asyncio.run(test_join_request_dm())