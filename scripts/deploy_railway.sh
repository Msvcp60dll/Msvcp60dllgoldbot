#!/bin/bash

# Railway Deployment Script for Telegram Stars Membership Bot
# This script helps deploy the bot to Railway with proper configuration

set -e

echo "======================================"
echo "Railway Deployment Script"
echo "======================================"

# Check if railway CLI is installed
if ! command -v railway &> /dev/null; then
    echo "❌ Railway CLI not found. Please install it first:"
    echo "   brew install railway"
    echo "   or"
    echo "   npm install -g @railway/cli"
    exit 1
fi

# Check if logged in to Railway
echo "🔐 Checking Railway authentication..."
if ! railway whoami &> /dev/null; then
    echo "📝 Please log in to Railway:"
    railway login
fi

# Display current user
echo "✅ Logged in as: $(railway whoami)"

# Create or link project
echo ""
echo "🚂 Setting up Railway project..."
echo "Choose an option:"
echo "1. Create new Railway project"
echo "2. Link to existing Railway project"
read -p "Enter your choice (1 or 2): " choice

if [ "$choice" = "1" ]; then
    read -p "Enter project name (default: msvcp60dll-bot): " project_name
    project_name=${project_name:-msvcp60dll-bot}
    railway init -n "$project_name"
    echo "✅ Created new project: $project_name"
elif [ "$choice" = "2" ]; then
    railway link
    echo "✅ Linked to existing project"
else
    echo "❌ Invalid choice"
    exit 1
fi

# Set environment variables
echo ""
echo "📝 Setting environment variables..."
echo "Note: You'll need to add your database password manually in Railway dashboard"

# Read from .env file and set in Railway
while IFS='=' read -r key value; do
    # Skip comments and empty lines
    if [[ ! "$key" =~ ^#.*$ ]] && [[ -n "$key" ]]; then
        # Remove quotes from value
        value=$(echo "$value" | sed 's/^"\(.*\)"$/\1/')
        
        # Skip setting SUPABASE_SERVICE_KEY since it's not the DB password
        if [[ "$key" == "SUPABASE_SERVICE_KEY" ]]; then
            echo "⚠️  Skipping SUPABASE_SERVICE_KEY (need database password instead)"
            continue
        fi
        
        echo "Setting $key..."
        railway variables set "$key=$value" &> /dev/null || true
    fi
done < .env

# Add Railway-specific variables
echo "Setting PORT=8080..."
railway variables set PORT=8080

# Important note about database
echo ""
echo "⚠️  IMPORTANT: Database Configuration"
echo "=================================="
echo "You need to set the database password in Railway:"
echo ""
echo "1. Go to your Supabase Dashboard"
echo "2. Navigate to Settings → Database"
echo "3. Find or reset your database password"
echo "4. In Railway dashboard, add:"
echo "   DATABASE_PASSWORD=your_actual_db_password"
echo ""

read -p "Press Enter when you've set the database password in Railway..."

# Deploy
echo ""
echo "🚀 Deploying to Railway..."
railway up

echo ""
echo "✅ Deployment initiated!"
echo ""
echo "📋 Next steps:"
echo "1. Check deployment logs: railway logs"
echo "2. Get your app URL: railway open"
echo "3. Update WEBHOOK_HOST in Railway with your app URL"
echo "4. Monitor health: railway status"
echo ""
echo "🔧 Useful commands:"
echo "- View logs: railway logs"
echo "- Open dashboard: railway open"
echo "- Check status: railway status"
echo "- Redeploy: railway up"