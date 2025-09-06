from fastapi import FastAPI, Request, Response, BackgroundTasks, Depends
from fastapi.responses import RedirectResponse
from contextlib import asynccontextmanager
import os
import time
import uuid
import json
from datetime import datetime, timezone
from app.config import settings
from app.db import db
from app.bot import bot, dp, setup_bot, close_bot, register_routers
from app.scheduler import start_scheduler, stop_scheduler
from app.dashboard_secure import dashboard_json_secure, dashboard_html_secure
from app.dashboard_enhanced import (
    dashboard_api_summary,
    dashboard_html_enhanced,
    export_overdue_csv
)
from app.routers.payments import create_subscription_invoice_link
from app.migrations.runner import MigrationRunner
from app.middleware import CorrelationIDMiddleware, WebhookLoggingMiddleware
from app.logging_config import (
    get_logger,
    set_correlation_id,
    set_request_start,
    log_performance,
    BusinessEvents
)
from app.security import (
    RateLimitMiddleware,
    SecurityMiddleware,
    TimeoutMiddleware,
    validate_webhook_request
)
from app.validators import (
    WebhookUpdateData,
    SubscriptionLinkParams,
    constant_time_compare
)
from app.health import (
    liveness_check,
    readiness_check,
    detailed_health_check
)
from app.retry_processor import (
    start_retry_processor,
    stop_retry_processor
)

# Initialize structured logging
logger = get_logger(__name__)

def validate_environment():
    """Validate required environment variables on startup"""
    required_vars = [
        "BOT_TOKEN",
        "DATABASE_URL",
        "GROUP_CHAT_ID",
        "WEBHOOK_SECRET"
    ]
    
    missing = []
    for var in required_vars:
        if not os.getenv(var):
            missing.append(var)
    
    if missing:
        logger.error(f"Missing required environment variables: {', '.join(missing)}")
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
    
    logger.info("✅ Environment validation passed")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle"""
    # Validate environment first
    validate_environment()
    
    # Startup
    start_time = time.time()
    logger.info(
        "application.startup_initiated",
        version="1.3",
        environment=os.getenv('ENVIRONMENT', 'production')
    )
    
    # Connect to database
    try:
        await db.connect()
        # Verify connection works
        await db.fetchval("SELECT 1")
        logger.info("✅ Database connected")
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        raise
    
    # Run pending migrations
    try:
        logger.info("migrations.check_started")
        migration_start = time.time()
        runner = MigrationRunner(settings.database_url)
        count = await runner.run_pending_migrations()
        migration_duration = int((time.time() - migration_start) * 1000)
        
        if count > 0:
            logger.info(
                "migrations.applied",
                count=count,
                duration_ms=migration_duration
            )
        else:
            logger.info(
                "migrations.up_to_date",
                duration_ms=migration_duration
            )
            
    except Exception as e:
        logger.error(
            "migrations.failed",
            exception=e
        )
        # Non-critical - continue startup even if migrations fail
        # This allows the app to run even if migrations were already applied manually
    
    # Setup bot
    try:
        await setup_bot()
        
        # Verify webhook is set
        webhook_info = await bot.get_webhook_info()
        if webhook_info and webhook_info.url:
            logger.info(f"✅ Webhook configured: {webhook_info.url[:50]}...")
        else:
            logger.warning("⚠️ Webhook not configured - bot may not receive updates")
        
        logger.info("✅ Bot setup completed")
    except Exception as e:
        logger.error(f"❌ Bot setup failed: {e}")
        raise
    
    # Register routers
    register_routers()
    logger.info("✅ Routers registered")
    
    # Start scheduler
    start_scheduler()
    logger.info("✅ Scheduler started")
    
    # Start retry processor (disabled due to missing schema columns)
    # await start_retry_processor() 
    logger.info("⚠️ Retry processor disabled (schema incomplete)")
    
    # All systems go!
    logger.info("🚀 Bot started successfully")
    logger.info(f"Environment: {os.getenv('ENVIRONMENT', 'production')}")
    logger.info(f"Group ID: {settings.group_chat_id}")
    logger.info(f"Webhook: {settings.webhook_url if settings.webhook_url else 'Not configured'}")
    
    yield
    
    # Shutdown
    shutdown_start = time.time()
    logger.info("application.shutdown_initiated")
    
    # Stop retry processor (was disabled)
    # stop_retry_processor()
    logger.info("retry_processor.was_disabled")
    
    # Stop scheduler
    stop_scheduler()
    logger.info("scheduler.stopped")
    
    # Close bot
    await close_bot()
    logger.info("bot.closed")
    
    # Disconnect database
    await db.disconnect()
    
    shutdown_duration = int((time.time() - shutdown_start) * 1000)
    logger.info(
        "application.shutdown_completed",
        duration_ms=shutdown_duration
    )

# Create FastAPI app
app = FastAPI(
    title="Telegram Stars Membership Bot",
    version="1.3",
    lifespan=lifespan
)

# Add middleware (order matters - security first)
app.add_middleware(TimeoutMiddleware)  # Timeout protection
app.add_middleware(SecurityMiddleware)  # Security headers and validation
app.add_middleware(RateLimitMiddleware)  # Rate limiting
app.add_middleware(CorrelationIDMiddleware)  # Correlation IDs
app.add_middleware(WebhookLoggingMiddleware)  # Webhook logging

@app.post(f"/webhook/{settings.webhook_secret}")
@log_performance("webhook.processing")
async def webhook_handler(request: Request):
    """Handle Telegram webhook"""
    start_time = time.time()
    
    # Extract or create correlation ID
    correlation_id = (
        request.headers.get("X-Correlation-ID") or
        f"webhook-{int(time.time())}-{uuid.uuid4().hex[:8]}"
    )
    set_correlation_id(correlation_id)
    
    try:
        # Verify webhook authenticity with constant-time comparison
        expected = settings.effective_telegram_secret
        if expected:
            provided = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
            if not provided or not constant_time_compare(provided, expected):
                logger.warning(
                    "webhook.auth_failed",
                    provided_token_exists=bool(provided),
                    correlation_id=correlation_id
                )
                return Response(status_code=401)
        
        # Parse and validate webhook data
        update_dict = await request.json()
        
        # Validate update structure
        try:
            webhook_data = WebhookUpdateData(**update_dict)
        except Exception as validation_error:
            logger.warning(
                "webhook.validation_failed",
                error=str(validation_error),
                correlation_id=correlation_id
            )
            return Response(status_code=200)  # Return 200 but don't process
        update_id = update_dict.get('update_id')
        
        logger.info(
            BusinessEvents.WEBHOOK_RECEIVED,
            update_id=update_id,
            correlation_id=correlation_id,
            update_type=update_dict.get('message', {}).get('successful_payment') and 'payment' or 'other'
        )
        
        from aiogram.types import Update
        telegram_update = Update(**update_dict)
        
        # Process update
        process_start = time.time()
        await dp.feed_update(bot=bot, update=telegram_update)
        process_duration = int((time.time() - process_start) * 1000)
        
        total_duration = int((time.time() - start_time) * 1000)
        
        logger.info(
            BusinessEvents.WEBHOOK_PROCESSED,
            update_id=update_id,
            correlation_id=correlation_id,
            process_duration_ms=process_duration,
            total_duration_ms=total_duration
        )
        
        return Response(status_code=200)
        
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        
        logger.error(
            BusinessEvents.WEBHOOK_FAILED,
            exception=e,
            correlation_id=correlation_id,
            duration_ms=duration_ms
        )
        return Response(status_code=200)  # Always return 200 to Telegram

@app.get("/r/sub")
async def redirect_subscription(
    params: SubscriptionLinkParams = Depends(),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """Redirect tracker for subscription links with validation"""
    try:
        # Extract validated parameters
        user_id = params.u
        variant = params.v
        price = params.p
        
        # Log the validated request
        logger.info(
            "subscription.redirect_request",
            user_id=user_id,
            variant=variant,
            price=price
        )
        
        # Create subscription invoice link
        link = await create_subscription_invoice_link(user_id, price)
        
        # Add timestamp to prevent caching
        timestamp = int(time.time())
        final_link = f"{link}&_t={timestamp}"
        
        # Log event in background
        async def log_click():
            await db.log_event(user_id, "sub_link_click", {
                "ab_variant": variant,
                "price": price
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
        
    except ValueError as e:
        logger.warning(
            "subscription.redirect_validation_error",
            error=str(e)
        )
        return Response(content="Invalid parameters", status_code=400)
    except Exception as e:
        logger.error(
            "subscription.redirect_error",
            user_id=getattr(params, 'u', None),
            exception=e
        )
        return Response(content="Error creating subscription link", status_code=500)

@app.get("/health/live")
async def health_live():
    """Liveness probe endpoint"""
    return await liveness_check()

@app.get("/health/ready")
async def health_ready():
    """Readiness probe endpoint"""
    response, status_code = await readiness_check()
    return Response(
        content=json.dumps(response),
        status_code=status_code,
        media_type="application/json"
    )

@app.get("/health/detailed")
async def health_detailed():
    """Detailed health check endpoint"""
    response, status_code = await detailed_health_check()
    return Response(
        content=json.dumps(response),
        status_code=status_code,
        media_type="application/json"
    )

@app.get("/healthz")
@app.get("/health")
async def health_check():
    """Basic health check endpoint (backward compatibility)"""
    return await liveness_check()

# Dashboard routes (secured)
# Legacy dashboard endpoints
app.get("/admin/api/summary/legacy")(dashboard_json_secure)
app.get("/admin/dashboard/legacy")(dashboard_html_secure)

# Enhanced dashboard endpoints
app.get("/admin/api/summary")(dashboard_api_summary)
app.get("/admin/dashboard")(dashboard_html_enhanced)
app.get("/admin/api/overdue/csv")(export_overdue_csv)

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
    
    # Check if wrapper is handling health endpoints
    if os.getenv("WRAPPER_HEALTH_ACTIVE") == "true":
        # Wrapper is handling health on PORT, so use a different port for the app
        port = int(os.getenv('APP_PORT', int(os.getenv('PORT', 8080)) + 1))
        logger.info(f"Wrapper detected, using port {port} for main app")
    else:
        # Normal mode - use PORT directly
        port = int(os.getenv('PORT', 8080))
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level=settings.log_level.lower()
    )
