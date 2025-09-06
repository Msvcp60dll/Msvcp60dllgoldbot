-- PART 2: Indexes and Constraints (Run this after tables are created)

-- Add foreign keys
ALTER TABLE users ADD CONSTRAINT fk_users_referrer 
    FOREIGN KEY (referrer_id) REFERENCES users(user_id) ON DELETE SET NULL;

ALTER TABLE subscriptions ADD CONSTRAINT fk_subscriptions_user 
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE;

ALTER TABLE payments ADD CONSTRAINT fk_payments_user 
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE;

ALTER TABLE payments ADD CONSTRAINT fk_payments_subscription 
    FOREIGN KEY (subscription_id) REFERENCES subscriptions(subscription_id) ON DELETE SET NULL;

ALTER TABLE recurring_subs ADD CONSTRAINT fk_recurring_user 
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE;

-- Create unique indexes for payment idempotency
CREATE UNIQUE INDEX IF NOT EXISTS uniq_payments_charge_id
    ON payments(charge_id) WHERE charge_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uniq_payments_star_tx
    ON payments(star_tx_id) WHERE star_tx_id IS NOT NULL;

-- Create performance indexes
-- Ensure one active/grace subscription per user for ON CONFLICT logic
CREATE UNIQUE INDEX IF NOT EXISTS uniq_sub_active_grace_per_user
    ON subscriptions(user_id) WHERE status IN ('active', 'grace');

CREATE INDEX IF NOT EXISTS idx_users_status ON users(status);
CREATE INDEX IF NOT EXISTS idx_users_referrer ON users(referrer_id);

CREATE INDEX IF NOT EXISTS idx_subscriptions_user_id ON subscriptions(user_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_status ON subscriptions(status);
CREATE INDEX IF NOT EXISTS idx_subscriptions_expires_at ON subscriptions(expires_at);
CREATE INDEX IF NOT EXISTS idx_subscriptions_grace_until ON subscriptions(grace_until);

CREATE INDEX IF NOT EXISTS idx_payments_user_id ON payments(user_id);
CREATE INDEX IF NOT EXISTS idx_payments_created_at ON payments(created_at);

CREATE INDEX IF NOT EXISTS idx_whitelist_user_id ON whitelist(user_id);
CREATE INDEX IF NOT EXISTS idx_whitelist_burned_at ON whitelist(burned_at);

CREATE INDEX IF NOT EXISTS idx_funnel_events_user_id ON funnel_events(user_id);
CREATE INDEX IF NOT EXISTS idx_funnel_events_type ON funnel_events(event_type);
CREATE INDEX IF NOT EXISTS idx_funnel_events_created_at ON funnel_events(created_at);

CREATE INDEX IF NOT EXISTS idx_notifications_queue_sent ON notifications_queue(sent);
CREATE INDEX IF NOT EXISTS idx_notifications_queue_user_id ON notifications_queue(user_id);

-- Insert initial data
INSERT INTO star_tx_cursor (id, last_tx_at) VALUES (1, NULL) ON CONFLICT DO NOTHING;

-- Add owner to whitelist
INSERT INTO whitelist (user_id, reason) 
VALUES (306145881, 'Bot owner') 
ON CONFLICT DO NOTHING;
