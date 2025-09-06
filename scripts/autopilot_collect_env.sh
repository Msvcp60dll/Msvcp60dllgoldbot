#!/usr/bin/env bash
set -euo pipefail

# Prompt for a var only if not set and we are in an interactive TTY
maybe_prompt() {
  local name="$1"; local silent="${2:-}"
  if [[ -z "${!name:-}" ]]; then
    if [[ -t 0 ]]; then
      if [[ -n "$silent" ]]; then
        read -r -s -p "Enter $name: " value; echo
      else
        read -r -p "Enter $name: " value
      fi
      export "$name"="$value"
    else
      echo "[warn] $name not set and no TTY; skipping prompt" >&2
    fi
  fi
}

# Required
maybe_prompt RAILWAY_TOKEN s
maybe_prompt RAILWAY_PROJECT_ID
maybe_prompt RAILWAY_SERVICE_NAME
maybe_prompt BOT_TOKEN s
maybe_prompt GROUP_CHAT_ID
maybe_prompt OWNER_IDS
maybe_prompt DATABASE_URL s
maybe_prompt SUPABASE_URL
maybe_prompt SUPABASE_SERVICE_KEY s
maybe_prompt WEBHOOK_SECRET s

# Optional with defaults
export PLAN_STARS="${PLAN_STARS:-499}"
export PLAN_DAYS="${PLAN_DAYS:-30}"
export SUB_ENABLED="${SUB_ENABLED:-true}"
export SUB_STARS="${SUB_STARS:-449}"
export GRACE_HOURS="${GRACE_HOURS:-48}"
export RECONCILE_WINDOW_DAYS="${RECONCILE_WINDOW_DAYS:-3}"
export DASHBOARD_ENABLED="${DASHBOARD_ENABLED:-true}"
export DASHBOARD_TOKENS="${DASHBOARD_TOKENS:-}"
export NIXPACKS_PYTHON_VERSION="${NIXPACKS_PYTHON_VERSION:-3.11}"
export PYTHONUNBUFFERED="${PYTHONUNBUFFERED:-1}"
export PYTHONDONTWRITEBYTECODE="${PYTHONDONTWRITEBYTECODE:-1}"

mask() { local v="$1"; echo "${v:0:2}***${v: -2}"; }

echo "Collected env (masked where sensitive):"
for v in RAILWAY_PROJECT_ID RAILWAY_SERVICE_NAME GROUP_CHAT_ID OWNER_IDS SUPABASE_URL PLAN_STARS PLAN_DAYS SUB_ENABLED SUB_STARS GRACE_HOURS RECONCILE_WINDOW_DAYS DASHBOARD_ENABLED NIXPACKS_PYTHON_VERSION PYTHONUNBUFFERED PYTHONDONTWRITEBYTECODE; do
  printf " - %s=%s\n" "$v" "${!v:-<unset>}"
done
for s in RAILWAY_TOKEN BOT_TOKEN DATABASE_URL SUPABASE_SERVICE_KEY WEBHOOK_SECRET; do
  if [[ -n "${!s:-}" ]]; then printf " - %s=%s\n" "$s" "$(mask "${!s}")"; else printf " - %s=<unset>\n" "$s"; fi
done

exit 0

