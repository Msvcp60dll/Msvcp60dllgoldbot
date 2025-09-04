from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime, timedelta, timezone
import logging
from app.config import settings
from app.db import db

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone=settings.timezone)

async def check_subscriptions():
    """Check and update subscription statuses"""
    from app.bot import bot
    
    now = datetime.now(timezone.utc)
    
    try:
        # Transition active -> grace
        expired_active = await db.fetch("""
            SELECT * FROM subscriptions
            WHERE status = 'active'
                AND expires_at < $1
                AND (grace_started_at IS NULL OR grace_started_at < $1 - INTERVAL '1 hour')
        """, now)
        
        for sub in expired_active:
            grace_until = sub['expires_at'] + timedelta(hours=settings.grace_hours)
            await db.set_grace(sub['user_id'], grace_until)
            
            # Send grace period notification
            try:
                text = (
                    "⏰ <b>Subscription Expired - Grace Period Active</b>\n\n"
                    f"Your subscription has expired, but you have a {settings.grace_hours}-hour grace period.\n"
                    f"Grace period ends: {grace_until.strftime('%Y-%m-%d %H:%M UTC')}\n\n"
                )
                
                if sub['is_recurring']:
                    text += (
                        "Your subscription should auto-renew soon. If payment fails, "
                        "you'll be removed from the group after the grace period.\n\n"
                        "To cancel auto-renewal, use /cancel_sub"
                    )
                else:
                    text += (
                        "Renew now to keep your access:\n"
                        "/status - Check renewal options"
                    )
                
                await bot.send_message(sub['user_id'], text)
                await db.log_event(sub['user_id'], "grace_notification_sent", {})
                
            except Exception as e:
                logger.warning(f"Failed to send grace notification to user {sub['user_id']}: {e}")
        
        # Transition grace -> expired
        expired_grace = await db.fetch("""
            SELECT * FROM subscriptions
            WHERE status = 'grace'
                AND grace_until < $1
        """, now)
        
        for sub in expired_grace:
            await db.set_expired(sub['user_id'])
            
            # Ban user if not whitelisted
            if not await db.is_whitelisted(sub['user_id']):
                try:
                    await bot.ban_chat_member(
                        chat_id=settings.group_chat_id,
                        user_id=sub['user_id'],
                        until_date=None  # Permanent ban
                    )
                    await db.log_event(sub['user_id'], "auto_banned", {
                        "reason": "grace_expired"
                    })
                    logger.info(f"Banned user {sub['user_id']} after grace period expired")
                except Exception as e:
                    logger.error(f"Failed to ban user {sub['user_id']}: {e}")
            
            # Send expiry notification
            try:
                await bot.send_message(
                    sub['user_id'],
                    "❌ <b>Access Expired</b>\n\n"
                    "Your grace period has ended and you've been removed from the group.\n\n"
                    "To rejoin, use /status to see available plans."
                )
                await db.log_event(sub['user_id'], "expiry_notification_sent", {})
            except Exception as e:
                logger.warning(f"Failed to send expiry notification to user {sub['user_id']}: {e}")
        
        logger.info(f"Subscription check: {len(expired_active)} to grace, {len(expired_grace)} expired")
        
    except Exception as e:
        logger.error(f"Error in subscription check: {e}", exc_info=True)

async def send_reminders():
    """Send expiry reminders for non-recurring subscriptions"""
    from app.bot import bot
    
    now = datetime.now(timezone.utc)
    reminder_date = now + timedelta(days=settings.days_before_expire)
    
    try:
        # Find subscriptions expiring soon
        expiring_soon = await db.fetch("""
            SELECT * FROM subscriptions
            WHERE status = 'active'
                AND is_recurring = false
                AND expires_at BETWEEN $1 AND $2
                AND (reminder_sent_at IS NULL OR reminder_sent_at < $1 - INTERVAL '1 day')
        """, now, reminder_date)
        
        for sub in expiring_soon:
            try:
                days_left = (sub['expires_at'] - now).days
                
                text = (
                    f"⏰ <b>Subscription Expiring Soon</b>\n\n"
                    f"Your access expires in {days_left} days.\n"
                    f"Expiry date: {sub['expires_at'].strftime('%Y-%m-%d %H:%M UTC')}\n\n"
                    f"Renew now to avoid interruption:\n"
                    f"• One-time: {settings.plan_stars} Stars\n"
                    f"• Monthly subscription: {settings.sub_stars} Stars\n\n"
                    f"Use /status to renew"
                )
                
                await bot.send_message(sub['user_id'], text)
                
                # Mark reminder as sent
                await db.execute("""
                    UPDATE subscriptions
                    SET reminder_sent_at = NOW()
                    WHERE subscription_id = $1
                """, sub['subscription_id'])
                
                await db.log_event(sub['user_id'], "reminder_sent", {
                    "days_left": days_left
                })
                
            except Exception as e:
                logger.warning(f"Failed to send reminder to user {sub['user_id']}: {e}")
        
        logger.info(f"Sent {len(expiring_soon)} expiry reminders")
        
    except Exception as e:
        logger.error(f"Error sending reminders: {e}", exc_info=True)

async def process_notifications():
    """Process queued notifications"""
    from app.bot import bot
    
    try:
        notifications = await db.get_pending_notifications(limit=50)
        
        for notif in notifications:
            try:
                # Build message based on notification type
                if notif['type'] == 'payment_received':
                    text = "✅ Payment received! Your access has been activated."
                elif notif['type'] == 'subscription_renewed':
                    text = "✅ Subscription renewed! Your access continues."
                elif notif['type'] == 'grace_period_started':
                    text = f"⏰ Your subscription expired. You have {settings.grace_hours} hours grace period."
                else:
                    continue
                
                await bot.send_message(notif['user_id'], text)
                await db.mark_notification_sent(notif['notification_id'])
                
            except Exception as e:
                logger.warning(f"Failed to send notification {notif['notification_id']}: {e}")
        
        if notifications:
            logger.info(f"Processed {len(notifications)} notifications")
            
    except Exception as e:
        logger.error(f"Error processing notifications: {e}", exc_info=True)

def start_scheduler():
    """Start the scheduler with all jobs"""
    # Check subscriptions every hour
    scheduler.add_job(
        check_subscriptions,
        IntervalTrigger(hours=1),
        id="check_subscriptions",
        replace_existing=True
    )
    
    # Send reminders daily
    scheduler.add_job(
        send_reminders,
        IntervalTrigger(hours=24),
        id="send_reminders",
        replace_existing=True
    )
    
    # Process notifications every 5 minutes
    scheduler.add_job(
        process_notifications,
        IntervalTrigger(minutes=5),
        id="process_notifications",
        replace_existing=True
    )
    
    # Start reconciliation every 6 hours
    from app.reconcile import reconcile_star_transactions
    scheduler.add_job(
        reconcile_star_transactions,
        IntervalTrigger(hours=6),
        id="reconcile_transactions",
        replace_existing=True
    )
    
    scheduler.start()
    logger.info("Scheduler started with all jobs")

def stop_scheduler():
    """Stop the scheduler"""
    scheduler.shutdown(wait=True)
    logger.info("Scheduler stopped")