-- Migration: Query optimization improvements
-- Author: System
-- Date: 2025-01-05
-- Description: Additional indexes and query optimizations for dashboard and analytics

-- UP

BEGIN;

-- Partial indexes for specific query patterns
-- For finding users who haven't paid yet
CREATE INDEX IF NOT EXISTS idx_users_no_payment 
    ON users(user_id)
    WHERE NOT EXISTS (
        SELECT 1 FROM payments p WHERE p.user_id = users.user_id
    );

-- For finding expired subscriptions that need cleanup
CREATE INDEX IF NOT EXISTS idx_subscriptions_expired_cleanup 
    ON subscriptions(user_id, expires_at)
    WHERE status = 'expired' AND expires_at < NOW() - INTERVAL '30 days';

-- Dashboard statistics optimization
-- Covering index for the dashboard summary query
CREATE INDEX IF NOT EXISTS idx_payments_dashboard_summary 
    ON payments(created_at DESC, payment_type, amount, is_recurring)
    WHERE created_at >= NOW() - INTERVAL '30 days';

-- For MRR (Monthly Recurring Revenue) calculation
CREATE INDEX IF NOT EXISTS idx_subscriptions_mrr 
    ON subscriptions(is_recurring, status)
    WHERE is_recurring = true AND status IN ('active', 'grace');

-- Reconciliation optimization
-- For finding unmatched Star transactions
CREATE INDEX IF NOT EXISTS idx_payments_star_tx_lookup 
    ON payments(star_tx_id)
    WHERE star_tx_id IS NOT NULL;

-- For charge ID lookups during payment processing
CREATE INDEX IF NOT EXISTS idx_payments_charge_lookup 
    ON payments(charge_id)
    WHERE charge_id IS NOT NULL;

-- Create partial indexes for whitelist burn rules
CREATE INDEX IF NOT EXISTS idx_whitelist_pending_burn 
    ON whitelist(telegram_id, granted_at)
    WHERE revoked_at IS NULL;

-- Update table statistics for better query planning
ANALYZE subscriptions;
ANALYZE payments;
ANALYZE funnel_events;
ANALYZE users;
ANALYZE whitelist;

COMMIT;

-- Log success
DO $$ 
BEGIN
    RAISE NOTICE 'Successfully created query optimization indexes';
END $$;

-- DOWN

BEGIN;

-- Drop indexes in reverse order
DROP INDEX IF EXISTS idx_whitelist_pending_burn;
DROP INDEX IF EXISTS idx_payments_charge_lookup;
DROP INDEX IF EXISTS idx_payments_star_tx_lookup;
DROP INDEX IF EXISTS idx_subscriptions_mrr;
DROP INDEX IF EXISTS idx_payments_dashboard_summary;
DROP INDEX IF EXISTS idx_subscriptions_expired_cleanup;
DROP INDEX IF EXISTS idx_users_no_payment;

COMMIT;

-- Log rollback
DO $$ 
BEGIN
    RAISE NOTICE 'Successfully rolled back query optimization indexes';
END $$;