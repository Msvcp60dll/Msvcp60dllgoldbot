from fastapi import FastAPI, Request, Response, BackgroundTasks
from fastapi.responses import RedirectResponse
from contextlib import asynccontextmanager
import logging
import os
import time
from datetime import datetime, timezone
from app.config import settings
from app.db import db
from app.bot import bot, dp, setup_bot, close_bot, register_routers
from app.scheduler import start_scheduler, stop_scheduler
from app.dashboard import dashboard_json, dashboard_html
from app.routers.payments import create_subscription_invoice_link

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle"""
    # Startup
    logger.info("Starting application...")
    
    # Connect to database
    await db.connect()
    
    # Setup bot
    await setup_bot()
    
    # Register routers
    register_routers()
    
    # Start scheduler
    start_scheduler()
    
    logger.info("Application started successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down application...")
    
    # Stop scheduler
    stop_scheduler()
    
    # Close bot
    await close_bot()
    
    # Disconnect database
    await db.disconnect()
    
    logger.info("Application shut down successfully")

# Create FastAPI app
app = FastAPI(
    title="Telegram Stars Membership Bot",
    version="1.3",
    lifespan=lifespan
)

@app.post(f"/webhook/{settings.webhook_secret}")
async def webhook_handler(request: Request):
    """Handle Telegram webhook"""
    try:
        update_dict = await request.json()
        telegram_update = dp.resolve_update(update_dict)
        
        # Process update
        await dp.feed_update(bot=bot, update=telegram_update)
        
        return Response(status_code=200)
        
    except Exception as e:
        logger.error(f"Webhook error: {e}", exc_info=True)
        return Response(status_code=200)  # Always return 200 to Telegram

@app.get("/r/sub")
async def redirect_subscription(
    u: int,
    v: str = "A",
    p: int = 0,
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """Redirect tracker for subscription links"""
    try:
        # Create subscription invoice link
        link = await create_subscription_invoice_link(u, p)
        
        # Add timestamp to prevent caching
        timestamp = int(time.time())
        final_link = f"{link}&_t={timestamp}"
        
        # Log event in background
        async def log_click():
            await db.log_event(u, "sub_link_click", {
                "ab_variant": v,
                "price": p
            })
        
        background_tasks.add_task(log_click)
        
        # Return redirect with no-cache headers
        return RedirectResponse(
            url=final_link,
            status_code=307,
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
                "Vary": "User-Agent"
            }
        )
        
    except Exception as e:
        logger.error(f"Redirect error for user {u}: {e}")
        return Response(content="Error creating subscription link", status_code=500)

@app.get("/healthz")
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    # Simple health check that always returns OK
    # We don't check database/bot here to avoid initialization issues
    return {
        "status": "healthy",
        "service": "telegram-stars-membership",
        "version": "1.3",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

# Dashboard routes
app.get("/admin/api/summary")(dashboard_json)
app.get("/admin/dashboard")(dashboard_html)

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "Telegram Stars Membership Bot",
        "version": "1.3",
        "status": "running"
    }

async def main():
    """Main entry point for async execution"""
    logger.info("Main application started")
    # The FastAPI app will be served by uvicorn from start_bot.py
    
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv('PORT', 8080))
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level=settings.log_level.lower()
    )