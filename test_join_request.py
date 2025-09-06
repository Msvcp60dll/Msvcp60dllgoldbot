#!/usr/bin/env python3
"""Test join request handling by checking bot configuration"""

import asyncio
import os
import sys

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def test_join_request_config():
    """Test join request configuration"""
    from app.config import settings
    from app.bot import bot
    
    print("=" * 60)
    print("JOIN REQUEST CONFIGURATION TEST")
    print("=" * 60)
    
    try:
        # Get bot info
        me = await bot.get_me()
        print(f"\n✅ Bot: @{me.username} ({me.first_name})")
        print(f"   ID: {me.id}")
        print(f"   Can join groups: {me.can_join_groups}")
        print(f"   Can read all group messages: {me.can_read_all_group_messages}")
        
        # Check webhook
        webhook = await bot.get_webhook_info()
        print(f"\n📍 Webhook:")
        print(f"   URL: {webhook.url or 'NOT SET'}")
        print(f"   Allowed updates: {webhook.allowed_updates or 'ALL'}")
        
        has_join = "chat_join_request" in (webhook.allowed_updates or [])
        has_payment = "successful_payment" in (webhook.allowed_updates or [])
        
        print(f"\n🔍 Critical Updates:")
        print(f"   chat_join_request: {'✅ ENABLED' if has_join else '❌ MISSING - JOIN REQUESTS WONT WORK!'}")
        print(f"   successful_payment: {'✅ ENABLED' if has_payment else '❌ MISSING - PAYMENTS WONT WORK!'}")
        
        # Check group configuration
        print(f"\n📋 Group Configuration:")
        print(f"   Group ID: {settings.group_chat_id}")
        
        try:
            # Try to get chat info
            chat = await bot.get_chat(settings.group_chat_id)
            print(f"   Group Name: {chat.title}")
            print(f"   Type: {chat.type}")
            
            # Check bot membership
            try:
                member = await bot.get_chat_member(settings.group_chat_id, me.id)
                print(f"   Bot Status: {member.status}")
                
                if member.status == "administrator":
                    print(f"   Bot is Admin: ✅")
                    print(f"   Can invite users: {member.can_invite_users if hasattr(member, 'can_invite_users') else 'Unknown'}")
                    print(f"   Can restrict members: {member.can_restrict_members if hasattr(member, 'can_restrict_members') else 'Unknown'}")
                else:
                    print(f"   Bot is Admin: ❌ Bot must be admin!")
                    
            except Exception as e:
                print(f"   Bot Status: ❌ Cannot check - {e}")
                
        except Exception as e:
            print(f"   ❌ Cannot access group: {e}")
            print(f"   Make sure bot is added to the group!")
        
        # Test sending a message
        print(f"\n📤 Testing DM capability...")
        try:
            # Try to send to bot owner
            owner_id = settings.owner_ids[0] if settings.owner_ids else None
            if owner_id:
                await bot.send_message(owner_id, "🧪 Test message from join request debugging")
                print(f"   ✅ Can send DMs to owner ({owner_id})")
        except Exception as e:
            print(f"   ❌ Cannot send DMs: {e}")
        
        print("\n" + "=" * 60)
        print("DIAGNOSIS:")
        print("=" * 60)
        
        if not has_join:
            print("❌ CRITICAL: chat_join_request not in allowed_updates!")
            print("   FIX: Update webhook to include chat_join_request")
            
        if not has_payment:
            print("❌ CRITICAL: successful_payment not in allowed_updates!")
            print("   FIX: Update webhook to include successful_payment")
            
        if has_join and has_payment:
            print("✅ Webhook configuration looks correct")
            print("   If join requests still don't work, check:")
            print("   1. Bot is admin in the group")
            print("   2. Group has 'Approve new members' enabled")
            print("   3. Bot privacy settings in @BotFather")
            
        await bot.session.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_join_request_config())