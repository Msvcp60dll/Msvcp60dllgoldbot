#!/usr/bin/env python3
"""
Simple startup script that just runs the FastAPI app directly
"""
import os
import sys
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logger.info("Starting Telegram Stars Membership Bot...")
    logger.info(f"Python version: {sys.version}")
    logger.info(f"Working directory: {os.getcwd()}")
    logger.info(f"PORT: {os.getenv('PORT', '8080')}")
    
    # Import and run the FastAPI app with uvicorn
    import uvicorn
    from main import app
    
    port = int(os.getenv('PORT', 8080))
    
    logger.info(f"Starting FastAPI on port {port}...")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info",
        access_log=True
    )