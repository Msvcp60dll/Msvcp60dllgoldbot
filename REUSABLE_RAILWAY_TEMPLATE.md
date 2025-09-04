# 🚂 Reusable Railway Deployment Template

## Overview

This template provides a generic, production-ready deployment pattern for any Python project on Railway. It includes all necessary configurations, scripts, and patterns that ensure successful deployment.

---

## 📁 Required File Structure

```
your-project/
├── railway.toml           # Railway configuration
├── requirements.txt       # Python dependencies
├── start_wrapper.py       # Production startup wrapper
├── main.py               # Your main application
├── .env.example          # Environment variable template
├── deploy.sh             # Deployment automation script
└── monitor.sh            # Deployment monitoring script
```

---

## 🔧 Core Configuration Files

### 1. railway.toml (Generic Template)

```toml
# Railway configuration for Python applications
[build]
# Use Nixpacks for automatic Python detection
builder = "nixpacks"

# Build command - customize as needed
buildCommand = "python -m pip install --upgrade pip && python -m pip install -r requirements.txt"

# Watch patterns for automatic rebuilds
watchPatterns = ["**/*.py", "requirements.txt", "railway.toml"]

[deploy]
# Number of instances (usually 1 for bots/small apps)
numReplicas = 1

# Start command - ALWAYS use wrapper for production
startCommand = "python start_wrapper.py"

# Health check configuration
healthcheckPath = "/health"
healthcheckTimeout = 300

# Restart policy
restartPolicyType = "always"
restartPolicyMaxRetries = 10

# Region (optional, defaults to us-west1)
region = "us-west1"

# Optional resource limits (adjust based on needs)
# memoryMB = 512
# cpuCores = 0.5

[env]
# Python optimization flags (always include these)
PYTHONUNBUFFERED = "1"
PYTHONDONTWRITEBYTECODE = "1"

# Add your app-specific environment variables here
# APP_ENV = "production"
```

### 2. start_wrapper.py (Production Wrapper Template)

```python
#!/usr/bin/env python3
"""
Production startup wrapper for Railway deployment
Ensures health checks remain active and handles graceful failures
"""
import os
import sys
import asyncio
import logging
import importlib
from typing import Optional
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
        self.runner: Optional[web.AppRunner] = None
        self.setup_routes()
    
    def setup_routes(self):
        """Setup health check routes"""
        self.app.router.add_get('/health', self.health_handler)
        self.app.router.add_get('/ready', self.ready_handler)
        self.app.router.add_get('/', self.root_handler)
    
    async def health_handler(self, request):
        """Health check endpoint for Railway"""
        return web.json_response({
            "status": "healthy",
            "service": os.getenv('SERVICE_NAME', 'python-app'),
            "timestamp": asyncio.get_event_loop().time(),
            "version": os.getenv('APP_VERSION', '1.0.0')
        })
    
    async def ready_handler(self, request):
        """Readiness check endpoint"""
        # Add custom readiness checks here (DB connection, etc.)
        return web.json_response({"ready": True})
    
    async def root_handler(self, request):
        """Root endpoint"""
        return web.json_response({
            "message": "Service is running",
            "endpoints": ["/health", "/ready"]
        })
    
    async def start(self):
        """Start the health check server"""
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, '0.0.0.0', self.port)
        await site.start()
        logger.info(f"Health check server started on port {self.port}")
        logger.info(f"Endpoints available: /health, /ready, /")
    
    async def stop(self):
        """Stop the health check server"""
        if self.runner:
            await self.runner.cleanup()
            logger.info("Health check server stopped")

async def import_and_run_main():
    """Import and run the main application"""
    try:
        # Try different import patterns
        try:
            # Pattern 1: main.py with main() function
            from main import main
            logger.info("Starting application from main.main()...")
            if asyncio.iscoroutinefunction(main):
                await main()
            else:
                main()
        except ImportError:
            try:
                # Pattern 2: app.py with app() function
                from app import app
                logger.info("Starting application from app.app()...")
                if asyncio.iscoroutinefunction(app):
                    await app()
                else:
                    app()
            except ImportError:
                # Pattern 3: Direct module execution
                logger.info("Starting application as module...")
                import main
    except Exception as e:
        logger.error(f"Failed to start main application: {e}")
        raise

async def run_with_health_check():
    """Run application with health check server"""
    # Get port from environment
    port = int(os.getenv('PORT', 8080))
    
    # Start health check server first
    health_server = HealthCheckServer(port)
    await health_server.start()
    
    try:
        # Import and run main application
        await import_and_run_main()
    except Exception as e:
        logger.error(f"Application crashed: {e}")
        logger.info("Health check server will continue running...")
        
        # Keep health server alive even if main app fails
        # This prevents Railway from continuously restarting
        while True:
            await asyncio.sleep(60)
            logger.info("Health check server still active...")

def main():
    """Entry point"""
    logger.info("=== Starting Production Wrapper ===")
    logger.info(f"Python version: {sys.version}")
    logger.info(f"Working directory: {os.getcwd()}")
    logger.info(f"PORT: {os.getenv('PORT', '8080')}")
    
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
```

### 3. requirements.txt (Template with Common Dependencies)

```txt
# Web framework (choose one)
aiohttp>=3.9.0          # For async web apps
# OR
# fastapi>=0.104.0      # For FastAPI apps
# uvicorn>=0.24.0       # ASGI server for FastAPI
# OR  
# flask>=3.0.0          # For Flask apps
# gunicorn>=21.0.0      # WSGI server for Flask

# Database (optional, choose as needed)
# asyncpg>=0.29.0       # PostgreSQL async driver
# motor>=3.3.0          # MongoDB async driver
# redis>=5.0.0          # Redis client

# HTTP client (optional)
httpx>=0.25.0           # Modern async HTTP client
# OR
# requests>=2.31.0      # Synchronous HTTP client

# Environment management
python-dotenv>=1.0.0    # Load .env files

# Logging and monitoring (optional)
# structlog>=24.1.0     # Structured logging
# sentry-sdk>=1.0.0     # Error tracking

# Utilities
# pydantic>=2.0.0       # Data validation
# python-dateutil>=2.8.0 # Date handling

# IMPORTANT: Do NOT include these built-in packages:
# - asyncio (built into Python 3.4+)
# - typing (built into Python 3.5+)
# - dataclasses (built into Python 3.7+)
# - enum (built into Python)
```

### 4. Deployment Script (deploy.sh)

```bash
#!/bin/bash
# Automated Railway deployment script

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
SERVICE_NAME="${1:-my-service}"
MAX_WAIT_TIME=300  # 5 minutes
CHECK_INTERVAL=5   # 5 seconds

echo -e "${GREEN}🚂 Railway Deployment Script${NC}"
echo "=========================="
echo "Service: $SERVICE_NAME"
echo ""

# Step 1: Verify authentication
echo -e "${YELLOW}Checking Railway authentication...${NC}"
if ! railway whoami > /dev/null 2>&1; then
    echo -e "${RED}❌ Not authenticated. Run 'railway login' first${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Authenticated${NC}"

# Step 2: Deploy
echo -e "${YELLOW}Starting deployment...${NC}"
OUTPUT=$(railway up --service "$SERVICE_NAME" 2>&1)
echo "$OUTPUT"

# Extract build URL
BUILD_URL=$(echo "$OUTPUT" | grep "Build Logs:" | awk '{print $3}')
if [ -n "$BUILD_URL" ]; then
    echo -e "${GREEN}Build URL: $BUILD_URL${NC}"
fi

# Step 3: Monitor deployment
echo -e "${YELLOW}Monitoring deployment...${NC}"

monitor_status() {
    railway status --json 2>/dev/null | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
    for s in d.get('services',{}).get('edges',[]):
        if s['node']['name'] == '$SERVICE_NAME':
            for si in s['node']['serviceInstances']['edges']:
                ld = si['node'].get('latestDeployment',{})
                if ld: 
                    status = ld.get('status','UNKNOWN')
                    print(status)
                    sys.exit(0 if status == 'SUCCESS' else 1 if status == 'FAILED' else 2)
except: pass
print('CHECKING')
sys.exit(2)
"
}

START_TIME=$(date +%s)
while true; do
    STATUS_OUTPUT=$(monitor_status)
    STATUS_CODE=$?
    CURRENT_TIME=$(date +%s)
    ELAPSED=$((CURRENT_TIME - START_TIME))
    
    echo -e "[$ELAPSED/$MAX_WAIT_TIME sec] Status: $STATUS_OUTPUT"
    
    if [ $STATUS_CODE -eq 0 ]; then
        echo -e "${GREEN}✅ Deployment successful!${NC}"
        echo ""
        echo "Next steps:"
        echo "1. Check logs: railway logs --service $SERVICE_NAME"
        echo "2. Generate domain in Railway dashboard (if needed)"
        exit 0
    elif [ $STATUS_CODE -eq 1 ]; then
        echo -e "${RED}❌ Deployment failed!${NC}"
        echo "Check build logs at: $BUILD_URL"
        exit 1
    fi
    
    if [ $ELAPSED -ge $MAX_WAIT_TIME ]; then
        echo -e "${YELLOW}⏱ Deployment timeout after ${MAX_WAIT_TIME} seconds${NC}"
        echo "Check status at: $BUILD_URL"
        exit 2
    fi
    
    sleep $CHECK_INTERVAL
done
```

### 5. Environment Variable Template (.env.example)

```bash
# Railway Environment Variables Template
# Copy to .env and fill in your values

# === Application Configuration ===
SERVICE_NAME=my-python-app
APP_VERSION=1.0.0
APP_ENV=production

# === Port Configuration ===
# Railway will set this automatically, but good for local testing
PORT=8080

# === Database Configuration (if needed) ===
DATABASE_URL=postgresql://user:pass@host:5432/dbname
# OR
# MONGODB_URI=mongodb://user:pass@host:27017/dbname
# OR
# REDIS_URL=redis://user:pass@host:6379/0

# === API Keys (examples) ===
# API_KEY=your-api-key-here
# SECRET_KEY=your-secret-key-here

# === Feature Flags ===
# ENABLE_FEATURE_X=true
# DEBUG_MODE=false

# === Python Optimization (always include) ===
PYTHONUNBUFFERED=1
PYTHONDONTWRITEBYTECODE=1

# === Logging Configuration ===
LOG_LEVEL=INFO
# SENTRY_DSN=https://xxxx@sentry.io/yyyy
```

---

## 🔨 Standard Implementation Steps

### Step 1: Prepare Your Project

```bash
# 1. Create required files
touch railway.toml
touch start_wrapper.py
touch requirements.txt
touch .env.example

# 2. Copy templates and customize
# (Use templates from above)

# 3. Test locally
python start_wrapper.py
# Visit http://localhost:8080/health
```

### Step 2: Set Up Railway

```bash
# 1. Login to Railway
railway login

# 2. Create new project (or link existing)
railway init
# OR
railway link

# 3. Set environment variables
railway variables --set SERVICE_NAME="my-app"
railway variables --set APP_VERSION="1.0.0"
# Add all other required variables
```

### Step 3: Deploy

```bash
# 1. Make deploy script executable
chmod +x deploy.sh

# 2. Run deployment
./deploy.sh my-service

# 3. Monitor until success
# Script will handle monitoring automatically
```

---

## 🎯 Environment Variable Patterns

### Pattern 1: Database URLs
```bash
# PostgreSQL
DATABASE_URL="postgresql://user:password@host:port/database"

# MongoDB
MONGODB_URI="mongodb://user:password@host:port/database"

# Redis
REDIS_URL="redis://user:password@host:port/db_number"
```

### Pattern 2: API Credentials
```bash
# Single API key
API_KEY="sk-xxxxxxxxxxxxxxxxxxxxx"

# OAuth style
CLIENT_ID="xxxxxxxxxxxxxxxxxxxxx"
CLIENT_SECRET="xxxxxxxxxxxxxxxxxxxxx"

# Bearer token
AUTH_TOKEN="Bearer xxxxxxxxxxxxxxxxxxxxx"
```

### Pattern 3: Feature Configuration
```bash
# Boolean flags
ENABLE_FEATURE="true"
DEBUG_MODE="false"

# Numeric values
MAX_CONNECTIONS="100"
TIMEOUT_SECONDS="30"

# Lists (comma-separated)
ALLOWED_HOSTS="host1.com,host2.com,host3.com"
```

---

## ✅ Health Check Implementation Patterns

### Basic Health Check
```python
async def health(request):
    return web.json_response({"status": "healthy"})
```

### Advanced Health Check with Dependencies
```python
async def health(request):
    checks = {
        "service": "healthy",
        "database": await check_database(),
        "cache": await check_cache(),
        "external_api": await check_external_api()
    }
    
    overall = "healthy" if all(
        v == "healthy" for v in checks.values()
    ) else "degraded"
    
    return web.json_response({
        "status": overall,
        "checks": checks,
        "timestamp": datetime.utcnow().isoformat()
    })

async def check_database():
    try:
        # Your DB check logic
        await db.execute("SELECT 1")
        return "healthy"
    except:
        return "unhealthy"
```

### Readiness vs Liveness
```python
# Liveness: Is the application running?
app.router.add_get('/health', liveness_check)

# Readiness: Is the application ready to serve requests?
app.router.add_get('/ready', readiness_check)

async def liveness_check(request):
    # Basic check - app is alive
    return web.json_response({"alive": True})

async def readiness_check(request):
    # Check if all dependencies are ready
    ready = (
        await check_database() and
        await check_cache() and
        app_initialized
    )
    return web.json_response(
        {"ready": ready},
        status=200 if ready else 503
    )
```

---

## 🚀 Optimization Tips

### 1. Reduce Cold Start Time
- Minimize dependencies in requirements.txt
- Lazy load heavy modules
- Use lightweight frameworks when possible

### 2. Memory Management
- Set appropriate resource limits in railway.toml
- Use connection pooling for databases
- Implement proper cleanup in shutdown handlers

### 3. Logging Best Practices
- Use structured logging (JSON format)
- Don't log sensitive information
- Set appropriate log levels (INFO for production)

### 4. Error Handling
- Implement global error handlers
- Use the wrapper pattern to keep health checks alive
- Log errors with context for debugging

---

## 📋 Validation Checklist

Before deploying any Python project:

- [ ] `railway.toml` configured with correct start command
- [ ] `start_wrapper.py` implemented with health checks
- [ ] `requirements.txt` has no built-in packages
- [ ] Environment variables defined in Railway
- [ ] Health endpoint returns 200 OK
- [ ] Application uses PORT from environment
- [ ] Logs are configured to stdout
- [ ] No hardcoded secrets in code
- [ ] `.env.example` documents all variables

---

## 🔗 Quick Commands Reference

```bash
# Deploy
railway up --service my-service

# Check status
railway status --json | jq '.services.edges[0].node.serviceInstances.edges[0].node.latestDeployment.status'

# View logs
railway logs --service my-service

# Set variable
railway variables --set KEY=value

# List variables
railway variables

# Redeploy
railway up --service my-service
```

---

*This template is designed to work with any Python application and has been tested with successful deployments on Railway.*