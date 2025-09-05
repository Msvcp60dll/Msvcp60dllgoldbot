#!/bin/bash

echo "======================================"
echo "RAILWAY DEPLOYMENT SCRIPT"
echo "======================================"
echo ""

# Check if Railway CLI is installed
if ! command -v railway &> /dev/null; then
    echo "❌ Railway CLI not installed"
    echo "Install with: brew install railway"
    exit 1
fi

# Check if logged in
railway whoami &> /dev/null
if [ $? -ne 0 ]; then
    echo "📝 Logging into Railway..."
    railway login
fi

echo "✅ Logged into Railway"
echo ""

# Create railway.toml configuration
echo "📝 Creating railway.toml configuration..."
cat > railway.toml << 'EOF'
[build]
builder = "DOCKERFILE"
dockerfilePath = "Dockerfile"

[deploy]
startCommand = "python start_simple.py"
healthcheckPath = "/healthz"
healthcheckTimeout = 100
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 10

[[services]]
name = "web"
port = 8080
EOF

echo "✅ railway.toml created"
echo ""

# Deploy using Railway CLI
echo "🚀 Deploying to Railway..."
echo ""
echo "Since Railway CLI requires interactive mode for linking,"
echo "please follow these manual steps:"
echo ""
echo "======================================"
echo "MANUAL DEPLOYMENT STEPS:"
echo "======================================"
echo ""
echo "1. Open Railway Dashboard:"
echo "   👉 https://railway.app/dashboard"
echo ""
echo "2. In your project 'msvcp60dll-bot':"
echo "   - Click '+ New'"
echo "   - Select 'GitHub Repo'"
echo "   - Connect 'Msvcp60dll/Msvcp60dllgoldbot'"
echo "   - Select 'main' branch"
echo ""
echo "3. Go to Variables tab and add these:"
echo ""
cat << 'VARS'
BOT_TOKEN=8263837787:AAE_kJD3YYM5L_7Hd28uCkgvvjqxFylCIWQ
GROUP_CHAT_ID=-100238460973
OWNER_IDS=306145881
SUPABASE_URL=https://cudmllwhxpamaiqxohse.supabase.co
SUPABASE_SERVICE_KEY=sb_secret_SIBInD2DwQYbi25ZaWdcTw_N4hrFDqS
SUPABASE_DB_PASSWORD=Msvcp60.dll173323519
WEBHOOK_SECRET=railway_webhook_secret_2024
WEBHOOK_HOST=https://msvcp60dll-bot-production.up.railway.app
PLAN_STARS=499
SUB_STARS=449
PLAN_DAYS=30
GRACE_HOURS=48
RECONCILE_WINDOW_DAYS=3
DAYS_BEFORE_EXPIRE=3
INVITE_TTL_MIN=5
DASHBOARD_TOKENS=dashboard_token_2024,admin_token_secure
LOG_LEVEL=INFO
TIMEZONE=UTC
VARS

echo ""
echo "4. Railway will auto-deploy after saving variables!"
echo ""
echo "5. Check deployment logs:"
echo "   railway logs --tail"
echo ""
echo "======================================"
echo ""
echo "Would you like to open Railway dashboard now? (y/n)"
read -r response
if [[ "$response" == "y" ]]; then
    railway open
fi