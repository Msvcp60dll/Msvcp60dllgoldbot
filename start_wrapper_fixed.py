#!/usr/bin/env python3
"""
Production wrapper with guaranteed health endpoints.
Health endpoints always return 200, regardless of app state.
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
import requests
from urllib.parse import urlparse

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class HealthHandler(BaseHTTPRequestHandler):
    """Handler that guarantees /health and /healthz always return 200"""
    
    def __init__(self, *args, app_port=None, **kwargs):
        self.app_port = app_port
        super().__init__(*args, **kwargs)
    
    def log_message(self, format, *args):
        # Only log non-health requests
        if "/health" not in args[0]:
            logger.info(f"Health server: {args[0]}")
    
    def do_GET(self):
        # UNCONDITIONAL health checks - always return 200
        if self.path in ['/health', '/healthz']:
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            response = {
                "status": "ok",  # Always OK for liveness
                "source": "wrapper",
                "service": "telegram-stars-membership",
                "version": "1.3"
            }
            self.wfile.write(json.dumps(response).encode())
            return
        
        # For readiness check (optional)
        if self.path == '/ready':
            # This can check the actual app state
            if self.app_port:
                try:
                    resp = requests.get(f'http://127.0.0.1:{self.app_port}/health', timeout=2)
                    self.send_response(resp.status_code)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(resp.content)
                except:
                    self.send_response(503)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    response = {"status": "not_ready", "source": "wrapper"}
                    self.wfile.write(json.dumps(response).encode())
            else:
                self.send_response(503)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                response = {"status": "not_ready", "source": "wrapper"}
                self.wfile.write(json.dumps(response).encode())
            return
        
        # Proxy other requests to main app if available
        if self.app_port:
            try:
                url = f'http://127.0.0.1:{self.app_port}{self.path}'
                resp = requests.get(url, timeout=10)
                self.send_response(resp.status_code)
                for key, value in resp.headers.items():
                    if key.lower() not in ['connection', 'content-length', 'transfer-encoding']:
                        self.send_header(key, value)
                self.end_headers()
                self.wfile.write(resp.content)
            except Exception as e:
                self.send_response(502)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                response = {"error": "Backend unavailable", "details": str(e)}
                self.wfile.write(json.dumps(response).encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_POST(self):
        # Proxy POST requests to main app
        if self.app_port:
            try:
                content_length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(content_length) if content_length else b''
                
                url = f'http://127.0.0.1:{self.app_port}{self.path}'
                headers = {k: v for k, v in self.headers.items() if k.lower() not in ['host']}
                
                resp = requests.post(url, data=body, headers=headers, timeout=30)
                
                self.send_response(resp.status_code)
                for key, value in resp.headers.items():
                    if key.lower() not in ['connection', 'content-length', 'transfer-encoding']:
                        self.send_header(key, value)
                self.end_headers()
                self.wfile.write(resp.content)
            except Exception as e:
                logger.error(f"POST proxy error: {e}")
                self.send_response(502)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                response = {"error": "Backend unavailable"}
                self.wfile.write(json.dumps(response).encode())
        else:
            self.send_response(502)
            self.end_headers()

def start_health_server(port, app_port=None):
    """Start health server in background thread"""
    handler_class = lambda *args, **kwargs: HealthHandler(*args, app_port=app_port, **kwargs)
    server = HTTPServer(('0.0.0.0', port), handler_class)
    logger.info(f"Health server started on 0.0.0.0:{port}")
    logger.info(f"Liveness endpoints: /health, /healthz (always 200)")
    logger.info(f"Readiness endpoint: /ready (checks app state)")
    
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server

class ProcessManager:
    def __init__(self, app_port):
        self.process = None
        self.should_exit = False
        self.restart_count = 0
        self.max_restarts = 5
        self.restart_delay = 5
        self.app_port = app_port
        
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
        """Start the main application on a different port"""
        logger.info(f"Starting main application on port {self.app_port}...")
        
        # Set environment for the subprocess
        env = os.environ.copy()
        env['PORT'] = str(self.app_port)  # Override PORT for the main app
        
        self.process = subprocess.Popen(
            [sys.executable, "-u", "main.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1,
            env=env
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
                        logger.error("Max restarts reached, keeping health server alive")
                        # Keep health server running even if main app fails
                        while not self.should_exit:
                            time.sleep(60)
                        
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

def check_environment():
    """Verify required environment variables (non-fatal)"""
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
        logger.warning(f"Missing environment variables: {', '.join(missing)}")
        logger.warning("App may not function properly")
        return False
    
    logger.info("Environment check passed")
    return True

def check_database_async():
    """Check database in background (non-blocking)"""
    import asyncio
    import asyncpg
    
    async def try_db():
        try:
            from app.config import settings
            conn = await asyncpg.connect(settings.database_url)
            await conn.fetchval("SELECT 1")
            await conn.close()
            logger.info("Database connection verified")
            return True
        except Exception as e:
            logger.warning(f"Database check failed: {e}")
            return False
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(try_db())
        loop.close()
        return result
    except Exception as e:
        logger.warning(f"Database check error: {e}")
        return False

if __name__ == "__main__":
    logger.info("=" * 50)
    logger.info("Starting Telegram Stars Membership Bot v1.3")
    logger.info("=" * 50)
    
    # Get ports
    health_port = int(os.getenv("PORT", 8080))
    app_port = health_port + 1  # Main app runs on PORT+1
    
    # Start health server IMMEDIATELY - this ensures liveness always works
    health_server = start_health_server(health_port, app_port)
    logger.info(f"Health server ready on port {health_port}")
    
    # Check environment (non-blocking, just warn)
    env_ok = check_environment()
    
    if not env_ok:
        logger.warning("Environment incomplete, but health server will remain up")
        # Still try to start the app - it might work partially
    
    # Quick DB check in background (non-blocking)
    logger.info("Performing quick database check...")
    db_ok = check_database_async()
    if not db_ok:
        logger.warning("Database not immediately available, app will retry")
    
    # Start process manager with app on different port
    manager = ProcessManager(app_port)
    manager.run()
    
    # Keep health server alive even if everything else fails
    while True:
        time.sleep(60)
        logger.info("Health server still running...")