from aiogram import Router, F
from aiogram.types import ChatJoinRequest, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery, LabeledPrice
from aiogram.exceptions import TelegramForbiddenError
import logging
from app.config import settings
from app.db import db
from app.routers.payments import finalize_access

logger = logging.getLogger(__name__)
router = Router()

@router.chat_join_request(F.chat.id == settings.group_chat_id)
async def handle_join_request(request: ChatJoinRequest):
    """Handle group join requests"""
    user_id = request.from_user.id
    
    # CRITICAL DEBUG: Log every join request
    logger.info(f"🔥 JOIN REQUEST RECEIVED from user {user_id} (@{request.from_user.username})")
    
    try:
        # Upsert user
        await db.upsert_user(
            user_id=user_id,
            username=request.from_user.username,
            first_name=request.from_user.first_name,
            last_name=request.from_user.last_name,
            language_code=request.from_user.language_code
        )
        
        # Burn whitelist if exists
        was_whitelisted = await db.burn_whitelist(user_id)
        logger.info(f"User {user_id} whitelist check: was_whitelisted={was_whitelisted}")
        
        # Check if user has active access
        has_access = await db.has_active_access(user_id)
        logger.info(f"User {user_id} access check: has_access={has_access}")
        
        if has_access or was_whitelisted:
            # Approve immediately
            try:
                await request.approve()
                await db.log_event(user_id, "auto_approved", {
                    "reason": "whitelist" if was_whitelisted else "active_subscription"
                })
                logger.info(f"Auto-approved user {user_id}")
            except Exception as e:
                logger.error(f"Failed to auto-approve user {user_id}: {e}")
            return
        
        # Send payment offer
        logger.info(f"User {user_id} needs payment - sending DM with payment options")
        await send_payment_offer(request.from_user)
        await db.log_event(user_id, "offer_shown", {"via": "join_request"})
        logger.info(f"Payment offer sent to user {user_id}")
        
    except Exception as e:
        logger.error(f"Error handling join request for user {user_id}: {e}", exc_info=True)

async def send_payment_offer(user):
    """Send payment offer to user"""
    from app.bot import bot
    
    logger.info(f"Preparing to send payment offer to user {user.id}")
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=f"💎 One-time ({settings.plan_stars} Stars)",
                callback_data="pay:one"
            )
        ],
        [
            InlineKeyboardButton(
                text=f"🔄 Monthly Subscription ({settings.sub_stars} Stars)",
                url=f"{settings.webhook_host}/r/sub?u={user.id}&v=A&p={settings.sub_stars}"
            )
        ]
    ])
    
    text = (
        f"👋 Welcome, {user.first_name}!\n\n"
        f"To join the exclusive group, choose your access plan:\n\n"
        f"<b>One-time Access</b>\n"
        f"• {settings.plan_stars} Stars\n"
        f"• {settings.plan_days} days of access\n"
        f"• No auto-renewal\n\n"
        f"<b>Monthly Subscription</b>\n"
        f"• {settings.sub_stars} Stars/month\n"
        f"• Auto-renews every 30 days\n"
        f"• Cancel anytime with /cancel_sub\n\n"
        f"After payment, use /enter to join the group!"
    )
    
    try:
        logger.info(f"Attempting to send DM to user {user.id}...")
        await bot.send_message(
            chat_id=user.id,
            text=text,
            reply_markup=keyboard,
            parse_mode="HTML"  # CRITICAL: This was missing!
        )
        logger.info(f"✅ Successfully sent payment offer DM to user {user.id}")
    except TelegramForbiddenError as e:
        logger.warning(f"Cannot send message to user {user.id} - bot blocked: {e}")
        await db.log_event(user.id, "offer_blocked", {})
    except Exception as e:
        logger.error(f"❌ Failed to send DM to user {user.id}: {e}", exc_info=True)

@router.callback_query(F.data == "pay:one")
async def handle_one_time_payment(callback: CallbackQuery):
    """Handle one-time payment button"""
    from app.bot import bot
    
    user_id = callback.from_user.id
    
    try:
        # Send invoice
        await bot.send_invoice(
            chat_id=user_id,
            title="One-time Group Access",
            description=f"{settings.plan_days} days of exclusive group access",
            payload=f"one_{user_id}",
            currency="XTR",
            prices=[LabeledPrice(label="Group Access", amount=settings.plan_stars)]
        )
        
        await callback.answer("Invoice sent! Complete the payment to get access.")
        await db.log_event(user_id, "invoice_sent", {"type": "one_time"})
        
    except Exception as e:
        logger.error(f"Failed to send invoice to user {user_id}: {e}")
        await callback.answer("Failed to create invoice. Please try again.", show_alert=True)

@router.callback_query(F.data.startswith("pay:"))
async def handle_payment_callback(callback: CallbackQuery):
    """Handle other payment callbacks"""
    await callback.answer("Please use the buttons above to select your payment option.")