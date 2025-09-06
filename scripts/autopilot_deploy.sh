#!/usr/bin/env bash
set -euo pipefail

echo "========================================="
echo "AUTOPILOT: Railway Deployment"
echo "========================================="

# Check if Railway is linked
if ! railway status --json >/dev/null 2>&1; then
  echo "⚠️  No Railway project linked"
  echo "Attempting to link project..."
  
  # Try to find and link the project
  PROJECT_NAME="msvcp60dllgoldbot"
  echo "Looking for project: $PROJECT_NAME"
  
  # Get projects list
  PROJECTS=$(railway list --json 2>/dev/null || echo '[]')
  
  # Parse and find project ID
  PROJECT_ID=$(echo "$PROJECTS" | python3 -c "
import json, sys
try:
    projects = json.load(sys.stdin)
    for p in projects:
        if p.get('name', '').lower() == '$PROJECT_NAME':
            print(p.get('id', ''))
            break
except:
    pass
")
  
  if [[ -n "$PROJECT_ID" ]]; then
    echo "Found project ID: $PROJECT_ID"
    railway link "$PROJECT_ID" || {
      echo "❌ Failed to link project"
      exit 1
    }
    echo "✅ Project linked"
  else
    echo "❌ Could not find project '$PROJECT_NAME'"
    echo "Please run: railway link"
    exit 1
  fi
fi

# Get deployment status
echo ""
echo "Current deployment status:"
railway status || true

# Deploy with verbose output
echo ""
echo "Starting deployment..."
echo "This may take 2-5 minutes..."

# Create deployment timestamp
DEPLOY_TIME=$(date +"%Y-%m-%d %H:%M:%S")
echo "Deployment initiated at: $DEPLOY_TIME"

# Run deployment
railway up --detach || {
  echo "❌ Deployment failed"
  echo "Check logs with: railway logs"
  exit 1
}

echo ""
echo "✅ Deployment triggered successfully!"

# Wait for deployment to start
echo ""
echo "Waiting for deployment to initialize..."
sleep 10

# Monitor deployment (non-blocking)
echo ""
echo "Deployment logs (last 20 lines):"
railway logs -n 20 || true

echo ""
echo "========================================="
echo "✅ Deployment initiated!"
echo "========================================="
echo ""
echo "Monitor progress with:"
echo "  railway logs -f"
echo ""
echo "Check status with:"
echo "  railway status"
echo ""
echo "Open in browser:"
echo "  railway open"