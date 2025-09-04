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