#!/usr/bin/env bash
set -euo pipefail

echo "=============================================="
echo "🚀 AUTOPILOT: Full Production Deployment"
echo "=============================================="
echo "Started at: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

# Track overall status
FAILED_STEPS=""

run_step() {
  local step_name="$1"
  local script_path="$2"
  
  echo ""
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "Step: $step_name"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  
  if [[ -f "$script_path" ]]; then
    chmod +x "$script_path"
    if "$script_path"; then
      echo "✅ $step_name completed successfully"
      return 0
    else
      echo "❌ $step_name failed"
      FAILED_STEPS="${FAILED_STEPS}${step_name}\n"
      return 1
    fi
  else
    echo "⚠️  Script not found: $script_path"
    FAILED_STEPS="${FAILED_STEPS}${step_name} (not found)\n"
    return 1
  fi
}

# Phase 1: Prerequisites
echo "📋 PHASE 1: Prerequisites"
run_step "Tool Check" "$SCRIPT_DIR/autopilot_tools.sh" || {
  echo "❌ Critical: Tool check failed. Aborting."
  exit 1
}

# Phase 2: Configuration
echo ""
echo "📋 PHASE 2: Configuration"
run_step "Push Environment Variables" "$SCRIPT_DIR/autopilot_push_env.sh" || {
  echo "⚠️  Environment sync failed, continuing anyway..."
}

# Phase 3: Database
echo ""
echo "📋 PHASE 3: Database Setup"
run_step "Apply Database Schema" "$SCRIPT_DIR/apply_schema.sh" || {
  echo "⚠️  Schema application failed, continuing anyway..."
}

# Phase 4: Deployment
echo ""
echo "📋 PHASE 4: Railway Deployment"
run_step "Deploy to Railway" "$SCRIPT_DIR/autopilot_deploy.sh" || {
  echo "❌ Deployment failed. Check logs with: railway logs"
  # Don't exit, continue to try webhook setup
}

# Wait for deployment to stabilize
echo ""
echo "⏳ Waiting 30 seconds for deployment to stabilize..."
sleep 30

# Phase 5: Webhook Setup
echo ""
echo "📋 PHASE 5: Webhook Configuration"
run_step "Configure Telegram Webhook" "$SCRIPT_DIR/set_webhook.sh" || {
  echo "⚠️  Webhook setup failed. You may need to set it manually."
}

# Phase 6: Verification
echo ""
echo "📋 PHASE 6: Production Verification"
echo "⏳ Waiting 10 seconds before smoke tests..."
sleep 10

run_step "Smoke Test Report" "$SCRIPT_DIR/smoke_report.sh" || {
  echo "⚠️  Some smoke tests failed. Review the report above."
}

# Final Summary
echo ""
echo ""
echo "=============================================="
echo "📊 DEPLOYMENT SUMMARY"
echo "=============================================="
echo "Completed at: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

if [[ -z "$FAILED_STEPS" ]]; then
  echo "✅ ALL STEPS COMPLETED SUCCESSFULLY!"
  echo ""
  echo "🎉 Your bot is now LIVE in production!"
  echo ""
  echo "Important URLs:"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  
  if [[ -f .env ]]; then
    source .env
    echo "🤖 Bot: @$(curl -s "https://api.telegram.org/bot$BOT_TOKEN/getMe" 2>/dev/null | python3 -c "import json,sys; print(json.load(sys.stdin).get('result',{}).get('username','your_bot'))" 2>/dev/null || echo "your_bot")"
    echo "🌐 Domain: https://${PUBLIC_BASE_URL:-msvcp60dllgoldbot-production.up.railway.app}"
    echo "📊 Dashboard: https://${PUBLIC_BASE_URL:-msvcp60dllgoldbot-production.up.railway.app}/admin/dashboard"
    echo "   (Auth: Bearer ${DASHBOARD_TOKENS%%,*})"
  fi
  
  echo ""
  echo "Quick Commands:"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "📝 View logs:        railway logs -f"
  echo "📊 Check status:     railway status"
  echo "🌐 Open dashboard:   railway open"
  echo "🔄 Redeploy:        railway up"
  echo "🧪 Run smoke test:  ./scripts/smoke_report.sh"
  
else
  echo "⚠️  DEPLOYMENT COMPLETED WITH WARNINGS"
  echo ""
  echo "Failed steps:"
  echo -e "$FAILED_STEPS"
  echo ""
  echo "Debug commands:"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "📝 Check logs:       railway logs --tail 100"
  echo "🔍 Test locally:     python main.py"
  echo "🔄 Retry webhook:    ./scripts/set_webhook.sh"
  echo "📊 Verify status:    ./scripts/smoke_report.sh"
fi

echo ""
echo "=============================================="
echo "✨ Autopilot sequence complete!"
echo "=============================================="