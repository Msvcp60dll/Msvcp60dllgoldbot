#!/bin/bash

# Check Railway deployment status and health

echo "======================================"
echo "Checking Railway Deployment"
echo "======================================"

# Check if railway CLI is installed
if ! command -v railway &> /dev/null; then
    echo "❌ Railway CLI not found."
    echo "Please install: brew install railway"
    exit 1
fi

# Check authentication
echo "🔐 Checking authentication..."
if ! railway whoami &> /dev/null; then
    echo "❌ Not logged in to Railway"
    echo "Run: railway login"
    exit 1
fi

echo "✅ Logged in as: $(railway whoami)"

# Check project status
echo ""
echo "📊 Project Status:"
railway status

# Get deployment URL
echo ""
echo "🌐 Getting deployment URL..."
DEPLOYMENT_URL=$(railway variables get RAILWAY_PUBLIC_DOMAIN 2>/dev/null || echo "")

if [ -z "$DEPLOYMENT_URL" ]; then
    echo "⚠️  No public URL found. Deployment might not be exposed."
    echo "Check Railway dashboard to enable public networking."
else
    echo "✅ Deployment URL: https://$DEPLOYMENT_URL"
    
    # Check health endpoint
    echo ""
    echo "🏥 Checking health endpoint..."
    HEALTH_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" "https://$DEPLOYMENT_URL/healthz")
    
    if [ "$HEALTH_RESPONSE" = "200" ]; then
        echo "✅ Health check passed!"
        curl -s "https://$DEPLOYMENT_URL/healthz" | python3 -m json.tool
    else
        echo "❌ Health check failed (HTTP $HEALTH_RESPONSE)"
    fi
fi

# Show recent logs
echo ""
echo "📝 Recent logs (last 10 lines):"
railway logs --tail 10

echo ""
echo "🔧 Useful commands:"
echo "- View all logs: railway logs"
echo "- View live logs: railway logs --follow"
echo "- Open dashboard: railway open"
echo "- Restart: railway restart"
echo "- Check variables: railway variables"