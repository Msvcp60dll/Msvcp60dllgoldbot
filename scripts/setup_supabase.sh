#!/bin/bash

# Supabase Table Setup Script
# This script outputs the SQL needed to create all tables in Supabase

echo "======================================"
echo "Supabase Database Setup Instructions"
echo "======================================"
echo ""
echo "1. Go to Supabase Dashboard:"
echo "   https://supabase.com/dashboard/project/cudmllwhxpamaiqxohse/sql"
echo ""
echo "2. Click 'New Query'"
echo ""
echo "3. Copy and paste ALL the SQL below:"
echo ""
echo "======================================"
echo ""

cat app/models.sql

echo ""
echo "======================================"
echo ""
echo "4. Click 'Run' to execute the SQL"
echo ""
echo "5. You should see 'Success' message"
echo ""
echo "6. Verify tables were created:"
echo "   - Go to Table Editor in Supabase"
echo "   - You should see these tables:"
echo "     • users"
echo "     • subscriptions"
echo "     • payments"
echo "     • whitelist"
echo "     • funnel_events"
echo "     • recurring_subs"
echo "     • star_tx_cursor"
echo "     • failed_payments_queue"
echo "     • notifications_queue"
echo ""
echo "======================================"