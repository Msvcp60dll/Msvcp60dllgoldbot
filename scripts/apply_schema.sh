#!/usr/bin/env bash
set -euo pipefail

echo "========================================="
echo "AUTOPILOT: Applying Database Schema"
echo "========================================="

# Load environment variables
if [[ -f .env ]]; then
  set -o allexport
  source <(grep -v '^#' .env | sed 's/#.*//g' | sed 's/[[:space:]]*$//')
  set +o allexport
fi

DATABASE_URL="${DATABASE_URL:-}"

if [[ -z "$DATABASE_URL" ]]; then
  echo "❌ DATABASE_URL not set"
  exit 1
fi

# Mask password in display
display_url=$(echo "$DATABASE_URL" | sed -E 's/(:[^:]+)@/:\*\*\*@/')
echo "📊 Database: $display_url"

echo ""
echo "Applying migrations (idempotent)..."

# Create temp file for SQL
SQL_FILE="/tmp/msvcp60_schema_$(date +%s).sql"

cat > "$SQL_FILE" << 'EOF'
-- Msvcp60dllgoldbot Schema v1.3.1 (Idempotent)
BEGIN;

-- 1. Users table
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    username VARCHAR(255),
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    is_blocked BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 2. Subscriptions table
CREATE TABLE IF NOT EXISTS subscriptions (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(user_id),
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    payment_method VARCHAR(50) NOT NULL DEFAULT 'stars',
    stars_amount INTEGER,
    expires_at TIMESTAMP,
    grace_ends_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    -- Ensure status values
    CONSTRAINT subscriptions_status_check CHECK (
        status IN ('pending', 'active', 'grace', 'expired', 'cancelled')
    )
);

-- 3. Payments table with idempotency
CREATE TABLE IF NOT EXISTS payments (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(user_id),
    subscription_id INTEGER REFERENCES subscriptions(id),
    charge_id VARCHAR(255) UNIQUE,  -- Idempotency key
    star_tx_id VARCHAR(255) UNIQUE,  -- Alternative idempotency
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    amount INTEGER NOT NULL,
    currency VARCHAR(10) DEFAULT 'XTR',
    is_recurring BOOLEAN DEFAULT FALSE,
    provider_charge_id VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW(),
    processed_at TIMESTAMP
);

-- 4. Invites table
CREATE TABLE IF NOT EXISTS invites (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(user_id),
    invite_code VARCHAR(100) UNIQUE NOT NULL,
    invite_link TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP,
    used_at TIMESTAMP,
    is_used BOOLEAN DEFAULT FALSE
);

-- 5. Analytics events
CREATE TABLE IF NOT EXISTS analytics_events (
    id SERIAL PRIMARY KEY,
    event_type VARCHAR(100) NOT NULL,
    user_id BIGINT,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 6. Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_subscriptions_user_status 
    ON subscriptions(user_id, status);
CREATE INDEX IF NOT EXISTS idx_subscriptions_expires 
    ON subscriptions(expires_at) WHERE status IN ('active', 'grace');
CREATE INDEX IF NOT EXISTS idx_subscriptions_grace 
    ON subscriptions(grace_ends_at) WHERE status = 'grace';
CREATE INDEX IF NOT EXISTS idx_payments_user 
    ON payments(user_id);
CREATE INDEX IF NOT EXISTS idx_payments_status 
    ON payments(status);
CREATE INDEX IF NOT EXISTS idx_invites_code 
    ON invites(invite_code);
CREATE INDEX IF NOT EXISTS idx_invites_user 
    ON invites(user_id);
CREATE INDEX IF NOT EXISTS idx_analytics_event_time 
    ON analytics_events(event_type, created_at DESC);

-- 7. Add missing columns (safe to run multiple times)
DO $$ 
BEGIN
    -- Add star_tx_id if missing
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'payments' AND column_name = 'star_tx_id'
    ) THEN
        ALTER TABLE payments ADD COLUMN star_tx_id VARCHAR(255) UNIQUE;
    END IF;
    
    -- Add grace_ends_at if missing
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'subscriptions' AND column_name = 'grace_ends_at'
    ) THEN
        ALTER TABLE subscriptions ADD COLUMN grace_ends_at TIMESTAMP;
    END IF;
    
    -- Add is_recurring if missing
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'payments' AND column_name = 'is_recurring'
    ) THEN
        ALTER TABLE payments ADD COLUMN is_recurring BOOLEAN DEFAULT FALSE;
    END IF;
END $$;

-- 8. Updated_at trigger function
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 9. Apply triggers
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger WHERE tgname = 'update_users_updated_at'
    ) THEN
        CREATE TRIGGER update_users_updated_at 
            BEFORE UPDATE ON users 
            FOR EACH ROW EXECUTE FUNCTION update_updated_at();
    END IF;
    
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger WHERE tgname = 'update_subscriptions_updated_at'
    ) THEN
        CREATE TRIGGER update_subscriptions_updated_at 
            BEFORE UPDATE ON subscriptions 
            FOR EACH ROW EXECUTE FUNCTION update_updated_at();
    END IF;
END $$;

COMMIT;

-- Report
SELECT 
    'Tables' as category,
    COUNT(*) as count
FROM information_schema.tables 
WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
UNION ALL
SELECT 
    'Indexes' as category,
    COUNT(*) as count
FROM pg_indexes 
WHERE schemaname = 'public'
UNION ALL
SELECT 
    'Triggers' as category,
    COUNT(*) as count
FROM pg_trigger t
JOIN pg_class c ON t.tgrelid = c.oid
WHERE c.relnamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public');
EOF

# Apply schema
echo "Executing migrations..."
if command -v psql >/dev/null 2>&1; then
  psql "$DATABASE_URL" -f "$SQL_FILE" 2>&1 | grep -E "(CREATE|ALTER|NOTICE|category|count)" || true
  RESULT=$?
else
  # Fallback: Use Python + psycopg2
  echo "Using Python fallback for migrations..."
  python3 -c "
import os
import psycopg2
from psycopg2.extras import RealDictCursor

with open('$SQL_FILE', 'r') as f:
    sql = f.read()

try:
    conn = psycopg2.connect('$DATABASE_URL')
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(sql)
    conn.commit()
    print('✅ Schema applied successfully')
    
    # Get counts
    cur.execute(\"\"\"
        SELECT COUNT(*) as tables FROM information_schema.tables 
        WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
    \"\"\")
    tables = cur.fetchone()['tables']
    
    cur.execute(\"\"\"
        SELECT COUNT(*) as indexes FROM pg_indexes WHERE schemaname = 'public'
    \"\"\")
    indexes = cur.fetchone()['indexes']
    
    print(f'  Tables: {tables}')
    print(f'  Indexes: {indexes}')
    
    conn.close()
except Exception as e:
    print(f'❌ Migration failed: {e}')
    exit(1)
" || RESULT=1
fi

# Clean up
rm -f "$SQL_FILE"

if [[ ${RESULT:-0} -eq 0 ]]; then
  echo ""
  echo "========================================="
  echo "✅ Database schema applied successfully!"
  echo "========================================="
else
  echo ""
  echo "❌ Schema application failed"
  exit 1
fi