-- v1.3 Schema for Telegram Stars Membership Bot
-- Includes idempotency, grace periods, reconciliation

-- Enable UUID extension if needed
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- User status enum
CREATE TYPE user_status AS ENUM ('active', 'inactive', 'banned');

-- Subscription status enum with grace
DO $$ BEGIN
    CREATE TYPE sub_status AS ENUM ('pending', 'active', 'grace', 'expired', 'cancelled');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- Payment type enum
CREATE TYPE payment_type AS ENUM ('one_time', 'recurring_initial', 'recurring_renewal');

-- Core users table
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    last_name TEXT,
    language_code TEXT DEFAULT 'en',
    status user_status DEFAULT 'inactive',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ,
    referrer_id BIGINT REFERENCES users(user_id),
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Subscriptions with grace period support
CREATE TABLE IF NOT EXISTS subscriptions (
    subscription_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id BIGINT NOT NULL REFERENCES users(user_id),
    status sub_status DEFAULT 'pending',
    is_recurring BOOLEAN DEFAULT FALSE,
    expires_at TIMESTAMPTZ,
    grace_until TIMESTAMPTZ,
    next_billing_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    cancelled_at TIMESTAMPTZ,
    grace_started_at TIMESTAMPTZ,
    reminder_sent_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Payments with idempotency keys
CREATE TABLE IF NOT EXISTS payments (
    payment_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id BIGINT NOT NULL REFERENCES users(user_id),
    charge_id TEXT,
    star_tx_id TEXT,
    amount INTEGER NOT NULL,
    currency TEXT DEFAULT 'XTR',
    payment_type payment_type NOT NULL,
    is_recurring BOOLEAN DEFAULT FALSE,
    subscription_id UUID REFERENCES subscriptions(subscription_id),
    invoice_payload TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Unique indexes for idempotency
CREATE UNIQUE INDEX IF NOT EXISTS uniq_payments_charge_id
    ON payments(charge_id) WHERE charge_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uniq_payments_star_tx
    ON payments(star_tx_id) WHERE star_tx_id IS NOT NULL;

-- Whitelist for existing members
CREATE TABLE IF NOT EXISTS whitelist (
    whitelist_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id BIGINT NOT NULL,
    added_by BIGINT,
    reason TEXT,
    expires_at TIMESTAMPTZ,
    burned_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Funnel events for analytics
CREATE TABLE IF NOT EXISTS funnel_events (
    event_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id BIGINT,
    event_type TEXT NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Recurring subscription tracking
CREATE TABLE IF NOT EXISTS recurring_subs (
    user_id BIGINT PRIMARY KEY REFERENCES users(user_id),
    charge_id TEXT NOT NULL,
    subscription_period INTEGER DEFAULT 2592000,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Star transaction reconciliation cursor
CREATE TABLE IF NOT EXISTS star_tx_cursor (
    id INTEGER PRIMARY KEY DEFAULT 1,
    last_tx_at TIMESTAMPTZ,
    last_tx_id TEXT,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Failed payments queue for manual review
CREATE TABLE IF NOT EXISTS failed_payments_queue (
    queue_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id BIGINT,
    charge_id TEXT,
    error TEXT,
    raw_update JSONB,
    resolved BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Notifications queue
CREATE TABLE IF NOT EXISTS notifications_queue (
    notification_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id BIGINT NOT NULL,
    type TEXT NOT NULL,
    sent BOOLEAN DEFAULT FALSE,
    sent_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for performance
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

-- Helper functions
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Auto-update timestamps
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_subscriptions_updated_at BEFORE UPDATE ON subscriptions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- Initial data
INSERT INTO star_tx_cursor (id, last_tx_at) VALUES (1, NULL) ON CONFLICT DO NOTHING;