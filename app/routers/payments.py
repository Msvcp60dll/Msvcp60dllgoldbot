from aiogram import Router, F
from aiogram.types import PreCheckoutQuery, Message, LabeledPrice
from aiogram.exceptions import TelegramRetryAfter, TelegramForbiddenError
from datetime import datetime, timezone, timedelta
import asyncio
import logging
from app.config import settings
from app.db import db

logger = logging.getLogger(__name__)
router = Router()

@router.pre_checkout_query()
async def handle_pre_checkout(query: PreCheckoutQuery):
    """Always approve pre-checkout queries for Stars payments"""
    try:
        await query.answer(ok=True)
        await db.log_event(query.from_user.id, "pre_checkout_approved", {
            "invoice_payload": query.invoice_payload,
            "total_amount": query.total_amount,
            "currency": query.currency
        })
    except Exception as e:
        logger.error(f"Pre-checkout error: {e}")
        await query.answer(ok=False, error_message="Payment processing error")

@router.message(F.successful_payment)
async def handle_successful_payment(message: Message):
    """Handle successful payment with idempotency"""
    payment = message.successful_payment
    user_id = message.from_user.id
    
    try:
        # Upsert user
        await db.upsert_user(
            user_id=user_id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name,
            language_code=message.from_user.language_code
        )
        
        # Determine payment type
        is_recurring = payment.is_recurring if hasattr(payment, 'is_recurring') else False
        payment_type = 'recurring_initial' if is_recurring else 'one_time'
        
        # Insert payment with idempotency
        payment_record = await db.insert_payment_idempotent(
            user_id=user_id,
            charge_id=payment.telegram_payment_charge_id,
            star_tx_id=getattr(payment, 'provider_payment_charge_id', None),
            amount=payment.total_amount,
            payment_type=payment_type,
            is_recurring=is_recurring,
            invoice_payload=payment.invoice_payload
        )
        
        if not payment_record:
            logger.info(f"Duplicate payment for user {user_id}, charge_id: {payment.telegram_payment_charge_id}")
            await message.answer("✅ Payment already processed. Use /enter to access the group.")
            return
        
        # Process subscription
        subscription_expiration = None
        if is_recurring and hasattr(payment, 'subscription_expiration_date'):
            subscription_expiration = datetime.fromtimestamp(
                payment.subscription_expiration_date, 
                tz=timezone.utc
            )
        
        await db.process_subscription_payment(
            user_id=user_id,
            payment=payment_record,
            subscription_expiration=subscription_expiration,
            is_recurring=is_recurring
        )
        
        # Log success
        await db.log_event(user_id, "payment_success", {
            "charge_id": payment.telegram_payment_charge_id,
            "amount": payment.total_amount,
            "is_recurring": is_recurring
        })
        
        # Send confirmation
        if is_recurring:
            text = (
                "✅ <b>Subscription activated!</b>\n\n"
                f"Your monthly subscription is now active and will auto-renew.\n"
                f"Expires: {subscription_expiration.strftime('%Y-%m-%d %H:%M UTC') if subscription_expiration else 'in 30 days'}\n\n"
                "Use /enter to join the group now!\n"
                "Use /cancel_sub to disable auto-renewal."
            )
        else:
            text = (
                "✅ <b>Payment successful!</b>\n\n"
                f"You have {settings.plan_days} days of access.\n\n"
                "Use /enter to join the group now!"
            )
        
        await message.answer(text)
        
        # Finalize access in background
        asyncio.create_task(finalize_access(user_id))
        
    except Exception as e:
        logger.error(f"Payment processing error for user {user_id}: {e}", exc_info=True)
        
        # Queue for manual review but still give access
        await db.execute("""
            INSERT INTO failed_payments_queue (user_id, charge_id, error, raw_update)
            VALUES ($1, $2, $3, $4)
        """, user_id, payment.telegram_payment_charge_id, str(e), message.model_dump_json())
        
        await message.answer(
            "✅ Payment received! There was a small issue with processing, "
            "but your access is secured. Use /enter to join the group."
        )
        
        # Still try to give access
        asyncio.create_task(finalize_access(user_id))

async def finalize_access(user_id: int):
    """Approve join request with exponential backoff retry"""
    from app.bot import bot
    
    delay = 0.5
    max_attempts = 8
    
    for attempt in range(max_attempts):
        try:
            await bot.approve_chat_join_request(
                chat_id=settings.group_chat_id,
                user_id=user_id
            )
            await db.log_event(user_id, "approve_ok", {"attempt": attempt})
            logger.info(f"Approved join request for user {user_id} on attempt {attempt}")
            return True
            
        except TelegramRetryAfter as e:
            await db.log_event(user_id, "approve_retry", {"attempt": attempt, "retry_after": e.retry_after})
            await asyncio.sleep(e.retry_after)
            
        except TelegramForbiddenError:
            # No pending join request
            await db.log_event(user_id, "approve_no_request", {"attempt": attempt})
            logger.info(f"No pending join request for user {user_id}")
            return False
            
        except Exception as e:
            await db.log_event(user_id, "approve_retry", {"attempt": attempt, "error": str(e)})
            logger.warning(f"Failed to approve user {user_id} on attempt {attempt}: {e}")
            
            if attempt < max_attempts - 1:
                await asyncio.sleep(delay)
                delay *= 2
            else:
                await db.log_event(user_id, "approve_fail", {"total_attempts": max_attempts})
                logger.error(f"Failed to approve user {user_id} after {max_attempts} attempts")
                return False
    
    return False

async def create_subscription_invoice_link(user_id: int, amount: int) -> str:
    """Create subscription invoice link"""
    from app.bot import bot
    
    link = await bot.create_invoice_link(
        title="Monthly Group Access",
        description="Recurring monthly subscription with auto-renewal",
        payload=f"sub_{user_id}",
        currency="XTR",
        prices=[LabeledPrice(label="Monthly Subscription", amount=amount or settings.sub_stars)],
        subscription_period=2592000  # Exactly 30 days in seconds
    )
    
    return link