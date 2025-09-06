#!/usr/bin/env bash
set -euo pipefail

echo "========================================="
echo "AUTOPILOT: Checking/Installing Tools"
echo "========================================="

# Check Railway CLI
if ! command -v railway >/dev/null 2>&1; then
  echo "❌ Railway CLI not found. Installing..."
  if [[ "$OSTYPE" == "darwin"* ]]; then
    brew install railway || {
      echo "Failed to install via Homebrew. Try: curl -fsSL https://railway.app/install.sh | sh"
      exit 1
    }
  else
    curl -fsSL https://railway.app/install.sh | sh || {
      echo "Failed to install Railway CLI"
      exit 1
    }
  fi
  echo "✅ Railway CLI installed"
else
  echo "✅ Railway CLI found: $(railway --version 2>/dev/null || echo 'version check failed')"
fi

# Check Python
if ! command -v python3 >/dev/null 2>&1; then
  echo "❌ Python3 not found. Please install Python 3.11+"
  exit 1
else
  echo "✅ Python found: $(python3 --version)"
fi

# Check psql (for database operations)
if ! command -v psql >/dev/null 2>&1; then
  echo "⚠️  psql not found. Database migrations may fail."
  echo "   To install: brew install postgresql (macOS) or apt install postgresql-client (Linux)"
else
  echo "✅ psql found: $(psql --version | head -1)"
fi

# Check jq (for JSON parsing)
if ! command -v jq >/dev/null 2>&1; then
  echo "⚠️  jq not found. Some scripts may have reduced functionality."
  echo "   To install: brew install jq (macOS) or apt install jq (Linux)"
else
  echo "✅ jq found"
fi

# Check Railway authentication
echo ""
echo "Checking Railway authentication..."
if railway whoami >/dev/null 2>&1; then
  echo "✅ Railway authenticated as: $(railway whoami 2>/dev/null)"
else
  echo "❌ Not authenticated with Railway"
  echo "   Run: railway login"
  exit 1
fi

# Check for linked project
echo ""
echo "Checking Railway project link..."
if railway status --json >/dev/null 2>&1; then
  echo "✅ Railway project linked"
else
  echo "⚠️  No Railway project linked in this directory"
  echo "   Will attempt to link during deployment"
fi

echo ""
echo "========================================="
echo "✅ Tool check complete!"
echo "========================================="