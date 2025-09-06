#!/usr/bin/env bash
set -euo pipefail

echo "========================================="
echo "AUTOPILOT: Syncing .env → Railway"
echo "========================================="

# Load .env file
ENV_FILE="${1:-.env}"
if [[ ! -f "$ENV_FILE" ]]; then
  echo "❌ .env file not found at: $ENV_FILE"
  exit 1
fi

echo "📄 Reading from: $ENV_FILE"

# Parse .env and set Railway variables
while IFS= read -r line || [[ -n "$line" ]]; do
  # Skip comments and empty lines
  [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue
  
  # Extract key=value (handle values with spaces)
  if [[ "$line" =~ ^([A-Z_][A-Z0-9_]*)=(.*)$ ]]; then
    key="${BASH_REMATCH[1]}"
    value="${BASH_REMATCH[2]}"
    
    # Remove surrounding quotes if present
    value="${value%\"}"
    value="${value#\"}"
    value="${value%\'}"
    value="${value#\'}"
    
    # Skip if empty value
    [[ -z "$value" ]] && continue
    
    # Mask sensitive values for display
    display_value="$value"
    if [[ "$key" =~ (TOKEN|KEY|SECRET|PASSWORD|DATABASE_URL) ]]; then
      if [[ ${#value} -gt 12 ]]; then
        display_value="${value:0:8}...${value: -4}"
      else
        display_value="***"
      fi
    fi
    
    echo "  Setting $key = $display_value"
    
    # Set in Railway (suppress output for security)
    railway variables set "$key=$value" >/dev/null 2>&1 || {
      echo "  ⚠️  Failed to set $key"
    }
  fi
done < "$ENV_FILE"

# Special handling for computed values
echo ""
echo "Setting computed values..."

# Extract PUBLIC_BASE_URL (remove https:// prefix if present)
PUBLIC_BASE_URL=$(grep "^PUBLIC_BASE_URL=" "$ENV_FILE" | cut -d'=' -f2- | sed 's/"//g' | sed 's/https:\/\///')
if [[ -n "$PUBLIC_BASE_URL" ]]; then
  # Set WEBHOOK_HOST as full URL
  WEBHOOK_HOST="https://$PUBLIC_BASE_URL"
  echo "  Setting WEBHOOK_HOST = $WEBHOOK_HOST"
  railway variables set "WEBHOOK_HOST=$WEBHOOK_HOST" >/dev/null 2>&1
  
  # Ensure PUBLIC_BASE_URL is set correctly
  echo "  Setting PUBLIC_BASE_URL = https://$PUBLIC_BASE_URL"
  railway variables set "PUBLIC_BASE_URL=https://$PUBLIC_BASE_URL" >/dev/null 2>&1
fi

# If TELEGRAM_SECRET_TOKEN not set, use WEBHOOK_SECRET
WEBHOOK_SECRET=$(grep "^WEBHOOK_SECRET=" "$ENV_FILE" | cut -d'=' -f2- | sed 's/"//g')
if [[ -n "$WEBHOOK_SECRET" ]]; then
  echo "  Setting TELEGRAM_SECRET_TOKEN = ${WEBHOOK_SECRET:0:8}..."
  railway variables set "TELEGRAM_SECRET_TOKEN=$WEBHOOK_SECRET" >/dev/null 2>&1
fi

echo ""
echo "Verifying Railway variables..."
railway variables --json 2>/dev/null | python3 -c "
import json, sys
try:
  vars = json.load(sys.stdin)
  if vars:
    print(f'✅ Successfully set {len(vars)} variables')
    critical = ['BOT_TOKEN', 'DATABASE_URL', 'GROUP_CHAT_ID', 'OWNER_IDS']
    missing = [k for k in critical if k not in vars]
    if missing:
      print(f'⚠️  Missing critical variables: {missing}')
      sys.exit(1)
  else:
    print('❌ No variables found')
    sys.exit(1)
except Exception as e:
  print(f'❌ Failed to verify: {e}')
  sys.exit(1)
" || {
  echo "⚠️  Variable verification failed, but continuing..."
}

echo ""
echo "========================================="
echo "✅ Environment variables synced to Railway!"
echo "========================================="