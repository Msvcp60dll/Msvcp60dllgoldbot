from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand
from aiogram.webhook.aiohttp_server import SimpleRequestHandler
import logging
from app.config import settings
from app.webhook_config import REQUIRED_WEBHOOK_UPDATES, validate_webhook_updates

logger = logging.getLogger(__name__)

# Initialize bot with default properties
bot = Bot(
    token=settings.bot_token,
    default=DefaultBotProperties(
        parse_mode=ParseMode.HTML,
        link_preview_is_disabled=True
    )
)

# Initialize dispatcher
dp = Dispatcher()

async def setup_bot():
    """Setup bot commands and webhook"""
    # Set bot commands
    commands = [
        BotCommand(command="start", description="Start interaction with bot"),
        BotCommand(command="status", description="Check your subscription status"),
        BotCommand(command="enter", description="Get access to the group"),
        BotCommand(command="cancel_sub", description="Cancel auto-renewal"),
        BotCommand(command="help", description="Get help")
    ]
    await bot.set_my_commands(commands)
    
    # Delete webhook first
    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Webhook deleted")
    
    # Set webhook if public base URL is configured
    if settings.public_base_url:
        webhook_url = settings.webhook_url
        secret = settings.effective_telegram_secret
        
        # Use the single source of truth for webhook configuration
        logger.info(f"Setting webhook with allowed_updates: {REQUIRED_WEBHOOK_UPDATES}")
        
        await bot.set_webhook(
            url=webhook_url,
            allowed_updates=REQUIRED_WEBHOOK_UPDATES,
            drop_pending_updates=False,  # Don't lose pending updates
            secret_token=secret,
        )
        
        # Verify webhook was set correctly
        webhook_info = await bot.get_webhook_info()
        logger.info(f"Webhook set to {webhook_url}")
        logger.info(f"Webhook allowed_updates: {webhook_info.allowed_updates}")
        
        if "chat_join_request" not in (webhook_info.allowed_updates or []):
            logger.critical("⚠️ WARNING: chat_join_request NOT in webhook allowed_updates!")
        if "successful_payment" not in (webhook_info.allowed_updates or []):
            logger.critical("⚠️ WARNING: successful_payment NOT in webhook allowed_updates!")
            
        # Validate webhook configuration using single source of truth
        is_valid, missing = validate_webhook_updates(webhook_info.allowed_updates)
        
        if not is_valid:
            logger.critical(f"🚨 FORCING WEBHOOK RESET - Missing: {missing}")
            await bot.delete_webhook(drop_pending_updates=False)
            await bot.set_webhook(
                url=webhook_url,
                allowed_updates=REQUIRED_WEBHOOK_UPDATES,
                drop_pending_updates=False,
                secret_token=secret,
            )
            webhook_info = await bot.get_webhook_info()
            logger.info(f"Webhook FORCED reset. New allowed_updates: {webhook_info.allowed_updates}")
    else:
        logger.warning("No webhook host configured, running in polling mode")

async def close_bot():
    """Close bot session"""
    await bot.session.close()

def register_routers():
    """Register all routers"""
    from app.routers import join, payments, commands, members
    
    # Register routers in order
    dp.include_router(payments.router)
    dp.include_router(join.router)
    dp.include_router(commands.router)
    dp.include_router(members.router)
    
    logger.info("All routers registered")
