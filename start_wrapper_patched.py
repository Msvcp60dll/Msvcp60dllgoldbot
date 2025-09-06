#!/usr/bin/env python3
"""
Production wrapper for Railway deployment with immediate health endpoint.
"""

import os
import sys
import time
import subprocess
import signal
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import json

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class HealthHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Suppress access logs for health checks
        if "/health" not in args[0]:
            logger.info(f"Health server: {args[0]}")
    
    def do_GET(self):
        if self.path in ['/health', '/healthz']:
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            response = {
                "status": "healthy",
                "service": "telegram-stars-membership",
                "version": "1.3",
                "wrapper": True
            }
            self.wfile.write(json.dumps(response).encode())
        else:
            self.send_response(404)
            self.end_headers()

def start_health_server(port):
    """Start health server in background thread"""
    server = HTTPServer(('0.0.0.0', port), HealthHandler)
    logger.info(f"Health server started on 0.0.0.0:{port}")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server

class ProcessManager:
    def __init__(self):
        self.process = None
        self.should_exit = False
        self.restart_count = 0
        self.max_restarts = 5
        self.restart_delay = 5
        
    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.should_exit = True
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                logger.warning("Process didn't terminate, killing...")
                self.process.kill()
        sys.exit(0)
    
    def start_process(self):
        """Start the main application"""
        logger.info("Starting main application...")
        self.process = subprocess.Popen(
            [sys.executable, "-u", "main.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )
        return self.process
    
    def run(self):
        """Main run loop with restart logic"""
        # Register signal handlers
        signal.signal(signal.SIGTERM, self.signal_handler)
        signal.signal(signal.SIGINT, self.signal_handler)
        
        while not self.should_exit and self.restart_count < self.max_restarts:
            try:
                process = self.start_process()
                
                # Stream output
                for line in process.stdout:
                    print(line, end='', flush=True)
                
                # Wait for process to complete
                return_code = process.wait()
                
                if return_code == 0:
                    logger.info("Process exited normally")
                    break
                else:
                    logger.error(f"Process exited with code {return_code}")
                    
                    if self.restart_count < self.max_restarts:
                        self.restart_count += 1
                        logger.info(f"Restarting in {self.restart_delay} seconds... (attempt {self.restart_count}/{self.max_restarts})")
                        time.sleep(self.restart_delay)
                        self.restart_delay = min(self.restart_delay * 2, 60)  # Exponential backoff
                    else:
                        logger.error("Max restarts reached, exiting...")
                        sys.exit(1)
                        
            except KeyboardInterrupt:
                logger.info("Keyboard interrupt received")
                self.should_exit = True
                if process:
                    process.terminate()
                    process.wait()
                break
                
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                self.restart_count += 1
                if self.restart_count < self.max_restarts:
                    time.sleep(self.restart_delay)
                else:
                    sys.exit(1)

def check_environment():
    """Verify required environment variables"""
    required_vars = [
        "BOT_TOKEN",
        "GROUP_CHAT_ID", 
        "OWNER_IDS",
        "SUPABASE_URL",
        "SUPABASE_SERVICE_KEY",
        "WEBHOOK_SECRET"
    ]
    
    missing = []
    for var in required_vars:
        if not os.environ.get(var):
            missing.append(var)
    
    if missing:
        logger.error(f"Missing required environment variables: {', '.join(missing)}")
        logger.error("Please set all required environment variables before starting")
        # Don't exit immediately - let health server stay up
        return False
    
    logger.info("Environment check passed")
    return True

def wait_for_database():
    """Wait for database to be ready (non-blocking)"""
    import asyncio
    import asyncpg
    
    # Import settings only if env vars are set
    try:
        from app.config import settings
    except Exception as e:
        logger.error(f"Cannot import settings: {e}")
        return False
    
    async def check_db():
        max_attempts = 10
        attempt = 0
        
        while attempt < max_attempts:
            try:
                conn = await asyncpg.connect(settings.database_url)
                await conn.fetchval("SELECT 1")
                await conn.close()
                logger.info("Database connection successful")
                return True
            except Exception as e:
                attempt += 1
                logger.warning(f"Database connection attempt {attempt} failed: {e}")
                if attempt < max_attempts:
                    await asyncio.sleep(2)
        
        return False
    
    logger.info("Checking database connection...")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    result = loop.run_until_complete(check_db())
    loop.close()
    
    if not result:
        logger.error("Failed to connect to database after multiple attempts")
    
    return result

if __name__ == "__main__":
    logger.info("=" * 50)
    logger.info("Starting Telegram Stars Membership Bot v1.3")
    logger.info("=" * 50)
    
    # Start health server IMMEDIATELY
    port = int(os.getenv("PORT", 8080))
    health_server = start_health_server(port)
    logger.info(f"Health endpoints available at /health and /healthz on port {port}")
    
    # Check environment (non-blocking)
    env_ok = check_environment()
    
    if not env_ok:
        logger.error("Environment check failed, entering health-only mode")
        # Keep health server running
        while True:
            time.sleep(60)
            logger.info("Health-only mode: awaiting proper configuration...")
    
    # Wait for database (with timeout)
    db_ok = wait_for_database()
    
    if not db_ok:
        logger.warning("Database not ready, but continuing anyway...")
        # Don't exit - let the app handle reconnection
    
    # Start process manager
    manager = ProcessManager()
    manager.run()
    
    logger.info("Wrapper exiting...")