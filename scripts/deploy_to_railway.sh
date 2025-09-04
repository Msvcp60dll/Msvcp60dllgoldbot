#!/bin/bash

# Railway Deployment Script for Msvcp60dllgoldbot
echo "=== Railway Deployment Script ==="
echo ""

# Check if Railway CLI is installed
if ! command -v railway &> /dev/null; then
    echo "Railway CLI is not installed. Install it with:"
    echo "brew install railway"
    exit 1
fi

# Check if logged in
railway whoami &> /dev/null
if [ $? -ne 0 ]; then
    echo "Not logged in to Railway. Running 'railway login'..."
    railway login
fi

echo "Current project status:"
railway status

echo ""
echo "=== Deployment Instructions ==="
echo ""
echo "1. Go to Railway Dashboard: https://railway.app/dashboard"
echo ""
echo "2. If you haven't connected the GitHub repo:"
echo "   a. Click on your project 'msvcp60dll-bot'"
echo "   b. Click '+ New' → 'GitHub Repo'"
echo "   c. Connect to 'Msvcp60dll/Msvcp60dllgoldbot'"
echo "   d. Select 'main' branch"
echo ""
echo "3. Set Environment Variables in Railway:"
echo "   Go to Variables tab and add:"
echo ""
echo "   BOT_TOKEN=8263837787:AAE_kJD3YYM5L_7Hd28uCkgvvjqxFylCIWQ"
echo "   GROUP_CHAT_ID=-100238460973"
echo "   OWNER_IDS=306145881"
echo "   SUPABASE_URL=https://cudmllwhxpamaiqxohse.supabase.co"
echo "   SUPABASE_SERVICE_KEY=sb_secret_10UN2tVL4bV5mLYVQ1z3Kg_x2s5yIr1"
echo "   WEBHOOK_SECRET=railway_webhook_secret_2024"
echo "   WEBHOOK_HOST=https://msvcp60dll-bot-production.up.railway.app"
echo "   PLAN_STARS=499"
echo "   SUB_STARS=449"
echo "   PLAN_DAYS=30"
echo "   GRACE_HOURS=48"
echo "   RECONCILE_WINDOW_DAYS=3"
echo "   DAYS_BEFORE_EXPIRE=3"
echo "   INVITE_TTL_MIN=5"
echo "   DASHBOARD_TOKENS=dashboard_token_2024,admin_token_secure"
echo "   LOG_LEVEL=INFO"
echo "   TIMEZONE=UTC"
echo ""
echo "4. Verify Deployment Settings:"
echo "   - Build Command: (leave empty, uses Dockerfile)"
echo "   - Start Command: python start_simple.py"
echo "   - Port: 8080"
echo ""
echo "5. Generate Domain:"
echo "   In Settings → Networking → Generate Domain"
echo "   Copy the generated URL and update WEBHOOK_HOST if different"
echo ""
echo "6. Deploy:"
echo "   Railway will auto-deploy when you push to GitHub"
echo "   Or click 'Deploy' button in Railway dashboard"
echo ""
echo "7. Check Logs:"
echo "   railway logs --tail"
echo ""
echo "Press Enter to open Railway dashboard..."
read

# Open Railway dashboard
railway open