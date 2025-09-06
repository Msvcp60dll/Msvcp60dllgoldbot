#!/bin/bash

# Quick deployment test for Telegram Stars Bot on Railway
# Run after deployment to verify everything works

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo "================================"
echo "  Quick Deployment Test"
echo "  30 Stars Testing Mode"
echo "================================"

# Check if Railway CLI is installed
if ! command -v railway &> /dev/null; then
    echo -e "${RED}Railway CLI not found. Install it first:${NC}"
    echo "npm install -g @railway/cli"
    exit 1
fi

# Check environment variables
echo -e "\n${YELLOW}Checking Railway variables...${NC}"

REQUIRED_VARS=(
    "BOT_TOKEN"
    "DATABASE_URL"
    "GROUP_ID"
    "WEBHOOK_SECRET"
)

for var in "${REQUIRED_VARS[@]}"; do
    if railway variables get "$var" &> /dev/null; then
        echo -e "✅ $var is set"
    else
        echo -e "${RED}❌ $var is NOT set${NC}"
        exit 1
    fi
done

# Check optional but recommended
OPTIONAL_VARS=(
    "WEBHOOK_URL"
    "BOT_OWNER_ID"
    "PLAN_STARS"
    "SUB_STARS"
)

echo -e "\n${YELLOW}Checking optional variables...${NC}"
for var in "${OPTIONAL_VARS[@]}"; do
    if railway variables get "$var" &> /dev/null; then
        VALUE=$(railway variables get "$var" 2>/dev/null || echo "set")
        if [ "$var" == "PLAN_STARS" ] || [ "$var" == "SUB_STARS" ]; then
            echo -e "✅ $var = $VALUE stars"
        else
            echo -e "✅ $var is set"
        fi
    else
        echo -e "⚠️  $var is not set (optional)"
    fi
done

# Get the app URL
echo -e "\n${YELLOW}Getting deployment URL...${NC}"
APP_URL=$(railway status --json 2>/dev/null | grep -o '"url":"[^"]*' | cut -d'"' -f4 || echo "")

if [ -z "$APP_URL" ]; then
    echo -e "${YELLOW}Could not auto-detect URL. Enter your Railway app URL:${NC}"
    read -p "https://" APP_INPUT
    APP_URL="https://$APP_INPUT"
fi

echo "App URL: $APP_URL"

# Test health endpoint
echo -e "\n${YELLOW}Testing health endpoints...${NC}"

echo -n "1. Basic health check... "
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$APP_URL/health" || echo "000")
if [ "$HTTP_STATUS" = "200" ]; then
    echo -e "${GREEN}✅ PASS${NC}"
else
    echo -e "${RED}❌ FAIL (HTTP $HTTP_STATUS)${NC}"
    echo "   Check Railway logs for startup errors"
    exit 1
fi

echo -n "2. Readiness check... "
READY=$(curl -s "$APP_URL/health/ready" || echo "{}")
if echo "$READY" | grep -q '"status":"ready"'; then
    echo -e "${GREEN}✅ Ready${NC}"
elif echo "$READY" | grep -q '"status":"not_ready"'; then
    echo -e "${YELLOW}⚠️ Not ready - check database/bot connection${NC}"
    echo "   Response: $READY"
else
    echo -e "${RED}❌ Failed${NC}"
fi

echo -n "3. Detailed health... "
DETAILED=$(curl -s "$APP_URL/health/detailed" || echo "{}")
if echo "$DETAILED" | grep -q '"status"'; then
    echo -e "${GREEN}✅ Available${NC}"
    
    # Parse component status
    if echo "$DETAILED" | grep -q '"database".*"healthy"'; then
        echo "   • Database: ✅ Healthy"
    else
        echo "   • Database: ❌ Not healthy"
    fi
    
    if echo "$DETAILED" | grep -q '"telegram_bot".*"healthy"'; then
        echo "   • Bot: ✅ Healthy"
    else
        echo "   • Bot: ❌ Not healthy"
    fi
else
    echo -e "${RED}❌ Failed${NC}"
fi

# Check logs for success message
echo -e "\n${YELLOW}Checking deployment logs...${NC}"
echo "Looking for startup confirmation..."

# Get recent logs
LOGS=$(railway logs --lines 50 2>/dev/null || echo "")

if echo "$LOGS" | grep -q "🚀 Bot started successfully"; then
    echo -e "${GREEN}✅ Bot started successfully${NC}"
elif echo "$LOGS" | grep -q "Bot started successfully"; then
    echo -e "${GREEN}✅ Bot started${NC}"
else
    echo -e "${YELLOW}⚠️ Could not confirm startup in logs${NC}"
fi

if echo "$LOGS" | grep -q "Webhook configured"; then
    echo -e "${GREEN}✅ Webhook configured${NC}"
else
    echo -e "${YELLOW}⚠️ Webhook status unknown${NC}"
fi

# Summary
echo -e "\n================================"
echo -e "  ${GREEN}Deployment Test Complete${NC}"
echo "================================"

echo -e "\n${GREEN}Next Steps:${NC}"
echo "1. Add test user to whitelist in Supabase:"
echo "   INSERT INTO whitelist (user_id, source) VALUES (YOUR_ID, 'test');"
echo ""
echo "2. Test whitelist flow:"
echo "   - Join group → Should auto-approve"
echo ""
echo "3. Test payment flow (30 Stars):"
echo "   - Remove from whitelist"
echo "   - Join group → Get payment DM"
echo "   - Pay 30 Stars → Get access"
echo ""
echo "4. Monitor at: $APP_URL/admin/dashboard"
echo ""
echo -e "${YELLOW}Remember: Using 30 Stars for testing${NC}"
echo "Update to production values (3800/2500) when ready"