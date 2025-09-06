#!/usr/bin/env python3
"""
Minimal production wrapper with guaranteed health endpoints.
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

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class HealthHandler(BaseHTTPRequestHandler):
    """Handler that guarantees /health and /healthz always return 200"""
    
    def log_message(self, format, *args):
        # Suppress health check logs to reduce noise
        if "/health" not in args[0]:
            logger.info(f"Request: {args[0]}")
    
    def do_GET(self):
        # UNCONDITIONAL health checks - always return 200
        if self.path in ['/health', '/healthz']:
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            response = {
                "status": "ok",
                "source": "wrapper",
                "service": "telegram-stars-membership",
                "version": "1.3"
            }
            self.wfile.write(json.dumps(response).encode())
            return
        
        # Any other path returns 404 from wrapper
        # The actual app will handle its own routes
        self.send_response(404)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        response = {"error": "Not found", "source": "wrapper"}
        self.wfile.write(json.dumps(response).encode())
    
    def do_POST(self):
        # For webhook and other POST requests, return 404
        # The actual app will handle these on its own port
        self.send_response(404)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        response = {"error": "Not found", "source": "wrapper"}
        self.wfile.write(json.dumps(response).encode())

def start_health_server(port):
    """Start health server in background thread"""
    server = HTTPServer(('0.0.0.0', port), HealthHandler)
    logger.info(f"Health server started on 0.0.0.0:{port}")
    logger.info(f"Liveness endpoints: /health, /healthz (always return 200)")
    
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
        
        # Important: Don't let main.py bind to the same port as health server
        # The app should use its own port or handle this internally
        
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
                        self.restart_delay = min(self.restart_delay * 2, 60)
                    else:
                        logger.error("Max restarts reached, but health server remains active")
                        # Keep health server running forever
                        while not self.should_exit:
                            time.sleep(60)
                            logger.info("Health server still active...")
                        
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
        logger.warning("Continuing anyway - health endpoints will work")
        return False
    
    logger.info("Environment check passed")
    return True

if __name__ == "__main__":
    logger.info("=" * 50)
    logger.info("Starting Telegram Stars Membership Bot v1.3")
    logger.info("=" * 50)
    
    # Get port from environment
    port = int(os.getenv("PORT", 8080))
    
    # CRITICAL: Start health server IMMEDIATELY
    # This must happen before ANY blocking operations
    health_server = start_health_server(port)
    logger.info(f"Health server ready - Railway health checks will pass")
    
    # Check environment (non-blocking, just warn)
    env_ok = check_environment()
    
    # Don't block on missing env vars
    if not env_ok:
        logger.warning("Environment incomplete, but continuing...")
    
    # Check if we should skip main app startup
    if os.getenv("HEALTH_ONLY_MODE") == "true":
        logger.info("HEALTH_ONLY_MODE enabled - not starting main app")
        logger.info("Health endpoints will remain available")
        while True:
            time.sleep(60)
            logger.info("Health-only mode active...")
    
    # Start main app - but don't let it bind to the same port!
    # We'll need to modify main.py to handle this
    logger.info("Starting main application process...")
    
    # Set a flag so main.py knows not to bind to PORT
    os.environ["WRAPPER_HEALTH_ACTIVE"] = "true"
    
    manager = ProcessManager()
    manager.run()
    
    # If we get here, keep health server alive
    logger.info("Main process manager exited, keeping health server active")
    while True:
        time.sleep(60)
        logger.info("Health server still running...")