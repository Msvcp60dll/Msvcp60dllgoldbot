#!/usr/bin/env bash
set -euo pipefail

if ! command -v railway >/dev/null 2>&1; then
  echo "ERROR: Railway CLI not found. Install it first." >&2
  exit 2
fi

SERVICE_ARGS=()
if [[ -n "${RAILWAY_SERVICE_NAME:-}" ]]; then
  SERVICE_ARGS=(--service "$RAILWAY_SERVICE_NAME")
fi

set_kv() {
  local k="$1"; local v="$2"
  if [[ -n "$v" ]]; then
    railway variables set "$k=$v" "${SERVICE_ARGS[@]}" >/dev/null || {
      echo "[warn] Failed to set $k"
    }
  fi
}

set_kv BOT_TOKEN "${BOT_TOKEN:-}"
set_kv GROUP_CHAT_ID "${GROUP_CHAT_ID:-}"
set_kv OWNER_IDS "${OWNER_IDS:-}"
set_kv DATABASE_URL "${DATABASE_URL:-}"
set_kv SUPABASE_URL "${SUPABASE_URL:-}"
set_kv SUPABASE_SERVICE_KEY "${SUPABASE_SERVICE_KEY:-}"
set_kv WEBHOOK_SECRET "${WEBHOOK_SECRET:-}"
set_kv TELEGRAM_SECRET_TOKEN "${WEBHOOK_SECRET:-}"
set_kv PLAN_STARS "${PLAN_STARS:-}"
set_kv PLAN_DAYS "${PLAN_DAYS:-}"
set_kv SUB_ENABLED "${SUB_ENABLED:-}"
set_kv SUB_STARS "${SUB_STARS:-}"
set_kv GRACE_HOURS "${GRACE_HOURS:-}"
set_kv RECONCILE_WINDOW_DAYS "${RECONCILE_WINDOW_DAYS:-}"
set_kv DASHBOARD_ENABLED "${DASHBOARD_ENABLED:-}"
set_kv DASHBOARD_TOKENS "${DASHBOARD_TOKENS:-}"
set_kv NIXPACKS_PYTHON_VERSION "${NIXPACKS_PYTHON_VERSION:-}"
set_kv PYTHONUNBUFFERED "${PYTHONUNBUFFERED:-}"
set_kv PYTHONDONTWRITEBYTECODE "${PYTHONDONTWRITEBYTECODE:-}"

echo "Variables pushed (secrets masked in logs)."
exit 0

