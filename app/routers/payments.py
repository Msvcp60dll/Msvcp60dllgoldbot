from aiogram import Router, F
from aiogram.types import PreCheckoutQuery, Message, LabeledPrice
from aiogram.exceptions import TelegramRetryAfter, TelegramForbiddenError
from datetime import datetime, timezone, timedelta
import asyncio
import time
from app.config import settings
from app.db import db
from app.bot import bot
from app.telegram_resilient import create_resilient_bot
from app.logging_config import (
    get_logger, 
    set_user_id,
    log_performance,
    log_business_event,
    log_error,
    BusinessEvents
)

logger = get_logger(__name__)
router = Router()

@router.pre_checkout_query()
async def handle_pre_checkout(query: PreCheckoutQuery):
    """Always approve pre-checkout queries for Stars payments"""
    user_id = query.from_user.id
    set_user_id(user_id)
    
    logger.info(
        BusinessEvents.PAYMENT_INITIATED,
        user_id=user_id,
        amount=query.total_amount,
        currency=query.currency,
        invoice_payload=query.invoice_payload
    )
    
    try:
        await query.answer(ok=True)
        
        await db.log_event(user_id, "pre_checkout_approved", {
            "invoice_payload": query.invoice_payload,
            "total_amount": query.total_amount,
            "currency": query.currency
        })
        
        logger.debug(
            "pre_checkout.approved",
            user_id=user_id,
            amount=query.total_amount
        )
        
    except Exception as e:
        log_error(
            "pre_checkout.error",
            exception=e,
            user_id=user_id,
            amount=query.total_amount
        )
        await query.answer(ok=False, error_message="Payment processing error")

@router.message(F.successful_payment)
@log_performance("payment.processing")
async def handle_successful_payment(message: Message):
    """Handle successful payment with idempotency"""
    start_time = time.time()
    payment = message.successful_payment
    user_id = message.from_user.id
    set_user_id(user_id)
    
    charge_id = payment.telegram_payment_charge_id
    amount = payment.total_amount
    
    logger.info(
        "payment.received",
        user_id=user_id,
        charge_id=charge_id,
        amount=amount,
        currency=payment.currency
    )
    
    try:
        # Upsert user
        user_start = time.time()
        await db.upsert_user(
            user_id=user_id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name,
            language_code=message.from_user.language_code
        )
        user_duration = int((time.time() - user_start) * 1000)
        
        if user_duration > 100:
            logger.warning(
                "database.slow_query",
                operation="upsert_user",
                duration_ms=user_duration,
                user_id=user_id
            )
        
        # Determine payment type
        is_recurring = payment.is_recurring if hasattr(payment, 'is_recurring') else False
        payment_type = 'recurring_initial' if is_recurring else 'one_time'
        
        logger.debug(
            "payment.type_determined",
            user_id=user_id,
            payment_type=payment_type,
            is_recurring=is_recurring
        )
        
        # Insert payment with idempotency
        payment_start = time.time()
        payment_record = await db.insert_payment_idempotent(
            user_id=user_id,
            charge_id=charge_id,
            star_tx_id=getattr(payment, 'provider_payment_charge_id', None),
            amount=amount,
            payment_type=payment_type,
            is_recurring=is_recurring,
            invoice_payload=payment.invoice_payload
        )
        payment_duration = int((time.time() - payment_start) * 1000)
        
        if payment_duration > 100:
            logger.warning(
                "database.slow_query",
                operation="insert_payment",
                duration_ms=payment_duration,
                user_id=user_id
            )
        
        if not payment_record:
            log_business_event(
                BusinessEvents.PAYMENT_DUPLICATE,
                user_id=user_id,
                charge_id=charge_id,
                amount=amount
            )
            await message.answer("✅ Payment already processed. Use /enter to access the group.")
            return
        
        # Process subscription
        subscription_expiration = None
        if is_recurring and hasattr(payment, 'subscription_expiration_date'):
            subscription_expiration = datetime.fromtimestamp(
                payment.subscription_expiration_date, 
                tz=timezone.utc
            )
        
        sub_start = time.time()
        await db.process_subscription_payment(
            user_id=user_id,
            payment=payment_record,
            subscription_expiration=subscription_expiration,
            is_recurring=is_recurring
        )
        sub_duration = int((time.time() - sub_start) * 1000)
        
        if sub_duration > 100:
            logger.warning(
                "database.slow_query",
                operation="process_subscription",
                duration_ms=sub_duration,
                user_id=user_id
            )
        
        # Log business event
        if is_recurring:
            log_business_event(
                BusinessEvents.SUBSCRIPTION_CREATED,
                user_id=user_id,
                charge_id=charge_id,
                amount=amount,
                expires_at=subscription_expiration.isoformat() if subscription_expiration else None
            )
        
        log_business_event(
            BusinessEvents.PAYMENT_PROCESSED,
            user_id=user_id,
            charge_id=charge_id,
            amount=amount,
            payment_type=payment_type,
            is_recurring=is_recurring,
            duration_ms=int((time.time() - start_time) * 1000)
        )
        
        # Log success to funnel events
        await db.log_event(user_id, "payment_success", {
            "charge_id": charge_id,
            "amount": amount,
            "is_recurring": is_recurring
        })
        
        # Send confirmation with resilient bot
        resilient_bot = create_resilient_bot(bot)
        
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
        
        # Use resilient send with fallback
        await resilient_bot.send_message_with_fallback(
            chat_id=user_id,
            text=text,
            fallback_text="✅ Payment successful! Use /enter to join the group.",
            parse_mode="HTML"
        )
        
        logger.info(
            "payment.confirmation_sent",
            user_id=user_id,
            payment_type=payment_type
        )
        
        # Finalize access in background
        asyncio.create_task(finalize_access(user_id))
        
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        
        log_error(
            BusinessEvents.PAYMENT_FAILED,
            exception=e,
            user_id=user_id,
            charge_id=charge_id,
            amount=amount,
            duration_ms=duration_ms
        )
        
        # Queue for manual review but still give access
        try:
            await db.execute("""
                INSERT INTO failed_payments_queue (user_id, charge_id, error, raw_update)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (charge_id) DO NOTHING
            """, user_id, charge_id, str(e), message.model_dump_json())
            
            logger.info(
                "payment.queued_for_review",
                user_id=user_id,
                charge_id=charge_id
            )
        except Exception as queue_error:
            logger.error(
                "payment.queue_failed",
                exception=queue_error,
                user_id=user_id,
                charge_id=charge_id
            )
        
        await message.answer(
            "✅ Payment received! There was a small issue with processing, "
            "but your access is secured. Use /enter to join the group."
        )
        
        # Still try to give access
        asyncio.create_task(finalize_access(user_id))

async def finalize_access(user_id: int):
    """Approve join request with exponential backoff retry"""
    from app.bot import bot
    
    set_user_id(user_id)
    delay = 0.5
    max_attempts = 8
    
    logger.info(
        "access.finalization_started",
        user_id=user_id,
        max_attempts=max_attempts
    )
    
    for attempt in range(max_attempts):
        try:
            api_start = time.time()
            await bot.approve_chat_join_request(
                chat_id=settings.group_chat_id,
                user_id=user_id
            )
            api_duration = int((time.time() - api_start) * 1000)
            
            await db.log_event(user_id, "approve_ok", {"attempt": attempt})
            
            log_business_event(
                BusinessEvents.JOIN_REQUEST_APPROVED,
                user_id=user_id,
                attempt=attempt,
                api_duration_ms=api_duration
            )
            
            return True
            
        except TelegramRetryAfter as e:
            logger.warning(
                "telegram.rate_limit",
                user_id=user_id,
                attempt=attempt,
                retry_after=e.retry_after
            )
            await db.log_event(user_id, "approve_retry", {"attempt": attempt, "retry_after": e.retry_after})
            await asyncio.sleep(e.retry_after)
            
        except TelegramForbiddenError:
            # No pending join request
            logger.info(
                "access.no_pending_request",
                user_id=user_id,
                attempt=attempt
            )
            await db.log_event(user_id, "approve_no_request", {"attempt": attempt})
            return False
            
        except Exception as e:
            logger.warning(
                "access.approval_failed",
                user_id=user_id,
                attempt=attempt,
                exception=e,
                will_retry=attempt < max_attempts - 1
            )
            
            await db.log_event(user_id, "approve_retry", {"attempt": attempt, "error": str(e)})
            
            if attempt < max_attempts - 1:
                await asyncio.sleep(delay)
                delay *= 2
            else:
                await db.log_event(user_id, "approve_fail", {"total_attempts": max_attempts})
                
                log_error(
                    "access.finalization_failed",
                    user_id=user_id,
                    total_attempts=max_attempts,
                    final_error=str(e)
                )
                return False
    
    return False

@log_performance("invoice.creation")
async def create_subscription_invoice_link(user_id: int, amount: int) -> str:
    """Create subscription invoice link"""
    from app.bot import bot
    
    set_user_id(user_id)
    
    logger.info(
        "invoice.creation_started",
        user_id=user_id,
        amount=amount or settings.sub_stars
    )
    
    try:
        api_start = time.time()
        link = await bot.create_invoice_link(
            title="Monthly Group Access",
            description="Recurring monthly subscription with auto-renewal",
            payload=f"sub_{user_id}",
            currency="XTR",
            prices=[LabeledPrice(label="Monthly Subscription", amount=amount or settings.sub_stars)],
            subscription_period=2592000  # Exactly 30 days in seconds
        )
        api_duration = int((time.time() - api_start) * 1000)
        
        logger.info(
            "invoice.created",
            user_id=user_id,
            amount=amount or settings.sub_stars,
            api_duration_ms=api_duration
        )
        
        return link
        
    except Exception as e:
        log_error(
            "invoice.creation_failed",
            exception=e,
            user_id=user_id,
            amount=amount
        )
        raise