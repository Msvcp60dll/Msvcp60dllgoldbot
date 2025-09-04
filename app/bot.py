from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand
from aiogram.webhook.aiohttp_server import SimpleRequestHandler
import logging
from app.config import settings

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
    
    # Set webhook if host is configured
    if settings.webhook_host:
        webhook_url = settings.webhook_url
        await bot.set_webhook(
            url=webhook_url,
            allowed_updates=[
                "message",
                "callback_query",
                "chat_join_request",
                "chat_member",
                "pre_checkout_query"
            ],
            drop_pending_updates=True
        )
        logger.info(f"Webhook set to {webhook_url}")
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