#!/usr/bin/env python3
"""
Manually set the Telegram webhook for the bot
"""
import asyncio
import aiohttp
import sys

BOT_TOKEN = "8263837787:AAE_kJD3YYM5L_7Hd28uCkgvvjqxFylCIWQ"
WEBHOOK_URL = "https://msvcp60dll-bot-production.up.railway.app/webhook/railway_webhook_secret_2024"

async def check_webhook():
    """Check current webhook status"""
    async with aiohttp.ClientSession() as session:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/getWebhookInfo"
        async with session.get(url) as response:
            data = await response.json()
            print("Current webhook info:")
            print(f"  URL: {data['result'].get('url', 'Not set')}")
            print(f"  Pending updates: {data['result'].get('pending_update_count', 0)}")
            print(f"  Last error: {data['result'].get('last_error_message', 'None')}")
            return data['result']

async def delete_webhook():
    """Delete existing webhook"""
    async with aiohttp.ClientSession() as session:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook"
        async with session.post(url, json={"drop_pending_updates": True}) as response:
            data = await response.json()
            if data['ok']:
                print("✅ Webhook deleted successfully")
            else:
                print(f"❌ Failed to delete webhook: {data}")
            return data['ok']

async def set_webhook():
    """Set new webhook"""
    async with aiohttp.ClientSession() as session:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook"
        payload = {
            "url": WEBHOOK_URL,
            "allowed_updates": [
                "message",
                "callback_query",
                "chat_join_request",
                "chat_member",
                "pre_checkout_query"
            ],
            "drop_pending_updates": True
        }
        async with session.post(url, json=payload) as response:
            data = await response.json()
            if data['ok']:
                print(f"✅ Webhook set successfully to: {WEBHOOK_URL}")
            else:
                print(f"❌ Failed to set webhook: {data}")
            return data['ok']

async def test_bot():
    """Get bot info"""
    async with aiohttp.ClientSession() as session:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/getMe"
        async with session.get(url) as response:
            data = await response.json()
            if data['ok']:
                bot_info = data['result']
                print(f"✅ Bot connected: @{bot_info['username']}")
                print(f"   Name: {bot_info['first_name']}")
                print(f"   ID: {bot_info['id']}")
            else:
                print(f"❌ Failed to connect to bot: {data}")
            return data.get('result')

async def main():
    print("🤖 Telegram Bot Webhook Setup")
    print("=" * 40)
    
    # Test bot connection
    bot_info = await test_bot()
    if not bot_info:
        print("❌ Cannot connect to bot. Check BOT_TOKEN.")
        sys.exit(1)
    
    print("\n" + "=" * 40)
    
    # Check current webhook
    webhook_info = await check_webhook()
    
    print("\n" + "=" * 40)
    
    # If webhook is not set or different, update it
    if webhook_info.get('url') != WEBHOOK_URL:
        print("\n🔄 Updating webhook...")
        
        # Delete old webhook
        await delete_webhook()
        
        # Set new webhook
        await asyncio.sleep(1)
        success = await set_webhook()
        
        if success:
            # Verify it was set
            await asyncio.sleep(1)
            await check_webhook()
    else:
        print("\n✅ Webhook is already correctly configured!")
    
    print("\n" + "=" * 40)
    print("✨ Setup complete!")
    print(f"\nYour bot @{bot_info['username']} should now respond to:")
    print("  /start - Start interaction")
    print("  /help - Get help")
    print("  /status - Check subscription status")
    print("\nTest it in Telegram now!")

if __name__ == "__main__":
    asyncio.run(main())