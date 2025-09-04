-- PART 1: Basic Tables Setup (Run this first)
-- Simple schema without complex types for Supabase

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create users table
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    last_name TEXT,
    language_code TEXT DEFAULT 'en',
    status TEXT DEFAULT 'inactive',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ,
    referrer_id BIGINT,
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Create subscriptions table
CREATE TABLE IF NOT EXISTS subscriptions (
    subscription_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id BIGINT NOT NULL,
    status TEXT DEFAULT 'pending',
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

-- Create payments table
CREATE TABLE IF NOT EXISTS payments (
    payment_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id BIGINT NOT NULL,
    charge_id TEXT,
    star_tx_id TEXT,
    amount INTEGER NOT NULL,
    currency TEXT DEFAULT 'XTR',
    payment_type TEXT NOT NULL,
    is_recurring BOOLEAN DEFAULT FALSE,
    subscription_id UUID,
    invoice_payload TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'::jsonb
);

-- Create whitelist table
CREATE TABLE IF NOT EXISTS whitelist (
    whitelist_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id BIGINT NOT NULL,
    added_by BIGINT,
    reason TEXT,
    expires_at TIMESTAMPTZ,
    burned_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create funnel_events table
CREATE TABLE IF NOT EXISTS funnel_events (
    event_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id BIGINT,
    event_type TEXT NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create recurring_subs table
CREATE TABLE IF NOT EXISTS recurring_subs (
    user_id BIGINT PRIMARY KEY,
    charge_id TEXT NOT NULL,
    subscription_period INTEGER DEFAULT 2592000,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create star_tx_cursor table
CREATE TABLE IF NOT EXISTS star_tx_cursor (
    id INTEGER PRIMARY KEY DEFAULT 1,
    last_tx_at TIMESTAMPTZ,
    last_tx_id TEXT,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create failed_payments_queue table
CREATE TABLE IF NOT EXISTS failed_payments_queue (
    queue_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id BIGINT,
    charge_id TEXT,
    error TEXT,
    raw_update JSONB,
    resolved BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create notifications_queue table
CREATE TABLE IF NOT EXISTS notifications_queue (
    notification_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id BIGINT NOT NULL,
    type TEXT NOT NULL,
    sent BOOLEAN DEFAULT FALSE,
    sent_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW()
);