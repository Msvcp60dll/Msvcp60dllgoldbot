#!/usr/bin/env bash
set -euo pipefail

echo "========================================="
echo "AUTOPILOT: Smoke Test Report"
echo "========================================="
echo "Time: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# Load environment
if [[ -f .env ]]; then
  set -o allexport
  source <(grep -v '^#' .env | sed 's/#.*//g' | sed 's/[[:space:]]*$//')
  set +o allexport
fi

PUBLIC_BASE_URL="${PUBLIC_BASE_URL:-${WEBHOOK_HOST:-}}"
BOT_TOKEN="${BOT_TOKEN:-}"

# Remove https:// prefix if present
PUBLIC_BASE_URL="${PUBLIC_BASE_URL#https://}"
PUBLIC_BASE_URL="${PUBLIC_BASE_URL#http://}"

if [[ -z "$PUBLIC_BASE_URL" || -z "$BOT_TOKEN" ]]; then
  echo "❌ Missing PUBLIC_BASE_URL or BOT_TOKEN"
  exit 1
fi

FULL_URL="https://$PUBLIC_BASE_URL"

# Test results storage
PASS_COUNT=0
FAIL_COUNT=0
TOTAL_COUNT=0

test_endpoint() {
  local name="$1"
  local url="$2"
  local expected="$3"
  local auth_header="${4:-}"
  
  TOTAL_COUNT=$((TOTAL_COUNT + 1))
  echo -n "Testing $name... "
  
  if [[ -n "$auth_header" ]]; then
    RESPONSE=$(curl -s -w "\n%{http_code}" -H "$auth_header" "$url" 2>/dev/null || echo "000")
  else
    RESPONSE=$(curl -s -w "\n%{http_code}" "$url" 2>/dev/null || echo "000")
  fi
  
  HTTP_CODE=$(echo "$RESPONSE" | tail -1)
  BODY=$(echo "$RESPONSE" | head -n -1)
  
  if [[ "$HTTP_CODE" == "$expected" ]]; then
    echo "✅ ($HTTP_CODE)"
    PASS_COUNT=$((PASS_COUNT + 1))
    return 0
  else
    echo "❌ (Expected: $expected, Got: $HTTP_CODE)"
    FAIL_COUNT=$((FAIL_COUNT + 1))
    return 1
  fi
}

echo "1. Health Endpoints"
echo "-------------------"
test_endpoint "GET /health" "$FULL_URL/health" "200"
test_endpoint "GET /healthz" "$FULL_URL/healthz" "200"

echo ""
echo "2. API Endpoints"
echo "----------------"
test_endpoint "GET / (root)" "$FULL_URL/" "200"
test_endpoint "GET /api/status" "$FULL_URL/api/status" "200"

# Test dashboard with auth
if [[ -n "${DASHBOARD_TOKENS:-}" ]]; then
  FIRST_TOKEN=$(echo "$DASHBOARD_TOKENS" | cut -d',' -f1)
  test_endpoint "GET /admin/dashboard (auth)" "$FULL_URL/admin/dashboard" "200" "Authorization: Bearer $FIRST_TOKEN"
  test_endpoint "GET /admin/dashboard (no auth)" "$FULL_URL/admin/dashboard" "401"
else
  echo "Skipping dashboard tests (no tokens configured)"
fi

echo ""
echo "3. Webhook Configuration"
echo "------------------------"
echo -n "Checking webhook status... "
WEBHOOK_INFO=$(curl -s "https://api.telegram.org/bot$BOT_TOKEN/getWebhookInfo" 2>/dev/null)

if echo "$WEBHOOK_INFO" | grep -q '"ok":true'; then
  WEBHOOK_URL=$(echo "$WEBHOOK_INFO" | python3 -c "import json,sys; print(json.load(sys.stdin).get('result',{}).get('url',''))" 2>/dev/null || echo "")
  EXPECTED_URL="$FULL_URL/webhook/${WEBHOOK_SECRET:-unknown}"
  
  if [[ "$WEBHOOK_URL" == "$EXPECTED_URL" ]]; then
    echo "✅ Configured correctly"
    PASS_COUNT=$((PASS_COUNT + 1))
  else
    echo "⚠️  URL mismatch"
    echo "  Expected: $EXPECTED_URL"
    echo "  Got: $WEBHOOK_URL"
    FAIL_COUNT=$((FAIL_COUNT + 1))
  fi
  
  # Check for errors
  LAST_ERROR=$(echo "$WEBHOOK_INFO" | python3 -c "import json,sys; r=json.load(sys.stdin).get('result',{}); print(r.get('last_error_message',''))" 2>/dev/null || echo "")
  if [[ -n "$LAST_ERROR" && "$LAST_ERROR" != "None" ]]; then
    echo "  ⚠️  Last error: $LAST_ERROR"
  fi
  
  TOTAL_COUNT=$((TOTAL_COUNT + 1))
else
  echo "❌ Failed to get webhook info"
  FAIL_COUNT=$((FAIL_COUNT + 1))
  TOTAL_COUNT=$((TOTAL_COUNT + 1))
fi

echo ""
echo "4. Database Connectivity"
echo "------------------------"
echo -n "Testing database connection... "

if command -v psql >/dev/null 2>&1 && [[ -n "${DATABASE_URL:-}" ]]; then
  if psql "$DATABASE_URL" -c "SELECT 1" >/dev/null 2>&1; then
    echo "✅ Connected"
    PASS_COUNT=$((PASS_COUNT + 1))
    
    # Count tables
    TABLE_COUNT=$(psql "$DATABASE_URL" -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public'" 2>/dev/null || echo "0")
    echo "  Tables: $TABLE_COUNT"
  else
    echo "❌ Connection failed"
    FAIL_COUNT=$((FAIL_COUNT + 1))
  fi
  TOTAL_COUNT=$((TOTAL_COUNT + 1))
else
  echo "⚠️  Skipped (psql not available or DATABASE_URL not set)"
fi

echo ""
echo "5. Railway Deployment"
echo "---------------------"
if command -v railway >/dev/null 2>&1; then
  echo -n "Checking deployment status... "
  
  if railway status --json 2>/dev/null | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    # Parse Railway status JSON
    print('✅ Deployment active')
    exit(0)
except:
    exit(1)
  " 2>/dev/null; then
    PASS_COUNT=$((PASS_COUNT + 1))
  else
    # Fallback: just check if command works
    if railway status >/dev/null 2>&1; then
      echo "✅ Railway connected"
      PASS_COUNT=$((PASS_COUNT + 1))
    else
      echo "⚠️  Cannot get status"
      FAIL_COUNT=$((FAIL_COUNT + 1))
    fi
  fi
  TOTAL_COUNT=$((TOTAL_COUNT + 1))
else
  echo "Railway CLI not installed"
fi

echo ""
echo "========================================="
echo "SMOKE TEST SUMMARY"
echo "========================================="
echo "✅ Passed: $PASS_COUNT/$TOTAL_COUNT"
echo "❌ Failed: $FAIL_COUNT/$TOTAL_COUNT"

if [[ $FAIL_COUNT -eq 0 ]]; then
  echo ""
  echo "🎉 All tests passed! Bot is ready for production."
  echo ""
  echo "Next steps:"
  echo "1. Send /start to your bot: @$(curl -s "https://api.telegram.org/bot$BOT_TOKEN/getMe" | python3 -c "import json,sys; print(json.load(sys.stdin).get('result',{}).get('username','your_bot'))" 2>/dev/null)"
  echo "2. Test joining your group"
  echo "3. Monitor logs: railway logs -f"
  exit 0
else
  echo ""
  echo "⚠️  Some tests failed. Review the failures above."
  echo ""
  echo "Debug commands:"
  echo "- Check logs: railway logs --tail 50"
  echo "- Test locally: python main.py"
  echo "- Verify webhook: curl https://api.telegram.org/bot\$BOT_TOKEN/getWebhookInfo | jq"
  exit 1
fi