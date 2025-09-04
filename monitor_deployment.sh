#!/bin/bash

# Railway Deployment Monitor
# Based on proven successful pattern

SERVICE_NAME="msvcp60dll-bot"

check_status() {
    railway status --json 2>/dev/null | python3 -c "
import json
import sys

try:
    data = json.load(sys.stdin)
    # Look for our service in the project
    project = data.get('project', {})
    if project:
        # The service should be in the project
        print(f'Project: {project.get(\"name\", \"Unknown\")}')
    
    # Try to find deployment status
    print('Status: CHECKING')
    sys.exit(2)
except Exception as e:
    print(f'Error: {e}')
    sys.exit(2)
"
}

echo "🚂 Monitoring Railway deployment..."
echo "Service: $SERVICE_NAME"
echo ""

MAX_ATTEMPTS=60
for i in $(seq 1 $MAX_ATTEMPTS); do
    STATUS_OUTPUT=$(check_status 2>&1)
    echo "[$i/$MAX_ATTEMPTS] $STATUS_OUTPUT"
    
    # Check for success patterns in logs
    LOGS=$(railway logs 2>&1 || echo "")
    
    if echo "$LOGS" | grep -q "Health check server started"; then
        echo "✅ Health server is running!"
    fi
    
    if echo "$LOGS" | grep -q "Application started successfully"; then
        echo "✅ Deployment successful!"
        echo ""
        echo "📝 Recent logs:"
        railway logs 2>/dev/null | tail -20
        exit 0
    fi
    
    if echo "$LOGS" | grep -q "Fatal error"; then
        echo "❌ Deployment failed!"
        echo "Check logs: railway logs"
        exit 1
    fi
    
    if [ $i -eq $MAX_ATTEMPTS ]; then
        echo "⏱ Timeout waiting for deployment"
        echo "Current logs:"
        railway logs 2>/dev/null | tail -20
        exit 2
    fi
    
    sleep 5
done