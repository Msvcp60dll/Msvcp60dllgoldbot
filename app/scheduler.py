from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, timedelta, timezone
import time
import os
from app.config import settings
from app.db import db
from app.logging_config import (
    get_logger,
    set_user_id,
    log_performance,
    log_business_event,
    log_error,
    BusinessEvents
)

logger = get_logger(__name__)

scheduler = AsyncIOScheduler(timezone=settings.timezone)

@log_performance("scheduler.check_subscriptions")
async def check_subscriptions():
    """Check and update subscription statuses"""
    from app.bot import bot
    
    start_time = time.time()
    now = datetime.now(timezone.utc)
    
    logger.info(
        "subscription_check.started",
        check_time=now.isoformat()
    )
    
    active_to_grace = 0
    grace_to_expired = 0
    users_banned = 0
    errors = 0
    
    try:
        # Transition active -> grace
        query_start = time.time()
        expired_active = await db.fetch("""
            SELECT * FROM subscriptions
            WHERE status = 'active'
                AND expires_at < $1
                AND (grace_started_at IS NULL OR grace_started_at < $1 - INTERVAL '1 hour')
        """, now)
        query_duration = int((time.time() - query_start) * 1000)
        
        if query_duration > 100:
            logger.warning(
                "database.slow_query",
                operation="fetch_expired_active",
                duration_ms=query_duration,
                result_count=len(expired_active)
            )
        
        for sub in expired_active:
            user_id = sub['user_id']
            set_user_id(user_id)
            
            try:
                grace_until = sub['expires_at'] + timedelta(hours=settings.grace_hours)
                
                # Set grace period
                await db.set_grace(user_id, grace_until)
                active_to_grace += 1
                
                log_business_event(
                    BusinessEvents.GRACE_PERIOD_STARTED,
                    user_id=user_id,
                    expires_at=sub['expires_at'].isoformat(),
                    grace_until=grace_until.isoformat(),
                    is_recurring=sub['is_recurring']
                )
                
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
                    
                    api_start = time.time()
                    await bot.send_message(user_id, text)
                    api_duration = int((time.time() - api_start) * 1000)
                    
                    await db.log_event(user_id, "grace_notification_sent", {})
                    
                    log_business_event(
                        BusinessEvents.GRACE_PERIOD_REMINDER,
                        user_id=user_id,
                        notification_sent=True,
                        api_duration_ms=api_duration
                    )
                    
                except Exception as e:
                    logger.warning(
                        "notification.send_failed",
                        user_id=user_id,
                        notification_type="grace_period",
                        exception=e
                    )
                    errors += 1
                    
            except Exception as e:
                logger.error(
                    "grace_transition.failed",
                    user_id=user_id,
                    exception=e
                )
                errors += 1
        
        # Transition grace -> expired
        query_start = time.time()
        expired_grace = await db.fetch("""
            SELECT * FROM subscriptions
            WHERE status = 'grace'
                AND grace_until < $1
        """, now)
        query_duration = int((time.time() - query_start) * 1000)
        
        if query_duration > 100:
            logger.warning(
                "database.slow_query",
                operation="fetch_expired_grace",
                duration_ms=query_duration,
                result_count=len(expired_grace)
            )
        
        for sub in expired_grace:
            user_id = sub['user_id']
            set_user_id(user_id)
            
            try:
                await db.set_expired(user_id)
                grace_to_expired += 1
                
                log_business_event(
                    BusinessEvents.GRACE_PERIOD_ENDED,
                    user_id=user_id,
                    grace_until=sub['grace_until'].isoformat()
                )
                
                # Ban user if not whitelisted
                is_whitelisted = await db.is_whitelisted(user_id)
                
                if not is_whitelisted:
                    try:
                        api_start = time.time()
                        await bot.ban_chat_member(
                            chat_id=settings.group_chat_id,
                            user_id=user_id,
                            until_date=None  # Permanent ban
                        )
                        api_duration = int((time.time() - api_start) * 1000)
                        
                        await db.log_event(user_id, "auto_banned", {
                            "reason": "grace_expired"
                        })
                        users_banned += 1
                        
                        log_business_event(
                            BusinessEvents.USER_BANNED,
                            user_id=user_id,
                            reason="grace_expired",
                            api_duration_ms=api_duration
                        )
                        
                    except Exception as e:
                        logger.error(
                            "ban.failed",
                            user_id=user_id,
                            exception=e
                        )
                        errors += 1
                else:
                    logger.info(
                        "ban.skipped_whitelist",
                        user_id=user_id
                    )
                
                # Send expiry notification
                try:
                    await bot.send_message(
                        user_id,
                        "❌ <b>Access Expired</b>\n\n"
                        "Your grace period has ended and you've been removed from the group.\n\n"
                        "To rejoin, use /status to see available plans."
                    )
                    await db.log_event(user_id, "expiry_notification_sent", {})
                    
                    log_business_event(
                        BusinessEvents.SUBSCRIPTION_EXPIRED,
                        user_id=user_id,
                        was_banned=not is_whitelisted
                    )
                    
                except Exception as e:
                    logger.warning(
                        "notification.send_failed",
                        user_id=user_id,
                        notification_type="expiry",
                        exception=e
                    )
                    errors += 1
                    
            except Exception as e:
                logger.error(
                    "expiry_transition.failed",
                    user_id=user_id,
                    exception=e
                )
                errors += 1
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        logger.info(
            "subscription_check.completed",
            duration_ms=duration_ms,
            active_to_grace=active_to_grace,
            grace_to_expired=grace_to_expired,
            users_banned=users_banned,
            errors=errors
        )
        
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        
        log_error(
            "subscription_check.failed",
            exception=e,
            duration_ms=duration_ms,
            partial_active_to_grace=active_to_grace,
            partial_grace_to_expired=grace_to_expired
        )

@log_performance("scheduler.send_reminders")
async def send_reminders():
    """Send expiry reminders for non-recurring subscriptions"""
    from app.bot import bot
    
    start_time = time.time()
    now = datetime.now(timezone.utc)
    reminder_date = now + timedelta(days=settings.days_before_expire)
    
    reminders_sent = 0
    errors = 0
    
    logger.info(
        "reminder_check.started",
        check_time=now.isoformat(),
        reminder_window_days=settings.days_before_expire
    )
    
    try:
        # Find subscriptions expiring soon
        query_start = time.time()
        expiring_soon = await db.fetch("""
            SELECT * FROM subscriptions
            WHERE status = 'active'
                AND is_recurring = false
                AND expires_at BETWEEN $1 AND $2
                AND (reminder_sent_at IS NULL OR reminder_sent_at < $1 - INTERVAL '1 day')
        """, now, reminder_date)
        query_duration = int((time.time() - query_start) * 1000)
        
        if query_duration > 100:
            logger.warning(
                "database.slow_query",
                operation="fetch_expiring_soon",
                duration_ms=query_duration,
                result_count=len(expiring_soon)
            )
        
        for sub in expiring_soon:
            user_id = sub['user_id']
            set_user_id(user_id)
            
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
                
                api_start = time.time()
                await bot.send_message(user_id, text)
                api_duration = int((time.time() - api_start) * 1000)
                
                # Mark reminder as sent
                await db.execute("""
                    UPDATE subscriptions
                    SET reminder_sent_at = NOW()
                    WHERE subscription_id = $1
                """, sub['subscription_id'])
                
                await db.log_event(user_id, "reminder_sent", {
                    "days_left": days_left
                })
                
                reminders_sent += 1
                
                logger.info(
                    "reminder.sent",
                    user_id=user_id,
                    days_left=days_left,
                    api_duration_ms=api_duration
                )
                
            except Exception as e:
                logger.warning(
                    "reminder.send_failed",
                    user_id=user_id,
                    exception=e
                )
                errors += 1
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        logger.info(
            "reminder_check.completed",
            duration_ms=duration_ms,
            reminders_sent=reminders_sent,
            errors=errors
        )
        
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        
        log_error(
            "reminder_check.failed",
            exception=e,
            duration_ms=duration_ms,
            partial_sent=reminders_sent
        )

@log_performance("scheduler.process_notifications")
async def process_notifications():
    """Process queued notifications"""
    from app.bot import bot
    
    start_time = time.time()
    processed = 0
    errors = 0
    
    try:
        notifications = await db.get_pending_notifications(limit=50)
        
        if notifications:
            logger.info(
                "notification_batch.started",
                batch_size=len(notifications)
            )
        
        for notif in notifications:
            user_id = notif['user_id']
            set_user_id(user_id)
            
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
                
                api_start = time.time()
                await bot.send_message(user_id, text)
                api_duration = int((time.time() - api_start) * 1000)
                
                await db.mark_notification_sent(notif['notification_id'])
                processed += 1
                
                logger.debug(
                    "notification.sent",
                    notification_id=notif['notification_id'],
                    user_id=user_id,
                    type=notif['type'],
                    api_duration_ms=api_duration
                )
                
            except Exception as e:
                logger.warning(
                    "notification.send_failed",
                    notification_id=notif['notification_id'],
                    user_id=user_id,
                    exception=e
                )
                errors += 1
        
        if notifications:
            duration_ms = int((time.time() - start_time) * 1000)
            
            logger.info(
                "notification_batch.completed",
                duration_ms=duration_ms,
                processed=processed,
                errors=errors
            )
            
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        
        log_error(
            "notification_batch.failed",
            exception=e,
            duration_ms=duration_ms,
            partial_processed=processed
        )

@log_performance("scheduler.daily_stats")
async def send_daily_stats():
    """Send daily statistics to bot owner"""
    from app.bot import bot
    
    owner_id = os.getenv("BOT_OWNER_ID")
    if not owner_id:
        logger.info("daily_stats.skipped - BOT_OWNER_ID not set")
        return
    
    try:
        owner_id = int(owner_id)
        today = datetime.now(timezone.utc).date()
        yesterday = today - timedelta(days=1)
        
        # Get statistics
        stats = await db.fetch_one("""
            SELECT 
                -- Active users
                COUNT(DISTINCT CASE 
                    WHEN last_interaction > NOW() - INTERVAL '24 hours' 
                    THEN user_id 
                END) as active_users_24h,
                
                -- Total users
                COUNT(DISTINCT user_id) as total_users,
                
                -- New signups today
                COUNT(DISTINCT CASE 
                    WHEN created_at::date = $1 
                    THEN user_id 
                END) as new_signups_today
            FROM users
        """, today)
        
        # Get revenue
        revenue = await db.fetch_one("""
            SELECT 
                -- Revenue today
                COALESCE(SUM(CASE 
                    WHEN created_at::date = $1 
                    THEN amount 
                END), 0) as revenue_today,
                
                -- Revenue this month
                COALESCE(SUM(CASE 
                    WHEN DATE_TRUNC('month', created_at) = DATE_TRUNC('month', $1::timestamp) 
                    THEN amount 
                END), 0) as revenue_month,
                
                -- Payments today
                COUNT(CASE 
                    WHEN created_at::date = $1 
                    THEN 1 
                END) as payments_today
            FROM payments
        """, today)
        
        # Get subscription stats
        subs = await db.fetch_one("""
            SELECT 
                COUNT(CASE WHEN status = 'active' THEN 1 END) as active_subs,
                COUNT(CASE WHEN status = 'grace' THEN 1 END) as grace_subs,
                COUNT(CASE WHEN is_recurring = true AND status = 'active' THEN 1 END) as recurring_subs
            FROM subscriptions
        """)
        
        # Format message
        message = f"""📊 <b>Daily Stats Report</b>
📅 {today.strftime('%Y-%m-%d')}

<b>👥 Users:</b>
• Active (24h): {stats['active_users_24h']}
• New signups: {stats['new_signups_today']}
• Total users: {stats['total_users']}

<b>💰 Revenue:</b>
• Today: {revenue['revenue_today']} ⭐
• This month: {revenue['revenue_month']} ⭐
• Payments today: {revenue['payments_today']}

<b>📋 Subscriptions:</b>
• Active: {subs['active_subs']}
• Recurring: {subs['recurring_subs']}
• Grace period: {subs['grace_subs']}

<b>💵 MRR:</b> {subs['recurring_subs'] * settings.sub_stars} ⭐
"""
        
        # Send to owner
        await bot.send_message(owner_id, message, parse_mode="HTML")
        
        logger.info(
            "daily_stats.sent",
            owner_id=owner_id,
            active_users=stats['active_users_24h'],
            new_signups=stats['new_signups_today'],
            revenue_today=revenue['revenue_today']
        )
        
    except Exception as e:
        logger.error(
            "daily_stats.failed",
            exception=e,
            owner_id=owner_id
        )

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
    
    # Send daily stats at 9 AM UTC
    scheduler.add_job(
        send_daily_stats,
        CronTrigger(hour=9, minute=0),
        id="daily_stats",
        replace_existing=True
    )
    
    scheduler.start()
    
    logger.info(
        "scheduler.started",
        jobs=[
            {"id": "check_subscriptions", "interval": "1 hour"},
            {"id": "send_reminders", "interval": "24 hours"},
            {"id": "process_notifications", "interval": "5 minutes"},
            {"id": "reconcile_transactions", "interval": "6 hours"},
            {"id": "daily_stats", "schedule": "daily at 9:00 UTC"}
        ]
    )

def stop_scheduler():
    """Stop the scheduler"""
    scheduler.shutdown(wait=True)
    logger.info("scheduler.stopped")