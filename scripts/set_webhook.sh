#!/usr/bin/env bash
set -euo pipefail

echo "========================================="
echo "AUTOPILOT: Setting Telegram Webhook"
echo "========================================="

# Load environment variables
if [[ -f .env ]]; then
  set -o allexport
  source <(grep -v '^#' .env | sed 's/#.*//g' | sed 's/[[:space:]]*$//')
  set +o allexport
fi

# Required variables
BOT_TOKEN="${BOT_TOKEN:-}"
WEBHOOK_HOST="${WEBHOOK_HOST:-${PUBLIC_BASE_URL:-}}"
WEBHOOK_SECRET="${WEBHOOK_SECRET:-}"
TELEGRAM_SECRET_TOKEN="${TELEGRAM_SECRET_TOKEN:-${WEBHOOK_SECRET:-}}"

# Validate requirements
if [[ -z "$BOT_TOKEN" ]]; then
  echo "❌ BOT_TOKEN not set"
  exit 1
fi

if [[ -z "$WEBHOOK_HOST" ]]; then
  echo "❌ WEBHOOK_HOST or PUBLIC_BASE_URL not set"
  exit 1
fi

if [[ -z "$WEBHOOK_SECRET" ]]; then
  echo "❌ WEBHOOK_SECRET not set"
  exit 1
fi

# Ensure WEBHOOK_HOST has https://
if [[ ! "$WEBHOOK_HOST" =~ ^https?:// ]]; then
  WEBHOOK_HOST="https://$WEBHOOK_HOST"
fi

# Construct webhook URL
WEBHOOK_URL="${WEBHOOK_HOST}/webhook/${WEBHOOK_SECRET}"

echo "📍 Webhook URL: $WEBHOOK_URL"
echo "🔐 Secret Token: ${TELEGRAM_SECRET_TOKEN:0:8}..."

# Delete existing webhook first
echo ""
echo "Deleting existing webhook..."
curl -s "https://api.telegram.org/bot$BOT_TOKEN/deleteWebhook" | python3 -c "
import json, sys
data = json.load(sys.stdin)
if data.get('ok'):
    print('✅ Webhook deleted')
else:
    print(f'⚠️  Delete failed: {data.get(\"description\", \"Unknown error\")}')
" || echo "⚠️  Failed to parse response"

# Set new webhook
echo ""
echo "Setting new webhook..."
curl -s "https://api.telegram.org/bot$BOT_TOKEN/setWebhook" \
  -F "url=$WEBHOOK_URL" \
  -F "secret_token=$TELEGRAM_SECRET_TOKEN" \
  -F "allowed_updates=[\"message\",\"callback_query\",\"chat_join_request\",\"chat_member\",\"pre_checkout_query\",\"successful_payment\"]" \
  -F "drop_pending_updates=false" | python3 -c "
import json, sys
data = json.load(sys.stdin)
if data.get('ok'):
    print('✅ Webhook set successfully')
else:
    print(f'❌ Failed: {data.get(\"description\", \"Unknown error\")}')
    sys.exit(1)
" || exit 1

# Verify webhook
echo ""
echo "Verifying webhook..."
curl -s "https://api.telegram.org/bot$BOT_TOKEN/getWebhookInfo" | python3 -c "
import json, sys
from datetime import datetime

data = json.load(sys.stdin)
if data.get('ok'):
    result = data['result']
    print('📊 Webhook Status:')
    print(f'  URL: {result.get(\"url\", \"Not set\")}')
    print(f'  Has secret: {\"Yes\" if result.get(\"has_custom_certificate\") == False and result.get(\"url\") else \"No\"}')
    print(f'  Pending updates: {result.get(\"pending_update_count\", 0)}')
    print(f'  Max connections: {result.get(\"max_connections\", 40)}')
    
    if result.get('last_error_date'):
        error_time = datetime.fromtimestamp(result['last_error_date'])
        print(f'  ⚠️  Last error: {result.get(\"last_error_message\", \"Unknown\")}')
        print(f'      at {error_time.strftime(\"%Y-%m-%d %H:%M:%S\")}')
    
    if result.get('ip_address'):
        print(f'  IP Address: {result[\"ip_address\"]}')
    
    # Verify it matches our URL
    expected_url = '$WEBHOOK_URL'
    if result.get('url') == expected_url:
        print('')
        print('✅ Webhook configured correctly!')
    else:
        print('')
        print(f'⚠️  URL mismatch!')
        print(f'  Expected: {expected_url}')
        print(f'  Got: {result.get(\"url\", \"None\")}')
else:
    print(f'❌ Failed to get webhook info: {data.get(\"description\", \"Unknown\")}')
    sys.exit(1)
" || exit 1

echo ""
echo "========================================="
echo "✅ Webhook setup complete!"
echo "========================================="