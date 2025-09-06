#!/bin/bash

# Simple deployment test for Telegram Stars subscription bot
# Run this after deploying to Railway to verify everything works

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "========================================="
echo "  Telegram Bot Deployment Test"
echo "========================================="

# Get deployment URL from environment or argument
if [ -z "$1" ]; then
    echo -e "${YELLOW}Usage: ./test_deployment.sh https://your-app.up.railway.app${NC}"
    echo "Please provide your Railway deployment URL"
    exit 1
fi

DEPLOY_URL=$1
echo "Testing deployment at: $DEPLOY_URL"
echo ""

# Test 1: Health check
echo -n "1. Testing health endpoint... "
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$DEPLOY_URL/health")
if [ "$HTTP_STATUS" = "200" ]; then
    echo -e "${GREEN}✓ PASS${NC} (HTTP $HTTP_STATUS)"
else
    echo -e "${RED}✗ FAIL${NC} (HTTP $HTTP_STATUS)"
    echo "   Health check failed. Check your deployment logs."
    exit 1
fi

# Test 2: Liveness check
echo -n "2. Testing liveness probe... "
LIVENESS=$(curl -s "$DEPLOY_URL/health/live")
if echo "$LIVENESS" | grep -q "alive"; then
    echo -e "${GREEN}✓ PASS${NC}"
else
    echo -e "${RED}✗ FAIL${NC}"
    echo "   Response: $LIVENESS"
fi

# Test 3: Readiness check (may fail if DB not connected)
echo -n "3. Testing readiness probe... "
READY_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$DEPLOY_URL/health/ready")
READY_RESPONSE=$(curl -s "$DEPLOY_URL/health/ready")
if [ "$READY_STATUS" = "200" ]; then
    echo -e "${GREEN}✓ PASS${NC} - All systems ready"
elif [ "$READY_STATUS" = "503" ]; then
    echo -e "${YELLOW}⚠ WARNING${NC} - Not ready"
    echo "   Response: $READY_RESPONSE"
    echo "   Check database connection and bot token"
else
    echo -e "${RED}✗ FAIL${NC} (HTTP $READY_STATUS)"
fi

# Test 4: Detailed health
echo -n "4. Testing detailed health... "
DETAILED=$(curl -s "$DEPLOY_URL/health/detailed")
if echo "$DETAILED" | grep -q "components"; then
    echo -e "${GREEN}✓ PASS${NC}"
    
    # Parse component status
    echo ""
    echo "   Component Status:"
    
    # Check database
    if echo "$DETAILED" | grep -q '"name":"database".*"status":"healthy"'; then
        echo -e "   • Database: ${GREEN}✓ Healthy${NC}"
    elif echo "$DETAILED" | grep -q '"name":"database".*"status":"degraded"'; then
        echo -e "   • Database: ${YELLOW}⚠ Degraded${NC}"
    else
        echo -e "   • Database: ${RED}✗ Unhealthy${NC}"
    fi
    
    # Check bot
    if echo "$DETAILED" | grep -q '"name":"telegram_bot".*"status":"healthy"'; then
        echo -e "   • Telegram Bot: ${GREEN}✓ Healthy${NC}"
    elif echo "$DETAILED" | grep -q '"name":"telegram_bot".*"status":"degraded"'; then
        echo -e "   • Telegram Bot: ${YELLOW}⚠ Degraded${NC}"
    else
        echo -e "   • Telegram Bot: ${RED}✗ Unhealthy${NC}"
    fi
else
    echo -e "${RED}✗ FAIL${NC}"
fi

# Test 5: Webhook endpoint (should return 401 without proper secret)
echo -n "5. Testing webhook security... "
WEBHOOK_STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$DEPLOY_URL/webhook/test")
if [ "$WEBHOOK_STATUS" = "401" ] || [ "$WEBHOOK_STATUS" = "404" ]; then
    echo -e "${GREEN}✓ PASS${NC} - Webhook protected (HTTP $WEBHOOK_STATUS)"
else
    echo -e "${YELLOW}⚠ WARNING${NC} - Unexpected status (HTTP $WEBHOOK_STATUS)"
fi

# Test 6: Bot command test (if BOT_TOKEN provided)
if [ ! -z "$BOT_TOKEN" ] && [ ! -z "$BOT_USERNAME" ]; then
    echo ""
    echo "6. Testing bot commands..."
    
    # Test /start command
    echo -n "   Testing /start command... "
    START_RESPONSE=$(curl -s "https://api.telegram.org/bot$BOT_TOKEN/getUpdates?limit=1")
    if echo "$START_RESPONSE" | grep -q "ok\":true"; then
        echo -e "${GREEN}✓ Bot API accessible${NC}"
    else
        echo -e "${RED}✗ Bot API error${NC}"
    fi
else
    echo ""
    echo "6. Bot command test skipped (set BOT_TOKEN and BOT_USERNAME to test)"
fi

echo ""
echo "========================================="
echo "  Test Summary"
echo "========================================="

# Final summary
if [ "$READY_STATUS" = "200" ]; then
    echo -e "${GREEN}✅ Deployment looks healthy!${NC}"
    echo ""
    echo "Next steps:"
    echo "1. Send /start to your bot to test it responds"
    echo "2. Check Railway logs for '🚀 Bot started successfully'"
    echo "3. Verify webhook is receiving updates in logs"
    echo "4. Test payment flow with /status command"
elif [ "$HTTP_STATUS" = "200" ]; then
    echo -e "${YELLOW}⚠️  Deployment is running but not fully ready${NC}"
    echo ""
    echo "Check:"
    echo "1. Database connection string is correct"
    echo "2. BOT_TOKEN is valid"
    echo "3. All required environment variables are set"
    echo "4. Check Railway logs for errors"
else
    echo -e "${RED}❌ Deployment failed health checks${NC}"
    echo ""
    echo "Debug steps:"
    echo "1. Check Railway deployment logs"
    echo "2. Verify environment variables are set"
    echo "3. Ensure database is accessible"
fi

echo ""
echo "Deployment URL: $DEPLOY_URL"
echo "Dashboard: $DEPLOY_URL/admin/dashboard (requires auth token)"
echo ""