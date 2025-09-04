# 🔧 Railway Deployment Troubleshooting Guide

## Overview

This guide documents common failure patterns encountered during Railway deployment and their solutions. Each pattern includes symptoms, root causes, diagnostic commands, and resolution steps.

---

## 🚨 Common Failure Patterns

### Pattern 1: "No deployments found" Error

#### Symptoms:
- Running `railway logs` returns "No deployments found"
- Deployment appears to be running but logs are inaccessible
- CLI commands don't recognize the deployment

#### Root Cause:
Railway CLI has a delay in recognizing new deployments, especially immediately after `railway up`

#### Diagnostic Commands:
```bash
# Check if deployment exists
railway status --json | python3 -c "
import json, sys
d = json.load(sys.stdin)
for s in d.get('services',{}).get('edges',[]):
    print(f\"Service: {s['node']['name']}\")
    for si in s['node']['serviceInstances']['edges']:
        ld = si['node'].get('latestDeployment')
        if ld: print(f\"  Deployment ID: {ld.get('id')}, Status: {ld.get('status')}\")
"

# Alternative: Check with service name
railway logs --service TGbot

# Try with explicit deployment ID if known
railway logs <deployment-id> --service TGbot
```

#### Solution:
1. Wait for deployment to reach SUCCESS status before attempting logs
2. Use monitoring script to track deployment progress
3. Access build logs via the URL provided by `railway up`

---

### Pattern 2: Health Check Failures

#### Symptoms:
- Deployment status shows FAILED after DEPLOYING stage
- Application crashes immediately after starting
- Railway repeatedly restarts the service

#### Root Cause:
Application doesn't respond to health checks or crashes before health endpoint is ready

#### Diagnostic Commands:
```bash
# Check health check configuration
grep healthcheck railway.toml

# Verify PORT environment variable
railway variables | grep PORT

# Test health endpoint locally
python start_bot.py &
sleep 5
curl http://localhost:8080/health
kill %1
```

#### Solution:
1. Implement separate health check server that starts before main application:
```python
# start_bot.py
async def start_health_server():
    app = web.Application()
    app.router.add_get('/health', health_handler)
    port = int(os.getenv('PORT', 8080))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    return runner

# Start health server FIRST
health_runner = await start_health_server()
# Then try to start main application
```

2. Ensure health endpoint returns quickly (< 300ms)
3. Keep health server running even if main app fails

---

### Pattern 3: Build Failures

#### Symptoms:
- Deployment fails during BUILDING stage
- Error messages about missing modules or invalid packages
- Build logs show pip installation errors

#### Root Cause:
Invalid packages in requirements.txt or incompatible Python version

#### Diagnostic Commands:
```bash
# Validate requirements.txt locally
pip install -r requirements.txt --dry-run

# Check for built-in packages that shouldn't be in requirements
grep -E "asyncio|typing|dataclasses" requirements.txt

# Verify Python version compatibility
python --version
```

#### Common Issues & Fixes:
1. **asyncio in requirements.txt**
   - Remove it - asyncio is built into Python 3.4+
   
2. **Version conflicts**
   - Use compatible version ranges: `package>=1.0.0,<2.0.0`
   
3. **Missing system dependencies**
   - Add nixpacks.toml if needed:
   ```toml
   [phases.setup]
   nixPkgs = ["...", "python311", "gcc"]
   ```

---

### Pattern 4: Port Binding Issues

#### Symptoms:
- Application starts but Railway can't connect
- Health checks timeout
- Logs show "Address already in use" or binding errors

#### Root Cause:
Not using Railway's PORT environment variable or binding to wrong interface

#### Diagnostic Commands:
```bash
# Check PORT variable
railway variables | grep PORT

# Verify port in code
grep -n "PORT\|8080\|3000" *.py

# Check railway.toml configuration
grep -A5 healthcheck railway.toml
```

#### Solution:
Always read PORT from environment and bind to 0.0.0.0:
```python
port = int(os.getenv('PORT', 8080))  # Railway sets PORT
# Bind to 0.0.0.0, not localhost or 127.0.0.1
site = web.TCPSite(runner, '0.0.0.0', port)
```

---

### Pattern 5: Environment Variable Issues

#### Symptoms:
- Application crashes with "KeyError" or "NoneType" errors
- Database connection failures
- API authentication failures

#### Root Cause:
Missing or incorrectly set environment variables

#### Diagnostic Commands:
```bash
# List all variables
railway variables

# Check specific variable
railway variables | grep BOT_TOKEN

# Validate variable format (no quotes needed in Railway)
railway variables | grep SUPABASE_URL
```

#### Environment Variable Validation Script:
```bash
#!/bin/bash
# validate_env.sh

REQUIRED_VARS=(
    "BOT_TOKEN"
    "GROUP_ID"
    "ADMIN_USER_ID"
    "SUPABASE_URL"
    "SUPABASE_SERVICE_KEY"
    "PORT"
)

echo "Checking required environment variables..."
MISSING=0

for var in "${REQUIRED_VARS[@]}"; do
    if railway variables | grep -q "$var"; then
        echo "✅ $var is set"
    else
        echo "❌ $var is missing"
        MISSING=$((MISSING + 1))
    fi
done

if [ $MISSING -eq 0 ]; then
    echo "✅ All required variables are set"
else
    echo "❌ $MISSING variables are missing"
    exit 1
fi
```

---

### Pattern 6: Deployment Stuck in DEPLOYING

#### Symptoms:
- Status remains "DEPLOYING" for > 5 minutes
- No error messages in logs
- Health checks might be passing

#### Root Cause:
Application is running but Railway can't verify deployment success

#### Diagnostic Commands:
```bash
# Check deployment status details
railway status --json | jq '.services.edges[0].node.serviceInstances.edges[0].node.latestDeployment'

# Force check logs (might timeout)
timeout 30 railway logs --service TGbot || echo "Logs unavailable"

# Check build URL directly
echo "Check: https://railway.com/project/{project-id}/service/{service-id}"
```

#### Solution:
1. Ensure startCommand in railway.toml doesn't exit immediately
2. Application should run continuously (infinite loop or server)
3. Health check must return 200 status code

---

## 🔍 Debugging Commands Reference

### Basic Status Checks
```bash
# Current deployment status
railway status

# Detailed JSON status
railway status --json | python3 -m json.tool

# Service list
railway list

# Environment check
railway whoami
```

### Advanced Diagnostics
```bash
# Monitor deployment in real-time
while true; do
    STATUS=$(railway status --json | jq -r '.services.edges[0].node.serviceInstances.edges[0].node.latestDeployment.status')
    echo "$(date +%H:%M:%S) - Status: $STATUS"
    [ "$STATUS" = "SUCCESS" ] && break
    [ "$STATUS" = "FAILED" ] && exit 1
    sleep 5
done

# Get deployment ID
railway status --json | jq -r '.services.edges[0].node.serviceInstances.edges[0].node.latestDeployment.id'

# Check specific service
railway status --json | jq '.services.edges[] | select(.node.name=="TGbot")'
```

### Log Access Strategies
```bash
# Try different log access methods
railway logs --service TGbot || \
railway logs --deployment || \
railway logs --build || \
echo "Logs not available via CLI"

# Alternative: Use the build URL from deployment
BURL=$(cat deployment.log | grep "Build Logs:" | awk '{print $3}')
echo "Access logs at: $BURL"
```

---

## ✅ Service Health Check Verification

### Local Testing
```bash
# Test the health endpoint locally
python3 << 'EOF'
import asyncio
from aiohttp import web

async def health(request):
    return web.json_response({"status": "healthy"})

app = web.Application()
app.router.add_get('/health', health)

async def test():
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()
    print("Health server running on :8080/health")
    await asyncio.sleep(60)

asyncio.run(test())
EOF
```

### Production Verification
```bash
# After deployment with domain
curl -i https://your-app.up.railway.app/health

# Expected response:
# HTTP/1.1 200 OK
# Content-Type: application/json
# {"status": "healthy", "service": "telegram-bot"}
```

---

## 🚀 Quick Recovery Procedures

### If Deployment Fails
```bash
# 1. Check status
railway status --json | jq '.services.edges[0].node.serviceInstances.edges[0].node.latestDeployment.status'

# 2. Review environment variables
railway variables

# 3. Fix identified issues

# 4. Redeploy
railway up --service TGbot

# 5. Monitor
./monitor_deployment.sh
```

### If Logs Not Available
```bash
# Use the build URL from railway up output
# Format: https://railway.com/project/{id}/service/{id}?id={deployment_id}

# Or wait and retry
sleep 60 && railway logs --service TGbot
```

### Emergency Rollback
```bash
# From Railway Dashboard:
# 1. Go to Deployments tab
# 2. Find last working deployment
# 3. Click "Redeploy" on that version
```

---

## 📋 Pre-Deployment Checklist

Before deploying, verify:

- [ ] `requirements.txt` has no built-in packages (asyncio, typing)
- [ ] `railway.toml` exists with correct configuration
- [ ] `start_bot.py` production wrapper is present
- [ ] All environment variables are set in Railway
- [ ] Health endpoint implemented at `/health`
- [ ] Application uses PORT from environment
- [ ] Python optimization flags set (PYTHONUNBUFFERED=1)
- [ ] No hardcoded credentials in code

---

## 🎯 Golden Rules

1. **Always use the production wrapper** - Don't start main.py directly
2. **Health checks are critical** - Must respond within timeout period
3. **Monitor with JSON status** - More reliable than logs command
4. **Wait for SUCCESS** - Don't check logs until deployment succeeds
5. **Use 0.0.0.0 binding** - Not localhost or 127.0.0.1
6. **Check build URL** - When CLI logs fail, use the web interface

---

*This troubleshooting guide is based on actual deployment experiences and solutions that worked in production.*