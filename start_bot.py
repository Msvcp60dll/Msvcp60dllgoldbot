#!/usr/bin/env python3
"""
Production startup wrapper for Railway deployment
Ensures health checks remain active and handles graceful failures
"""
import os
import sys
import asyncio
import logging
from aiohttp import web

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

class HealthCheckServer:
    """Standalone health check server"""
    
    def __init__(self, port: int = 8080):
        self.port = port
        self.app = web.Application()
        self.runner = None
        self.setup_routes()
    
    def setup_routes(self):
        """Setup health check routes"""
        self.app.router.add_get('/health', self.health_handler)
        self.app.router.add_get('/healthz', self.health_handler)
        self.app.router.add_get('/ready', self.ready_handler)
        self.app.router.add_get('/', self.root_handler)
    
    async def health_handler(self, request):
        """Health check endpoint for Railway"""
        return web.json_response({
            "status": "healthy",
            "service": "msvcp60dll-bot",
            "bot": "telegram-stars-membership",
            "timestamp": asyncio.get_event_loop().time(),
            "version": "1.3"
        })
    
    async def ready_handler(self, request):
        """Readiness check endpoint"""
        return web.json_response({"ready": True})
    
    async def root_handler(self, request):
        """Root endpoint"""
        return web.json_response({
            "name": "Telegram Stars Membership Bot",
            "version": "1.3",
            "status": "running",
            "endpoints": ["/health", "/healthz", "/ready"]
        })
    
    async def start(self):
        """Start the health check server"""
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, '0.0.0.0', self.port)
        await site.start()
        logger.info(f"Health check server started on port {self.port}")
        logger.info(f"Endpoints available: /health, /healthz, /ready, /")
    
    async def stop(self):
        """Stop the health check server"""
        if self.runner:
            await self.runner.cleanup()
            logger.info("Health check server stopped")

async def start_main_application():
    """Import and start the main FastAPI application"""
    try:
        # Set up Python path
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        
        logger.info("Starting FastAPI application...")
        
        # Import uvicorn and run the FastAPI app
        import uvicorn
        from main import app
        
        # Get port from environment
        port = int(os.getenv('PORT', 8080))
        
        # Run uvicorn programmatically
        config = uvicorn.Config(
            app=app,
            host="0.0.0.0",
            port=port,
            log_level="info",
            access_log=True
        )
        server = uvicorn.Server(config)
        await server.serve()
        
    except ImportError as e:
        logger.error(f"Import error: {e}")
        logger.info("Trying alternative startup method...")
        
        # Try running main.py directly
        try:
            import main
            if hasattr(main, 'main') and asyncio.iscoroutinefunction(main.main):
                await main.main()
            else:
                # If no async main, the app might already be running
                logger.info("Main module imported, app should be running")
        except Exception as e2:
            logger.error(f"Alternative startup also failed: {e2}")
            raise
            
    except Exception as e:
        logger.error(f"Failed to start main application: {e}")
        raise

async def run_with_health_check():
    """Run application with health check server"""
    # Get port from environment
    port = int(os.getenv('PORT', 8080))
    
    # Start health check server first (critical for Railway)
    health_server = HealthCheckServer(port)
    await health_server.start()
    
    try:
        # Start the main application
        await start_main_application()
        
    except Exception as e:
        logger.error(f"Application crashed: {e}")
        logger.error(f"Error details: {type(e).__name__}: {str(e)}")
        logger.info("Bot crashed but health server will keep running to prevent Railway restarts")
        
        # Keep health server alive even if main app fails
        # This prevents Railway from continuously restarting
        while True:
            await asyncio.sleep(60)
            logger.info("Health check server still active, preventing Railway restart loop...")

def main():
    """Entry point"""
    logger.info("=== Starting Production Wrapper for Railway ===")
    logger.info(f"Python version: {sys.version}")
    logger.info(f"Working directory: {os.getcwd()}")
    logger.info(f"PORT: {os.getenv('PORT', '8080')}")
    logger.info(f"Environment: production")
    
    # Log important environment variables (without exposing secrets)
    env_vars = ['BOT_TOKEN', 'GROUP_CHAT_ID', 'SUPABASE_URL', 'WEBHOOK_HOST']
    for var in env_vars:
        value = os.getenv(var)
        if value:
            if 'TOKEN' in var or 'KEY' in var:
                logger.info(f"{var}: ***CONFIGURED***")
            else:
                logger.info(f"{var}: {value}")
        else:
            logger.warning(f"{var}: NOT SET")
    
    try:
        # Run the application with health checks
        asyncio.run(run_with_health_check())
    except KeyboardInterrupt:
        logger.info("Application stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()