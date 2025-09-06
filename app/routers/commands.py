from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest
from datetime import datetime, timezone, timedelta
import logging
from app.config import settings
from app.db import db

logger = logging.getLogger(__name__)
router = Router()

@router.message(Command("test_dm"))
async def test_dm(message: Message):
    """Test if bot can send DMs"""
    user_id = message.from_user.id
    try:
        await message.bot.send_message(user_id, "✅ Test DM works! Bot can send you messages.")
        await message.answer("✅ DM sent successfully!")
        logger.info(f"Test DM sent successfully to user {user_id}")
    except Exception as e:
        await message.answer(f"❌ Cannot send DM: {str(e)}")
        logger.error(f"Cannot send DM to user {user_id}: {e}")

@router.message(Command("start"))
async def cmd_start(message: Message):
    """Handle /start command"""
    user_id = message.from_user.id
    
    # Upsert user
    await db.upsert_user(
        user_id=user_id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name,
        language_code=message.from_user.language_code
    )
    
    text = (
        f"👋 Welcome, {message.from_user.first_name}!\n\n"
        "This bot manages access to our exclusive group.\n\n"
        "Commands:\n"
        "/status - Check your subscription\n"
        "/enter - Join the group\n"
        "/cancel_sub - Cancel auto-renewal\n"
        "/help - Get help\n\n"
        "To join the group, request access and follow the payment instructions."
    )
    
    await message.answer(text)

@router.message(Command("paysupport"))
async def cmd_paysupport(message: Message):
    """Provide payment support instructions and notify owners"""
    user = message.from_user
    await db.log_event(user.id, "paysupport_requested", {})

    help_text = (
        "🛟 <b>Payment Support</b>\n\n"
        "If you had an issue with Stars payment or access:\n"
        "• Keep your Telegram receipt/charge ID\n"
        "• Try /enter to refresh access\n"
        "• If it still fails, reply here with details\n\n"
        "An admin will review shortly."
    )
    await message.answer(help_text)

    # Notify owners for follow-up (best-effort)
    try:
        from app.bot import bot
        owner_text = (
            f"🔔 Payment support request\n"
            f"User: {user.id} @{user.username or ''} {user.first_name or ''}\n"
            f"Message ID: {message.message_id}"
        )
        for owner_id in settings.owner_ids:
            try:
                await bot.send_message(owner_id, owner_text)
            except Exception:
                pass
    except Exception:
        pass

@router.message(Command("status"))
async def cmd_status(message: Message):
    """Check subscription status"""
    user_id = message.from_user.id
    
    subscription = await db.get_active_subscription(user_id)
    
    if not subscription:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"💎 Get Access ({settings.plan_stars} Stars)",
                    callback_data="pay:one"
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"🔄 Subscribe ({settings.sub_stars} Stars/mo)",
                    url=f"{settings.webhook_host}/r/sub?u={user_id}&v=A&p={settings.sub_stars}"
                )
            ]
        ])
        
        await message.answer(
            "❌ You don't have an active subscription.\n\n"
            "Choose a plan to get access:",
            reply_markup=keyboard
        )
        return
    
    # Format status message
    status_emoji = "✅" if subscription['status'] == 'active' else "⏰"
    status_text = "Active" if subscription['status'] == 'active' else "Grace Period"
    
    expires_at = subscription.get('grace_until') or subscription.get('expires_at')
    if expires_at:
        expires_str = expires_at.strftime('%Y-%m-%d %H:%M UTC')
        time_left = expires_at - datetime.now(timezone.utc)
        days_left = time_left.days
        hours_left = time_left.seconds // 3600
        
        if days_left > 0:
            time_left_str = f"{days_left} days"
        elif hours_left > 0:
            time_left_str = f"{hours_left} hours"
        else:
            time_left_str = "Less than an hour"
    else:
        expires_str = "Unknown"
        time_left_str = "Unknown"
    
    text = (
        f"{status_emoji} <b>Subscription Status</b>\n\n"
        f"Status: {status_text}\n"
        f"Type: {'Recurring' if subscription['is_recurring'] else 'One-time'}\n"
        f"Expires: {expires_str}\n"
        f"Time left: {time_left_str}\n"
    )
    
    # Add buttons
    buttons = []
    
    # Enter button
    buttons.append([
        InlineKeyboardButton(text="🚪 Enter Group", callback_data="cmd:enter")
    ])
    
    # Extend/subscribe buttons
    if not subscription['is_recurring']:
        if subscription['status'] == 'grace':
            buttons.append([
                InlineKeyboardButton(
                    text=f"💎 Extend ({settings.plan_stars} Stars)",
                    callback_data="pay:one"
                )
            ])
        buttons.append([
            InlineKeyboardButton(
                text=f"🔄 Switch to Subscription ({settings.sub_stars} Stars/mo)",
                url=f"{settings.webhook_host}/r/sub?u={user_id}&v=A&p={settings.sub_stars}"
            )
        ])
    else:
        buttons.append([
            InlineKeyboardButton(text="❌ Cancel Auto-renewal", callback_data="cmd:cancel")
        ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer(text, reply_markup=keyboard)

@router.message(Command("enter"))
async def cmd_enter(message: Message):
    """Self-service group entry"""
    from app.bot import bot
    
    user_id = message.from_user.id
    
    # Check access
    if not await db.has_active_access(user_id):
        await message.answer(
            "❌ You don't have active access.\n"
            "Use /status to see available plans."
        )
        return
    
    # Try to approve pending join request
    try:
        await bot.approve_chat_join_request(
            chat_id=settings.group_chat_id,
            user_id=user_id
        )
        await message.answer("✅ Join request approved! You can now enter the group.")
        await db.log_event(user_id, "self_service_approve", {})
        return
    except TelegramBadRequest:
        pass  # No pending request, create invite link
    
    # Create single-use invite link
    try:
        expire_date = datetime.now(timezone.utc) + timedelta(minutes=settings.invite_ttl_min)
        invite_link = await bot.create_chat_invite_link(
            chat_id=settings.group_chat_id,
            creates_join_request=True,
            member_limit=1,
            expire_date=expire_date
        )
        
        await message.answer(
            f"🔗 <b>Personal invite link created!</b>\n\n"
            f"This link is valid for {settings.invite_ttl_min} minutes and can be used once:\n"
            f"{invite_link.invite_link}\n\n"
            f"After clicking, your join request will be auto-approved."
        )
        
        await db.log_event(user_id, "invite_link_created", {
            "expire_minutes": settings.invite_ttl_min
        })
        
    except Exception as e:
        logger.error(f"Failed to create invite link for user {user_id}: {e}")
        await message.answer(
            "❌ Failed to create invite link. Please try again later or contact support."
        )

@router.message(Command("cancel_sub"))
async def cmd_cancel_sub(message: Message):
    """Cancel subscription auto-renewal"""
    from app.bot import bot
    
    user_id = message.from_user.id
    
    # Check if user has recurring subscription
    subscription = await db.get_active_subscription(user_id)
    
    if not subscription or not subscription['is_recurring']:
        await message.answer(
            "❌ You don't have an active recurring subscription.\n"
            "Nothing to cancel."
        )
        return
    
    # Get charge_id from recurring_subs
    charge_id = await db.fetchval("""
        SELECT charge_id FROM recurring_subs WHERE user_id = $1
    """, user_id)
    
    if not charge_id:
        await message.answer(
            "❌ Cannot find your subscription details.\n"
            "Please contact support."
        )
        return
    
    try:
        # Cancel via Telegram API
        result = await bot.refund_star_payment(
            user_id=user_id,
            telegram_payment_charge_id=charge_id
        )
        
        # Update subscription
        await db.execute("""
            UPDATE subscriptions
            SET is_recurring = false,
                cancelled_at = NOW()
            WHERE user_id = $1 AND status IN ('active', 'grace')
        """, user_id)
        
        await message.answer(
            "✅ <b>Auto-renewal cancelled!</b>\n\n"
            f"Your access remains active until {subscription['expires_at'].strftime('%Y-%m-%d')}.\n"
            "After that, you can purchase a new pass if you wish to continue."
        )
        
        await db.log_event(user_id, "subscription_cancelled", {})
        
    except Exception as e:
        logger.error(f"Failed to cancel subscription for user {user_id}: {e}")
        
        # Still mark as cancelled in DB
        await db.execute("""
            UPDATE subscriptions
            SET is_recurring = false,
                cancelled_at = NOW()
            WHERE user_id = $1 AND status IN ('active', 'grace')
        """, user_id)
        
        await message.answer(
            "✅ Auto-renewal has been disabled.\n"
            f"Your access remains active until {subscription['expires_at'].strftime('%Y-%m-%d')}."
        )

@router.message(Command("stats"))
async def cmd_stats(message: Message):
    """Show statistics (owners only)"""
    user_id = message.from_user.id
    
    if not settings.is_owner(user_id):
        await message.answer("❌ This command is for bot owners only.")
        return
    
    stats = await db.get_stats()
    
    # Calculate MRR (Monthly Recurring Revenue)
    mrr = stats.get('recurring_subs', 0) * settings.sub_stars
    
    text = (
        "📊 <b>Bot Statistics</b>\n\n"
        f"<b>Users</b>\n"
        f"Total: {stats.get('total_users', 0)}\n"
        f"Active: {stats.get('active_users', 0)}\n\n"
        f"<b>Subscriptions</b>\n"
        f"Active: {stats.get('active_subs', 0)}\n"
        f"Grace: {stats.get('grace_subs', 0)}\n"
        f"Recurring: {stats.get('recurring_subs', 0)}\n\n"
        f"<b>Revenue</b>\n"
        f"Last 24h: {stats.get('revenue_24h', 0)} Stars\n"
        f"Last 30d: {stats.get('revenue_30d', 0)} Stars\n"
        f"MRR: {mrr} Stars\n\n"
        f"<b>Payments</b>\n"
        f"Last 24h: {stats.get('payments_24h', 0)}\n"
    )
    
    await message.answer(text)

@router.message(Command("help"))
async def cmd_help(message: Message):
    """Show help message"""
    text = (
        "ℹ️ <b>Help</b>\n\n"
        "<b>How to join the group:</b>\n"
        "1. Request to join the group\n"
        "2. Choose a payment plan in the bot\n"
        "3. Complete the payment\n"
        "4. Use /enter to get instant access\n\n"
        "<b>Commands:</b>\n"
        "/status - Check your subscription\n"
        "/enter - Join the group (if you have access)\n"
        "/cancel_sub - Disable auto-renewal\n"
        "/help - This message\n\n"
        "<b>Payment options:</b>\n"
        f"• One-time: {settings.plan_stars} Stars for {settings.plan_days} days\n"
        f"• Subscription: {settings.sub_stars} Stars/month (auto-renews)\n\n"
        "Questions? Contact the group admin."
    )
    
    await message.answer(text)

@router.callback_query(F.data == "cmd:enter")
async def callback_enter(callback: CallbackQuery):
    """Handle enter button from status"""
    await callback.message.delete()
    await cmd_enter(callback.message)

# ============= KICK CONTROL COMMANDS (OWNERS ONLY) =============

@router.message(Command("kicks_off"))
async def cmd_kicks_off(message: Message):
    """Disable kicks globally (owners only)"""
    user_id = message.from_user.id
    
    if not settings.is_owner(user_id):
        await message.answer("❌ This command is for bot owners only.")
        return
    
    success = await db.set_feature_flag('kick_enabled', False)
    if success:
        await message.answer(
            "🛡️ <b>Kicks DISABLED</b>\n\n"
            "The bot will NOT kick any users.\n"
            "All expired members are protected."
        )
        await db.log_event(user_id, "kicks_disabled", {})
    else:
        await message.answer("❌ Failed to disable kicks. Check database connection.")

@router.message(Command("kicks_on"))
async def cmd_kicks_on(message: Message):
    """Enable kicks globally (owners only)"""
    user_id = message.from_user.id
    
    if not settings.is_owner(user_id):
        await message.answer("❌ This command is for bot owners only.")
        return
    
    # Double confirmation
    await message.answer(
        "⚠️ <b>WARNING: Enable Kicks?</b>\n\n"
        "This will allow the bot to kick expired users.\n"
        "Make sure whitelist is properly seeded first!\n\n"
        "Type /kicks_on_confirm to proceed."
    )

@router.message(Command("kicks_on_confirm"))
async def cmd_kicks_on_confirm(message: Message):
    """Confirm enabling kicks (owners only)"""
    user_id = message.from_user.id
    
    if not settings.is_owner(user_id):
        await message.answer("❌ This command is for bot owners only.")
        return
    
    success = await db.set_feature_flag('kick_enabled', True)
    if success:
        await message.answer(
            "⚠️ <b>Kicks ENABLED</b>\n\n"
            "The bot will now kick expired users.\n"
            "Whitelisted users remain protected."
        )
        await db.log_event(user_id, "kicks_enabled", {})
    else:
        await message.answer("❌ Failed to enable kicks. Check database connection.")

@router.message(Command("kicks_status"))
async def cmd_kicks_status(message: Message):
    """Check kick status (owners only)"""
    user_id = message.from_user.id
    
    if not settings.is_owner(user_id):
        await message.answer("❌ This command is for bot owners only.")
        return
    
    is_enabled = await db.is_kicks_enabled()
    status_emoji = "⚠️" if is_enabled else "🛡️"
    status_text = "ENABLED" if is_enabled else "DISABLED"
    
    # Get whitelist stats
    wl_stats = await db.get_whitelist_stats()
    
    text = (
        f"{status_emoji} <b>Kick System Status</b>\n\n"
        f"Status: <b>{status_text}</b>\n\n"
        f"<b>Whitelist Protection:</b>\n"
        f"Total whitelisted: {wl_stats.get('total_whitelisted', 0)}\n"
        f"Revoked: {wl_stats.get('revoked_count', 0)}\n"
        f"Active subs whitelisted: {wl_stats.get('subs_active_whitelisted', 0)}\n"
        f"Expired subs whitelisted: {wl_stats.get('subs_expired_whitelisted', 0)}\n\n"
        f"<i>Use /kicks_off to disable kicks</i>"
    )
    
    await message.answer(text)

# ============= WHITELIST MANAGEMENT COMMANDS (OWNERS ONLY) =============

@router.message(Command("wl_add"))
async def cmd_wl_add(message: Message):
    """Add user to whitelist (owners only)"""
    user_id = message.from_user.id
    
    if not settings.is_owner(user_id):
        await message.answer("❌ This command is for bot owners only.")
        return
    
    # Parse command arguments
    args = message.text.split(maxsplit=2)
    if len(args) < 2:
        await message.answer(
            "Usage: /wl_add <user_id> [note]\n"
            "Example: /wl_add 12345678 VIP member"
        )
        return
    
    try:
        target_user_id = int(args[1])
        note = args[2] if len(args) > 2 else None
    except ValueError:
        await message.answer("❌ Invalid user ID. Must be a number.")
        return
    
    success = await db.grant_whitelist(target_user_id, 'manual_command', note)
    if success:
        await message.answer(
            f"✅ User {target_user_id} added to whitelist.\n"
            f"Note: {note or 'No note'}"
        )
        await db.log_event(user_id, "whitelist_add_manual", {
            'target_user_id': target_user_id,
            'note': note
        })
    else:
        await message.answer("❌ Failed to add user to whitelist.")

@router.message(Command("wl_remove"))
async def cmd_wl_remove(message: Message):
    """Remove user from whitelist (owners only)"""
    user_id = message.from_user.id
    
    if not settings.is_owner(user_id):
        await message.answer("❌ This command is for bot owners only.")
        return
    
    # Parse command arguments
    args = message.text.split(maxsplit=2)
    if len(args) < 2:
        await message.answer(
            "Usage: /wl_remove <user_id> [reason]\n"
            "Example: /wl_remove 12345678 No longer VIP"
        )
        return
    
    try:
        target_user_id = int(args[1])
        reason = args[2] if len(args) > 2 else 'manual_removal'
    except ValueError:
        await message.answer("❌ Invalid user ID. Must be a number.")
        return
    
    success = await db.revoke_whitelist(target_user_id, reason)
    if success:
        await message.answer(
            f"✅ User {target_user_id} removed from whitelist.\n"
            f"Reason: {reason}"
        )
        await db.log_event(user_id, "whitelist_remove_manual", {
            'target_user_id': target_user_id,
            'reason': reason
        })
    else:
        await message.answer("❌ User was not whitelisted or removal failed.")

@router.message(Command("wl_status"))
async def cmd_wl_status(message: Message):
    """Check whitelist status of a user (owners only)"""
    user_id = message.from_user.id
    
    if not settings.is_owner(user_id):
        await message.answer("❌ This command is for bot owners only.")
        return
    
    # Parse command arguments
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        # Check self if no user_id provided
        target_user_id = user_id
    else:
        try:
            target_user_id = int(args[1])
        except ValueError:
            await message.answer("❌ Invalid user ID. Must be a number.")
            return
    
    # Get whitelist status
    wl_status = await db.get_whitelist_status(target_user_id)
    
    if not wl_status:
        await message.answer(f"❌ User {target_user_id} has never been whitelisted.")
        return
    
    # Format status message
    status_emoji = "✅" if wl_status['is_active'] else "❌"
    status_text = "ACTIVE" if wl_status['is_active'] else "REVOKED"
    
    text = (
        f"{status_emoji} <b>Whitelist Status</b>\n\n"
        f"User ID: {wl_status['telegram_id']}\n"
        f"Status: <b>{status_text}</b>\n"
        f"Source: {wl_status['source']}\n"
        f"Granted: {wl_status['granted_at'].strftime('%Y-%m-%d %H:%M UTC') if wl_status['granted_at'] else 'Unknown'}\n"
    )
    
    if wl_status['revoked_at']:
        text += f"Revoked: {wl_status['revoked_at'].strftime('%Y-%m-%d %H:%M UTC')}\n"
    
    if wl_status['note']:
        text += f"Note: {wl_status['note']}\n"
    
    await message.answer(text)

@router.message(Command("wl_stats"))
async def cmd_wl_stats(message: Message):
    """Show whitelist statistics (owners only)"""
    user_id = message.from_user.id
    
    if not settings.is_owner(user_id):
        await message.answer("❌ This command is for bot owners only.")
        return
    
    stats = await db.get_whitelist_stats()
    
    text = (
        "📋 <b>Whitelist Statistics</b>\n\n"
        f"<b>Total whitelisted:</b> {stats.get('total_whitelisted', 0)}\n"
        f"<b>Revoked:</b> {stats.get('revoked_count', 0)}\n\n"
        f"<b>Subscription Status:</b>\n"
        f"Active subs whitelisted: {stats.get('subs_active_whitelisted', 0)}\n"
        f"Expired/Grace whitelisted: {stats.get('subs_expired_whitelisted', 0)}\n\n"
        f"<i>Use /wl_report for detailed report</i>"
    )
    
    await message.answer(text)

@router.message(Command("dryrun_expired"))
async def cmd_dryrun_expired(message: Message):
    """Show who would be kicked (dry-run, owners only)"""
    user_id = message.from_user.id
    
    if not settings.is_owner(user_id):
        await message.answer("❌ This command is for bot owners only.")
        return
    
    # Get expired non-whitelisted users
    expired_users = await db.get_expired_non_whitelisted(limit=20)
    
    if not expired_users:
        await message.answer("✅ No users would be kicked. All expired users are whitelisted.")
        return
    
    text = (
        "🔍 <b>Dry-Run: Users That Would Be Kicked</b>\n"
        f"<i>(Showing up to 20 users)</i>\n\n"
    )
    
    for user in expired_users:
        username = f"@{user['username']}" if user['username'] else "No username"
        name = user['first_name'] or "Unknown"
        reason = user['kick_reason']
        expired = user['expires_at'].strftime('%Y-%m-%d') if user['expires_at'] else 'N/A'
        
        text += (
            f"• {name} ({username})\n"
            f"  ID: {user['user_id']}\n"
            f"  Reason: {reason}\n"
            f"  Expired: {expired}\n\n"
        )
    
    text += (
        f"\n<b>Total would be kicked:</b> {len(expired_users)}\n"
        f"<i>Use /wl_add to protect specific users</i>"
    )
    
    await message.answer(text)

@router.message(Command("wl_report"))
async def cmd_wl_report(message: Message):
    """Generate detailed whitelist report (owners only)"""
    user_id = message.from_user.id
    
    if not settings.is_owner(user_id):
        await message.answer("❌ This command is for bot owners only.")
        return
    
    # Get comprehensive stats
    stats = await db.get_whitelist_stats()
    is_kicks_enabled = await db.is_kicks_enabled()
    expired_count = len(await db.get_expired_non_whitelisted(limit=1000))
    
    # Get recent whitelist activity
    recent_grants = await db.fetch("""
        SELECT telegram_id, granted_at, source, note
        FROM whitelist
        WHERE revoked_at IS NULL
        ORDER BY granted_at DESC
        LIMIT 5
    """)
    
    recent_revokes = await db.fetch("""
        SELECT telegram_id, revoked_at, note
        FROM whitelist
        WHERE revoked_at IS NOT NULL
        ORDER BY revoked_at DESC
        LIMIT 5
    """)
    
    text = (
        "📊 <b>WHITELIST REPORT</b>\n"
        "━━━━━━━━━━━━━━━━━━━\n\n"
        f"<b>System Status:</b>\n"
        f"Kicks: {'⚠️ ENABLED' if is_kicks_enabled else '🛡️ DISABLED'}\n\n"
        f"<b>Whitelist Stats:</b>\n"
        f"Total protected: {stats.get('total_whitelisted', 0)}\n"
        f"Revoked: {stats.get('revoked_count', 0)}\n"
        f"Active subs protected: {stats.get('subs_active_whitelisted', 0)}\n"
        f"Expired subs protected: {stats.get('subs_expired_whitelisted', 0)}\n\n"
        f"<b>Risk Assessment:</b>\n"
        f"Users at risk (not whitelisted): {expired_count}\n\n"
    )
    
    if recent_grants:
        text += "<b>Recent Grants:</b>\n"
        for grant in recent_grants[:3]:
            text += f"• {grant['telegram_id']} ({grant['source']})\n"
        text += "\n"
    
    if recent_revokes:
        text += "<b>Recent Revokes:</b>\n"
        for revoke in recent_revokes[:3]:
            text += f"• {revoke['telegram_id']}\n"
        text += "\n"
    
    text += (
        "━━━━━━━━━━━━━━━━━━━\n"
        "<i>Run /dryrun_expired to see who would be kicked</i>"
    )
    
    await message.answer(text)
