#!/usr/bin/env python3
"""
Run the bot in polling mode for testing
"""
import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

BOT_TOKEN = "8263837787:AAE_kJD3YYM5L_7Hd28uCkgvvjqxFylCIWQ"

async def main():
    """Run bot in polling mode"""
    # Initialize bot
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML,
            link_preview_is_disabled=True
        )
    )
    
    # Initialize dispatcher
    dp = Dispatcher()
    
    # Register routers
    from app.routers import join, payments, commands, members
    dp.include_router(payments.router)
    dp.include_router(join.router) 
    dp.include_router(commands.router)
    dp.include_router(members.router)
    
    # Delete webhook to use polling
    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Webhook deleted, starting polling mode")
    
    # Get bot info
    bot_info = await bot.get_me()
    logger.info(f"Bot @{bot_info.username} started in polling mode!")
    logger.info("Send /start to test the bot")
    
    # Start polling
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Bot error: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
        sys.exit(0)