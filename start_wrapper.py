#!/usr/bin/env python3
"""
Production wrapper with health endpoints and request forwarding.
Health endpoints always return 200, all other requests forwarded to backend.
"""

import os
import sys
import asyncio
import signal
import logging
from aiohttp import web, ClientSession, ClientTimeout
import json

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Health paths that always return 200
HEALTH_PATHS = {"/health", "/healthz"}

class ProxyWrapper:
    def __init__(self, port: int):
        self.port = port
        self.backend_port = port + 1
        self.backend_base = f"http://127.0.0.1:{self.backend_port}"
        self.app = web.Application()
        self.session = None
        self.backend_process = None
        self._setup_routes()
    
    def _setup_routes(self):
        # Add catch-all handler for all methods and paths
        self.app.router.add_route("*", "/{path:.*}", self.handle_request)
    
    async def handle_request(self, request: web.Request):
        """Handle all incoming requests - health or proxy"""
        
        # Health check paths - always return 200
        if request.path in HEALTH_PATHS:
            return web.json_response({
                "status": "ok",
                "source": "wrapper",
                "service": "telegram-stars-membership",
                "version": "1.3"
            })
        
        # Proxy all other requests to backend
        try:
            # Initialize session if needed
            if not self.session:
                timeout = ClientTimeout(connect=10, total=30)
                self.session = ClientSession(timeout=timeout)
            
            # Build backend URL preserving path and query string
            backend_url = self.backend_base + str(request.rel_url)
            
            # Prepare headers to forward (skip hop-by-hop headers)
            headers = {}
            skip_headers = {'host', 'connection', 'keep-alive', 'transfer-encoding', 
                          'upgrade', 'proxy-authenticate', 'proxy-authorization', 
                          'te', 'trailer'}
            
            for key, value in request.headers.items():
                if key.lower() not in skip_headers:
                    headers[key] = value
            
            # Read request body if present
            body = await request.read() if request.body_exists else None
            
            # Log the proxied request (no bodies or secrets)
            logger.info(f"Proxy: {request.method} {request.path} -> backend:{self.backend_port}")
            
            # Forward request to backend
            async with self.session.request(
                method=request.method,
                url=backend_url,
                headers=headers,
                data=body,
                allow_redirects=False
            ) as backend_resp:
                # Read backend response
                backend_body = await backend_resp.read()
                
                # Create response with backend's status
                response = web.Response(
                    status=backend_resp.status,
                    body=backend_body
                )
                
                # Forward response headers (skip hop-by-hop)
                for key, value in backend_resp.headers.items():
                    if key.lower() not in skip_headers:
                        response.headers[key] = value
                
                logger.info(f"Proxy response: {request.method} {request.path} -> {backend_resp.status}")
                return response
                
        except asyncio.TimeoutError:
            logger.error(f"Backend timeout for {request.method} {request.path}")
            return web.json_response(
                {"error": "Backend timeout", "source": "wrapper"},
                status=502
            )
        except Exception as e:
            logger.error(f"Backend error for {request.method} {request.path}: {e}")
            return web.json_response(
                {"error": "Backend unavailable", "source": "wrapper"},
                status=502
            )
    
    async def start_backend(self):
        """Start the main application as subprocess"""
        logger.info(f"Starting main application on port {self.backend_port}")
        
        # Set environment for backend
        env = os.environ.copy()
        env['PORT'] = str(self.backend_port)
        env['WRAPPER_HEALTH_ACTIVE'] = 'true'
        env['APP_PORT'] = str(self.backend_port)
        
        # Start backend process
        self.backend_process = await asyncio.create_subprocess_exec(
            sys.executable, "-u", "main.py",
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT
        )
        
        # Forward backend output
        asyncio.create_task(self._forward_backend_output())
        
        # Give backend time to start
        await asyncio.sleep(2)
        logger.info(f"Backend started with PID {self.backend_process.pid}")
    
    async def _forward_backend_output(self):
        """Forward backend stdout to our stdout"""
        try:
            async for line in self.backend_process.stdout:
                print(line.decode().rstrip())
        except Exception as e:
            logger.error(f"Error forwarding backend output: {e}")
    
    async def cleanup(self):
        """Cleanup resources"""
        if self.session:
            await self.session.close()
        if self.backend_process:
            self.backend_process.terminate()
            await self.backend_process.wait()

async def check_environment():
    """Check environment variables (non-blocking)"""
    required = ["BOT_TOKEN", "GROUP_CHAT_ID", "OWNER_IDS", 
                "SUPABASE_URL", "SUPABASE_SERVICE_KEY", "WEBHOOK_SECRET"]
    missing = [v for v in required if not os.getenv(v)]
    
    if missing:
        logger.warning(f"Missing environment variables: {', '.join(missing)}")
        return False
    
    logger.info("Environment check passed")
    return True

async def main_async():
    """Main async entry point"""
    # Get port from environment
    port = int(os.getenv("PORT", 8080))
    
    logger.info("=" * 50)
    logger.info("Starting Telegram Stars Membership Bot v1.3")
    logger.info(f"Wrapper binding to 0.0.0.0:{port}")
    logger.info(f"Backend will run on port {port + 1}")
    logger.info("=" * 50)
    
    # Create proxy wrapper
    proxy = ProxyWrapper(port)
    
    # Check environment
    env_ok = await check_environment()
    if not env_ok:
        logger.warning("Environment incomplete, but health endpoints will work")
    
    # Check if health-only mode
    if os.getenv("HEALTH_ONLY_MODE") == "true":
        logger.info("HEALTH_ONLY_MODE enabled - not starting backend")
    else:
        # Start backend application
        await proxy.start_backend()
    
    # Start web server
    runner = web.AppRunner(proxy.app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    
    logger.info(f"Proxy server ready on 0.0.0.0:{port}")
    logger.info("Health endpoints: /health, /healthz (always 200)")
    logger.info(f"All other requests forwarded to backend on port {port + 1}")
    
    # Keep running forever
    stop_event = asyncio.Event()
    
    def handle_signal(sig, frame):
        logger.info(f"Received signal {sig}, shutting down...")
        stop_event.set()
    
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    
    try:
        await stop_event.wait()
    finally:
        await proxy.cleanup()
        await runner.cleanup()

def main():
    """Entry point"""
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        logger.info("Interrupted")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()