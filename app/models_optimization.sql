-- Additional indexes for query optimization
-- Based on audit findings

-- Composite index for frequently used query pattern in get_active_subscription()
CREATE INDEX IF NOT EXISTS idx_subscriptions_user_status 
    ON subscriptions(user_id, status);

-- Index for payment queries filtered by user and date
CREATE INDEX IF NOT EXISTS idx_payments_user_created 
    ON payments(user_id, created_at DESC);

-- Index for recent payment analytics (last 30 days)
CREATE INDEX IF NOT EXISTS idx_payments_created_amount 
    ON payments(created_at, amount) 
    WHERE created_at > NOW() - INTERVAL '30 days';

-- Index for reconciliation queries
CREATE INDEX IF NOT EXISTS idx_payments_star_tx_created
    ON payments(star_tx_id, created_at)
    WHERE star_tx_id IS NOT NULL;

-- Composite index for whitelist queries
CREATE INDEX IF NOT EXISTS idx_whitelist_user_burned 
    ON whitelist(user_id, burned_at);

-- Index for grace period queries
CREATE INDEX IF NOT EXISTS idx_subscriptions_status_grace
    ON subscriptions(status, grace_until)
    WHERE status = 'grace';

-- Index for expiring subscriptions
CREATE INDEX IF NOT EXISTS idx_subscriptions_status_expires
    ON subscriptions(status, expires_at)
    WHERE status IN ('active', 'grace');

-- Analyze tables to update statistics for query planner
ANALYZE users;
ANALYZE subscriptions;
ANALYZE payments;
ANALYZE whitelist;
ANALYZE funnel_events;