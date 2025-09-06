# Railway Deployment Guide for Telegram Stars Bot

## Table of Contents
1. [Railway Fundamentals](#1-railway-fundamentals)
2. [Configuration Files](#2-configuration-files)
3. [Environment Variables](#3-environment-variables)
4. [Deployment Process](#4-deployment-process)
5. [Bot-Specific Configuration](#5-our-bot-specific-configuration)
6. [Monitoring & Logs](#6-monitoring--logs)
7. [Production Checklist](#7-production-checklist)

---

## 1. RAILWAY FUNDAMENTALS

### How Railway Detects and Builds Python Projects

Railway automatically detects Python projects by looking for:
- `requirements.txt` or `pyproject.toml` (Python dependency files)
- `main.py` or `app.py` (common entry points)
- `Procfile` (if present, used for start command)

### Nixpacks vs Dockerfile

**Nixpacks (Default)**
- Zero-configuration builds
- Automatic environment detection
- Faster builds (~6 seconds vs 15 seconds for Docker)
- Caches build layers automatically
- Default Python version: 3.8 (configurable)

**Dockerfile**
- Full control over build process
- Required for complex dependencies
- Railway prioritizes Dockerfile if present
- Must remove/rename Dockerfile to use Nixpacks

### Build and Start Commands

**Default Detection:**
```python
# Railway looks for these files in order:
1. main.py with app variable (FastAPI/Flask)
2. app.py with app variable
3. wsgi.py with application variable
```

**Custom Start Command:**
```bash
# For our bot (FastAPI + aiogram):
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

### Environment Detection

Railway automatically detects:
- Python version from `runtime.txt` or `.python-version`
- Dependencies from `requirements.txt`
- Framework from imports (FastAPI, Flask, Django)

---

## 2. CONFIGURATION FILES

### railway.json vs railway.toml

Both formats are functionally identical. Choose based on preference:

**railway.toml (Recommended for simplicity)**
```toml
[build]
builder = "NIXPACKS"
buildCommand = "pip install -r requirements.txt"

[deploy]
startCommand = "uvicorn app.main:app --host 0.0.0.0 --port $PORT"
healthcheckPath = "/health"
healthcheckTimeout = 300
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 3
```

**railway.json (Better for complex configs)**
```json
{
  "$schema": "https://railway.com/railway.schema.json",
  "build": {
    "builder": "NIXPACKS",
    "buildCommand": "pip install -r requirements.txt"
  },
  "deploy": {
    "startCommand": "uvicorn app.main:app --host 0.0.0.0 --port $PORT",
    "healthcheckPath": "/health",
    "healthcheckTimeout": 300,
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 3
  }
}
```

### Nixpacks Configuration

**nixpacks.toml (for advanced control)**
```toml
[phases.setup]
nixPkgs = ["python311", "postgresql"]

[phases.install]
cmds = ["pip install --upgrade pip", "pip install -r requirements.txt"]

[start]
cmd = "uvicorn app.main:app --host 0.0.0.0 --port $PORT"
```

### Python Version Configuration

**Option 1: Environment Variable**
```bash
NIXPACKS_PYTHON_VERSION=3.11
```

**Option 2: runtime.txt**
```
python-3.11
```

**Option 3: .python-version**
```
3.11
```

### Procfile (Alternative to railway config)
```
web: uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1
```

---

## 3. ENVIRONMENT VARIABLES

### Variable Precedence (Highest to Lowest)

1. **Railway Dashboard UI** - Overrides everything
2. **railway.toml/json** - Config as code
3. **.env file** - Local development (not deployed)
4. **Defaults** - Railway-provided variables

### Variable Types

**Service Variables** (Scoped to single service)
```bash
BOT_TOKEN=your_bot_token
DATABASE_URL=postgresql://...
```

**Shared Variables** (Project-wide)
```bash
# Reference in service:
DATABASE_URL=${{ shared.DATABASE_URL }}
```

**Railway-Provided Variables**
```bash
PORT                      # Dynamic port assignment
RAILWAY_PUBLIC_DOMAIN     # Public URL for your service
RAILWAY_PRIVATE_DOMAIN    # Internal service communication
RAILWAY_ENVIRONMENT       # Current environment name
RAILWAY_PROJECT_ID        # Project identifier
RAILWAY_SERVICE_ID        # Service identifier
```

### Variable Referencing

```bash
# Reference shared variable
PUBLIC_URL=https://${{ RAILWAY_PUBLIC_DOMAIN }}

# Reference from another service
API_URL=${{ backend.RAILWAY_PRIVATE_DOMAIN }}

# Self-reference with fallback
WEBHOOK_URL=${PUBLIC_BASE_URL:-${{ RAILWAY_PUBLIC_DOMAIN }}}
```

### Secrets Management

**Sealed Variables** (Most secure)
- Hidden from UI and API
- Not copied across environments
- Not available in CLI
- Perfect for tokens and keys

```bash
# Mark as sealed in Railway UI
BOT_TOKEN=[SEALED]
SUPABASE_SERVICE_KEY=[SEALED]
```

---

## 4. DEPLOYMENT PROCESS

### What Happens During 'railway up'

1. **Detection Phase**
   - Analyzes project structure
   - Detects language and framework
   - Selects build provider (Nixpacks/Docker)

2. **Build Phase**
   - Installs dependencies
   - Runs build commands
   - Creates deployment image
   - Caches layers for next build

3. **Deploy Phase**
   - Starts new container
   - Runs health checks
   - Routes traffic after health check passes
   - Removes old container

### Railway CLI Commands

```bash
# First-time setup
railway login
railway link  # Link to existing project

# Deployment
railway up    # Deploy current directory
railway up --detach  # Deploy without watching logs

# Environment management
railway environment  # Show current environment
railway variables    # List all variables
railway run python app/main.py  # Run locally with Railway env

# Logs and monitoring
railway logs
railway logs --tail 100
railway status

# Rollback
railway down  # Remove deployment
```

### Build Caching

Railway automatically caches:
- Python packages (pip cache)
- System packages (apt cache)
- Build artifacts

**Force rebuild without cache:**
```bash
railway up --no-cache
```

### Zero-Downtime Deployments

Requirements:
1. Health check endpoint returns 200
2. New deployment passes health check
3. Traffic switches automatically

```python
# app/main.py
@app.get("/health")
async def health_check():
    # Check critical dependencies
    try:
        await db.fetchval("SELECT 1")
        return {"status": "healthy", "timestamp": datetime.now().isoformat()}
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "error": str(e)}
        )
```

### Rollback Procedures

**Via CLI:**
```bash
railway logs  # Find deployment ID
railway rollback <deployment-id>
```

**Via Dashboard:**
1. Go to Deployments tab
2. Find previous successful deployment
3. Click "Rollback to this deployment"

---

## 5. OUR BOT SPECIFIC CONFIGURATION

### Optimal railway.toml for Telegram Bot

```toml
# railway.toml
[build]
builder = "NIXPACKS"
nixpacksPlan = {
  providers = ["python"],
  phases = {
    setup = {
      nixPkgs = ["python311", "postgresql"]
    }
  }
}

[deploy]
startCommand = "python -m app.main"
healthcheckPath = "/health"
healthcheckTimeout = 300
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 3

[variables]
PYTHONUNBUFFERED = "1"
PYTHONDONTWRITEBYTECODE = "1"
```

### Health Check for Telegram Bots

```python
# app/main.py
from fastapi import FastAPI
from app.db import db
from app.bot import bot

app = FastAPI()

@app.get("/health")
async def health_check():
    """Railway health check endpoint"""
    checks = {
        "database": False,
        "telegram": False,
        "webhook": False
    }
    
    # Check database
    try:
        await db.fetchval("SELECT 1")
        checks["database"] = True
    except:
        pass
    
    # Check Telegram connection
    try:
        me = await bot.get_me()
        checks["telegram"] = me.username is not None
    except:
        pass
    
    # Check webhook
    try:
        webhook = await bot.get_webhook_info()
        checks["webhook"] = webhook.url is not None
    except:
        pass
    
    all_healthy = all(checks.values())
    return JSONResponse(
        status_code=200 if all_healthy else 503,
        content={
            "status": "healthy" if all_healthy else "degraded",
            "checks": checks,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    )
```

### Webhook URL Formation

```python
# app/config.py
import os

# Railway provides RAILWAY_PUBLIC_DOMAIN
public_domain = os.getenv("RAILWAY_PUBLIC_DOMAIN")
if public_domain:
    # Railway domain doesn't include https://
    WEBHOOK_URL = f"https://{public_domain}/webhook"
else:
    # Fallback to manual config
    WEBHOOK_URL = f"https://{os.getenv('PUBLIC_BASE_URL')}/webhook"
```

### Database Connection Pooling

```python
# app/db.py
# Optimal settings for Railway's infrastructure
self.pool = await asyncpg.create_pool(
    settings.database_url,
    min_size=2,          # Minimum connections
    max_size=10,         # Maximum connections
    max_queries=50000,   # Queries per connection
    max_inactive_connection_lifetime=300,  # 5 minutes
    command_timeout=60,  # 60 seconds
    server_settings={
        'jit': 'off'    # Disable JIT for stability
    }
)
```

### Proper PORT Binding

```python
# app/main.py
import os
import uvicorn

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",  # Must bind to all interfaces
        port=port,        # Use Railway's PORT
        log_level="info"
    )
```

---

## 6. MONITORING & LOGS

### Accessing Logs

**Via CLI:**
```bash
# Stream logs
railway logs

# Last 100 lines
railway logs --tail 100

# Filter by text
railway logs | grep ERROR

# Save to file
railway logs > deployment.log
```

**Via Dashboard:**
1. Navigate to service
2. Click "View Logs"
3. Use filters for:
   - Build logs
   - Deploy logs
   - Runtime logs

### Metrics Available

Railway Dashboard provides:
- **CPU Usage** - Percentage and cores
- **Memory Usage** - MB/GB used
- **Network** - Inbound/outbound traffic
- **Disk** - Storage usage
- **Response Time** - Average latency

### Setting Up Alerts

**Using Railway Webhooks:**
1. Go to Project Settings > Webhooks
2. Add webhook URL (Slack, Discord, or custom)
3. Select events:
   - `DEPLOYMENT_SUCCESS`
   - `DEPLOYMENT_FAILED`
   - `DEPLOYMENT_CRASHED`
   - `DEPLOYMENT_REMOVED`

**Webhook Payload Example:**
```json
{
  "type": "DEPLOYMENT_FAILED",
  "timestamp": "2024-01-01T00:00:00Z",
  "project": {
    "id": "xxx",
    "name": "telegram-bot"
  },
  "environment": {
    "id": "xxx",
    "name": "production"
  },
  "deployment": {
    "id": "xxx",
    "status": "FAILED",
    "error": "Health check timeout"
  }
}
```

### Debugging Deployment Failures

**Common Issues and Solutions:**

1. **Port Binding Error**
```python
# Wrong:
uvicorn.run(host="127.0.0.1", port=8000)

# Correct:
uvicorn.run(host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
```

2. **Module Import Error**
```bash
# Add to railway.toml:
[build]
buildCommand = "pip install -e ."
```

3. **Database Connection Timeout**
```python
# Use Railway's private networking for databases
DATABASE_URL = "postgresql://...@postgres.railway.internal:5432/railway"
```

4. **Memory Limit Exceeded**
```toml
# Limit workers
[deploy]
startCommand = "uvicorn app.main:app --workers 1"
```

---

## 7. PRODUCTION CHECKLIST

### Pre-Deployment Verification

```bash
# 1. Test locally with Railway variables
railway run python -m app.main

# 2. Verify all environment variables
railway variables

# 3. Check database migrations
railway run python -m app.migrations.run

# 4. Test health endpoint
curl http://localhost:8000/health
```

### First Deployment Sequence

```bash
# 1. Login and link project
railway login
railway link

# 2. Set environment variables
railway variables set BOT_TOKEN=xxx
railway variables set DATABASE_URL=xxx
railway variables set PUBLIC_BASE_URL=xxx

# 3. Deploy
railway up

# 4. Monitor logs
railway logs --tail

# 5. Verify webhook
curl https://$RAILWAY_PUBLIC_DOMAIN/health
```

### Post-Deployment Checks

```python
# verification_script.py
import asyncio
import aiohttp

async def verify_deployment():
    domain = os.getenv("RAILWAY_PUBLIC_DOMAIN")
    
    # 1. Check health endpoint
    async with aiohttp.ClientSession() as session:
        async with session.get(f"https://{domain}/health") as resp:
            assert resp.status == 200
            data = await resp.json()
            assert data["status"] == "healthy"
    
    # 2. Check webhook registration
    from app.bot import bot
    webhook = await bot.get_webhook_info()
    assert webhook.url == f"https://{domain}/webhook"
    
    # 3. Check database
    from app.db import db
    await db.connect()
    result = await db.fetchval("SELECT COUNT(*) FROM users")
    print(f"Users in database: {result}")
    
    print("✅ All checks passed!")

asyncio.run(verify_deployment())
```

### Common Railway Gotchas for Python Apps

1. **Missing PORT Binding**
   - Always use `$PORT` environment variable
   - Bind to `0.0.0.0`, not `localhost`

2. **Procfile Ignored**
   - Railway prioritizes railway.toml/json over Procfile
   - Use one configuration method consistently

3. **Build Cache Issues**
   - Add version comments to requirements.txt to force rebuild
   - Use `railway up --no-cache` for clean build

4. **Async Event Loop**
   - Don't create multiple event loops
   - Use `asyncio.run()` for main entry point

5. **Webhook HTTPS Only**
   - Railway always provides HTTPS domains
   - Never use HTTP in webhook URLs

6. **Environment Detection**
   ```python
   # Detect Railway environment
   IS_RAILWAY = bool(os.getenv("RAILWAY_ENVIRONMENT"))
   ```

7. **Private Networking**
   - Use `*.railway.internal` for service-to-service
   - Reduces latency and costs

8. **Resource Limits**
   - Default: 512MB RAM, 0.5 vCPU
   - Upgrade in dashboard for production

### Emergency Procedures

```bash
# Service crashed - quick restart
railway restart

# Bad deployment - immediate rollback
railway logs  # Find last good deployment ID
railway rollback <deployment-id>

# Database issues - connect directly
railway run python
>>> from app.db import db
>>> await db.connect()
>>> await db.execute("SELECT pg_stat_activity")

# Webhook broken - re-register
railway run python -c "
from app.bot import bot
import asyncio
asyncio.run(bot.delete_webhook())
asyncio.run(bot.set_webhook('https://NEW_URL/webhook'))
"
```

### Production Configuration Template

```toml
# railway.toml - Production Ready
[build]
builder = "NIXPACKS"
nixpacksPlan = {
  providers = ["python"],
  phases = {
    setup = {
      nixPkgs = ["python311", "postgresql", "curl"]
    },
    install = {
      cmds = ["pip install --upgrade pip", "pip install -r requirements.txt"]
    }
  }
}

[deploy]
startCommand = "python -m app.main"
healthcheckPath = "/health"
healthcheckTimeout = 300
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 3
region = "us-west1"  # Choose closest to users

[variables]
PYTHONUNBUFFERED = "1"
PYTHONDONTWRITEBYTECODE = "1"
LOG_LEVEL = "INFO"
```

---

## Quick Reference Card

```bash
# Essential Railway CLI Commands
railway login          # Authenticate
railway link          # Connect to project
railway up            # Deploy
railway logs          # View logs
railway variables     # List env vars
railway restart       # Restart service
railway rollback <id> # Revert deployment

# Debugging
railway run python    # Python REPL with env
railway run bash      # Shell with env
railway logs --tail   # Stream logs

# URLs Your Bot Will Have
https://<project>-<environment>.up.railway.app  # Public URL
<service>.railway.internal:$PORT                # Private URL
```

## Next Steps

1. Create `railway.toml` in project root
2. Set all environment variables in Railway dashboard
3. Run `railway up` for first deployment
4. Monitor logs with `railway logs --tail`
5. Verify webhook with health check
6. Set up monitoring webhooks

---

*Last Updated: Based on Railway Documentation (2024)*
*Specific to: Msvcp60dllgoldbot Telegram Stars Subscription Bot*