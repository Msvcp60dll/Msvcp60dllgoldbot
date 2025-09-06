# Database Migration System

Simple, reliable SQL migration system for the Telegram Stars subscription bot.

## Quick Start

```bash
# Run all pending migrations
python -m app.migrate

# Check migration status
python -m app.migrate status

# List all available migrations
python -m app.migrate list

# Rollback last migration (if DOWN section exists)
python -m app.migrate rollback
```

## How It Works

1. **Automatic on Startup**: Migrations run automatically when the app starts (see `main.py`)
2. **Idempotent**: Safe to run multiple times - applied migrations are tracked in `schema_migrations` table
3. **Simple SQL Files**: Plain SQL with `-- UP` and `-- DOWN` sections
4. **Numbered Order**: Files are executed in numeric order (001, 002, 003...)

## Creating New Migrations

1. Create a new SQL file with the next number:
```bash
touch app/migrations/003_your_migration_name.sql
```

2. Add UP and DOWN sections:
```sql
-- Migration: Brief description
-- Author: Your name
-- Date: YYYY-MM-DD
-- Description: What this migration does and why

-- UP
BEGIN;

-- Your forward migration SQL here
CREATE INDEX IF NOT EXISTS idx_example ON table(column);

COMMIT;

-- DOWN
BEGIN;

-- Your rollback SQL here (optional but recommended)
DROP INDEX IF EXISTS idx_example;

COMMIT;
```

## Migration Tracking

The system tracks applied migrations in the `schema_migrations` table:

```sql
CREATE TABLE schema_migrations (
    version VARCHAR(255) PRIMARY KEY,      -- e.g., "001"
    applied_at TIMESTAMPTZ NOT NULL,        -- When it was applied
    execution_time_ms INTEGER,              -- How long it took
    checksum VARCHAR(64)                    -- Hash of the UP section
);
```

## Current Migrations

### 001_add_performance_indexes.sql
**Purpose**: Add critical performance indexes for frequently queried columns

**Indexes added**:
- `idx_subscriptions_user_status` - Find active/grace subs for a user
- `idx_subscriptions_expires_at` - Process expiring subscriptions
- `idx_subscriptions_grace_until` - Process grace period expiry
- `idx_payments_created_at` - Reconciliation window queries
- `idx_payments_user_id` - User payment history
- `idx_funnel_events_created_type` - Dashboard analytics

**Impact**: Significant query performance improvement (10-100x faster for common queries)

### 002_optimize_queries.sql
**Purpose**: Additional optimization for specific query patterns

**Indexes added**:
- Dashboard summary queries
- MRR calculations
- Reconciliation lookups
- Whitelist burn rules

## Best Practices

1. **Always use IF NOT EXISTS**: Makes migrations idempotent
```sql
CREATE INDEX IF NOT EXISTS idx_name ON table(column);
```

2. **Wrap in transactions**: Use BEGIN/COMMIT for atomicity
```sql
BEGIN;
-- Your changes
COMMIT;
```

3. **Add DOWN section**: Even if just for documentation
```sql
-- DOWN
-- This migration cannot be safely rolled back
```

4. **Test locally first**: Run against a test database
```bash
DATABASE_URL=postgresql://test_db python -m app.migrate
```

5. **Keep migrations small**: One logical change per migration

6. **Document thoroughly**: Future you will thank present you

## Troubleshooting

### Migration fails to apply
- Check SQL syntax
- Ensure database user has required permissions
- Look for conflicting constraints or indexes

### App won't start after migration error
- Migrations are non-critical - app continues even if they fail
- Fix the migration file and restart
- Or manually apply the migration and record it:
```sql
INSERT INTO schema_migrations (version, applied_at, execution_time_ms, checksum)
VALUES ('001', NOW(), 100, 'manual');
```

### Need to skip a migration
- Manually insert a record into schema_migrations
- The runner will skip migrations already in the table

### Performance impact
- Migrations run during startup (before accepting requests)
- Most index creation is fast (<1 second)
- For large tables, consider running manually during maintenance

## Monitoring

Check migration status in logs:
```
2025-01-05 12:00:00 - INFO - Checking for pending database migrations...
2025-01-05 12:00:01 - INFO - Applying migration 001: 001_add_performance_indexes.sql
2025-01-05 12:00:02 - INFO - ✅ Applied migration 001 (823ms)
2025-01-05 12:00:02 - INFO - ✅ Applied 1 database migration(s)
```

Or via CLI:
```bash
$ python -m app.migrate status

============================================================
📊 Migration Status
============================================================
Total migrations:   2
Applied migrations: 1
Pending migrations: 1

Latest applied:
  Version: 001
  Applied: 2025-01-05T12:00:02
  Time:    823ms

Pending migrations:
  002: 002_optimize_queries.sql
============================================================
```