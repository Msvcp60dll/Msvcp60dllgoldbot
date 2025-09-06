#!/bin/bash

# EMERGENCY: Fix webhook to include successful_payment

BOT_TOKEN=$(railway variables | grep "BOT_TOKEN" | awk -F'│' '{print $2}' | xargs)
WEBHOOK_URL=$(railway variables | grep "PUBLIC_BASE_URL\|WEBHOOK_HOST" | head -1 | awk -F'│' '{print $2}' | xargs)
WEBHOOK_SECRET=$(railway variables | grep "WEBHOOK_SECRET" | awk -F'│' '{print $2}' | xargs)

if [ -z "$BOT_TOKEN" ]; then
    echo "❌ BOT_TOKEN not found"
    exit 1
fi

if [ -z "$WEBHOOK_URL" ]; then
    WEBHOOK_URL="https://msvcp60dllgoldbot-production.up.railway.app"
fi

FULL_WEBHOOK_URL="${WEBHOOK_URL}/webhook/${WEBHOOK_SECRET}"

echo "🚨 EMERGENCY WEBHOOK FIX"
echo "========================"
echo "Bot Token: ${BOT_TOKEN:0:10}..."
echo "Webhook URL: $FULL_WEBHOOK_URL"
echo ""

# Delete existing webhook
echo "🗑️ Deleting existing webhook..."
curl -s -X POST "https://api.telegram.org/bot${BOT_TOKEN}/deleteWebhook" | jq '.'

# Set new webhook with ALL required updates
echo ""
echo "🔧 Setting new webhook with all updates..."
curl -s -X POST "https://api.telegram.org/bot${BOT_TOKEN}/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "'$FULL_WEBHOOK_URL'",
    "allowed_updates": [
      "message",
      "callback_query",
      "chat_join_request",
      "chat_member",
      "pre_checkout_query",
      "successful_payment"
    ],
    "drop_pending_updates": false,
    "secret_token": "'$WEBHOOK_SECRET'"
  }' | jq '.'

# Verify the webhook
echo ""
echo "✅ Verifying webhook configuration..."
curl -s "https://api.telegram.org/bot${BOT_TOKEN}/getWebhookInfo" | jq '.result | {url: .url, allowed_updates: .allowed_updates, pending_update_count: .pending_update_count}'

echo ""
echo "✅ WEBHOOK FIXED! The bot should now receive:"
echo "   - chat_join_request (for join requests)"
echo "   - successful_payment (for payment processing)"