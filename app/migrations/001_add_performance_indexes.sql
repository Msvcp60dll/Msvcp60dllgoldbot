-- Migration: Add critical performance indexes for Telegram Stars subscription bot
-- Author: System
-- Date: 2025-01-05
-- Description: Adds indexes for frequently queried columns to improve query performance

-- UP

BEGIN;

-- Subscriptions table indexes
-- Most common query: find active/grace subscriptions for a user
CREATE INDEX IF NOT EXISTS idx_subscriptions_user_status 
    ON subscriptions(user_id, status)
    WHERE status IN ('active', 'grace');

-- For grace period checks and expiry processing
CREATE INDEX IF NOT EXISTS idx_subscriptions_expires_at 
    ON subscriptions(expires_at)
    WHERE status = 'active';

-- For grace period expiry processing  
CREATE INDEX IF NOT EXISTS idx_subscriptions_grace_until 
    ON subscriptions(grace_until)
    WHERE status = 'grace' AND grace_until IS NOT NULL;

-- Composite index for scheduler queries
CREATE INDEX IF NOT EXISTS idx_subscriptions_status_expires 
    ON subscriptions(status, expires_at)
    WHERE status IN ('active', 'grace');

-- Payments table indexes
-- For reconciliation window queries
CREATE INDEX IF NOT EXISTS idx_payments_created_at 
    ON payments(created_at DESC);

-- For user payment history
CREATE INDEX IF NOT EXISTS idx_payments_user_id 
    ON payments(user_id, created_at DESC);

-- For finding recurring payments
CREATE INDEX IF NOT EXISTS idx_payments_recurring 
    ON payments(is_recurring, created_at DESC)
    WHERE is_recurring = true;

-- Composite index for payment lookups
CREATE INDEX IF NOT EXISTS idx_payments_user_type 
    ON payments(user_id, payment_type, created_at DESC);

-- Funnel events table indexes
-- For analytics and dashboard queries
CREATE INDEX IF NOT EXISTS idx_funnel_events_created_type 
    ON funnel_events(created_at DESC, event_type);

-- For user-specific event history
CREATE INDEX IF NOT EXISTS idx_funnel_events_user 
    ON funnel_events(telegram_id, created_at DESC);

-- For event type aggregations
CREATE INDEX IF NOT EXISTS idx_funnel_events_type_created 
    ON funnel_events(event_type, created_at DESC);

-- Whitelist table indexes (if not already present)
CREATE INDEX IF NOT EXISTS idx_whitelist_active 
    ON whitelist(telegram_id)
    WHERE revoked_at IS NULL;

-- Users table indexes
-- For finding users by Telegram ID (primary key already indexed)
-- For finding users by last activity
CREATE INDEX IF NOT EXISTS idx_users_last_seen 
    ON users(last_seen_at DESC);

-- Analyze tables to update statistics for query planner
ANALYZE subscriptions;
ANALYZE payments;
ANALYZE funnel_events;
ANALYZE whitelist;
ANALYZE users;

COMMIT;

-- Log success
DO $$ 
BEGIN
    RAISE NOTICE 'Successfully created performance indexes';
END $$;

-- DOWN

BEGIN;

-- Drop indexes in reverse order
DROP INDEX IF EXISTS idx_users_last_seen;
DROP INDEX IF EXISTS idx_whitelist_active;
DROP INDEX IF EXISTS idx_funnel_events_type_created;
DROP INDEX IF EXISTS idx_funnel_events_user;
DROP INDEX IF EXISTS idx_funnel_events_created_type;
DROP INDEX IF EXISTS idx_payments_user_type;
DROP INDEX IF EXISTS idx_payments_recurring;
DROP INDEX IF EXISTS idx_payments_user_id;
DROP INDEX IF EXISTS idx_payments_created_at;
DROP INDEX IF EXISTS idx_subscriptions_status_expires;
DROP INDEX IF EXISTS idx_subscriptions_grace_until;
DROP INDEX IF EXISTS idx_subscriptions_expires_at;
DROP INDEX IF EXISTS idx_subscriptions_user_status;

COMMIT;

-- Log rollback
DO $$ 
BEGIN
    RAISE NOTICE 'Successfully rolled back performance indexes';
END $$;