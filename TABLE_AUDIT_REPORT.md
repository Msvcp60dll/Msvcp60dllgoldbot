# 🔍 Supabase Tables Audit Report

## Executive Summary

**Critical Issues Found:**
- ❌ **SCHEMA MISMATCH**: `whitelist` table uses different column names in schema vs actual database
- ⚠️ **UNUSED TABLE**: `failed_payment_operations` doesn't exist (correct name is `failed_payments_queue`)
- ⚠️ **MISSING USAGE**: Several tables have limited write operations

---

## Table-by-Table Audit

### 1. `users` Table
**Status:** 🟢 **GREEN - Working Correctly**
- **Purpose:** Stores Telegram user profile data
- **Read Operations:**
  - `app/db.py`: Stats queries, user lookups
  - `dashboard.py`: User counts
  - `routers/members.py`: User status checks
- **Write Operations:**
  - `app/db.py`: `upsert_user()` - INSERT with ON CONFLICT
  - `routers/members.py`: Status updates (ban/unban)
- **Issues:** None
- **Risk:** LOW

### 2. `subscriptions` Table  
**Status:** 🟢 **GREEN - Working Correctly**
- **Purpose:** Tracks payment status, expiry dates, and grace periods
- **Read Operations:**
  - `app/db.py`: `get_active_subscription()`, `has_active_access()`
  - `scheduler.py`: Grace period checks, expiry monitoring
  - `reconcile.py`: Subscription status for reconciliation
  - `dashboard_enhanced.py`: Overdue member queries
- **Write Operations:**
  - `app/db.py`: Insert new subscriptions, status updates
  - `scheduler.py`: Grace period transitions, status changes
  - `reconcile.py`: Extend expiry dates
  - `routers/commands.py`: Cancel subscriptions
- **Issues:** None - Well integrated
- **Risk:** LOW

### 3. `payments` Table
**Status:** 🟢 **GREEN - Working Correctly** 
- **Purpose:** Records all payment transactions with idempotency
- **Read Operations:**
  - `app/db.py`: Payment stats, revenue calculations
  - `dashboard_enhanced.py`: Revenue metrics
  - `retry_processor.py`: Check existing payments
- **Write Operations:**
  - `app/db.py`: `insert_payment_idempotent()` - Critical for preventing duplicates
  - `retry_processor.py`: Retry failed payments
- **Critical Features:**
  - ✅ Unique index on `charge_id` for idempotency
  - ✅ Unique index on `star_tx_id` for reconciliation
- **Issues:** None
- **Risk:** LOW

### 4. `whitelist` Table
**Status:** 🟡 **YELLOW - Schema Mismatch**
- **Purpose:** Free access list for grandfathered members
- **CRITICAL ISSUE:** Column name mismatch!
  - Schema defines: `user_id`, `whitelist_id`, `burned_at`
  - Database uses: `telegram_id`, `granted_at`, `revoked_at`
- **Read Operations:**
  - `app/db.py`: `burn_whitelist()` checks
  - `dashboard_enhanced.py`: Overdue member whitelist checks
  - `safety_verification.py`: Whitelist protection checks
- **Write Operations:**
  - `app/db.py`: Burn whitelist on use, create entries
  - `import_whitelist.py`: Bulk import
- **Issues:** 
  - ⚠️ Schema file (`models.sql`) doesn't match actual table structure
  - Code correctly uses `telegram_id` but documentation is wrong
- **Risk:** MEDIUM - Could cause confusion during migrations

### 5. `recurring_subs` Table
**Status:** 🟡 **YELLOW - Minimal Usage**
- **Purpose:** Stores subscription metadata for recurring payments
- **Read Operations:**
  - `routers/commands.py`: Check charge_id for cancellation
- **Write Operations:**
  - `app/db.py`: Insert when recurring payment starts
- **Issues:**
  - ⚠️ Very limited usage - only 2 operations in entire codebase
  - May be redundant with subscription table's `is_recurring` field
- **Risk:** LOW - Non-critical

### 6. `funnel_events` Table
**Status:** 🟢 **GREEN - Working Correctly**
- **Purpose:** Analytics and conversion tracking
- **Read Operations:**
  - `dashboard.py`: Funnel metrics, conversion rates
- **Write Operations:**
  - `app/db.py`: `log_event()` - Records all user actions
  - Test scripts: Generate test events
- **Issues:** None
- **Risk:** LOW

### 7. `star_tx_cursor` Table
**Status:** 🟡 **YELLOW - Limited Operations**
- **Purpose:** Tracks reconciliation position for Star transactions
- **Read Operations:**
  - `app/db.py`: `get_reconcile_cursor()`
- **Write Operations:**
  - `app/db.py`: `update_reconcile_cursor()`
- **Issues:**
  - ⚠️ No INSERT operation - assumes row exists
  - Could fail if table is empty
- **Risk:** MEDIUM - Reconciliation could fail on first run

### 8. `notifications_queue` Table
**Status:** 🟢 **GREEN - Working Correctly**
- **Purpose:** Queue for pending user notifications
- **Read Operations:**
  - `app/db.py`: Get pending notifications
- **Write Operations:**
  - `app/db.py`: Queue notification, mark as sent
- **Issues:** None
- **Risk:** LOW

### 9. `failed_payments_queue` Table (NOT `failed_payment_operations`)
**Status:** 🟡 **YELLOW - Limited Usage**
- **Purpose:** Store failed payments for manual review/retry
- **Read Operations:**
  - `retry_processor.py`: Get failed payments for retry
- **Write Operations:**
  - `routers/payments.py`: Log failed payment
  - `retry_processor.py`: Mark as resolved or update retry count
- **Issues:**
  - ⚠️ Documentation refers to wrong table name
- **Risk:** LOW - Backup mechanism works

---

## Critical Findings

### 🔴 HIGH PRIORITY FIXES

1. **Whitelist Schema Mismatch**
   ```sql
   -- models.sql has wrong schema
   -- Actual table uses: telegram_id, granted_at, revoked_at
   -- Schema file uses: user_id, whitelist_id, burned_at
   ```
   **Impact:** Could break migrations or new deployments
   **Fix:** Update `models.sql` to match actual schema

### 🟡 MEDIUM PRIORITY FIXES

2. **Star TX Cursor Initialization**
   ```python
   # Missing INSERT for first run
   # Could fail if table is empty
   ```
   **Fix:** Add initialization in `db.py`:
   ```python
   async def init_reconcile_cursor():
       await db.execute("""
           INSERT INTO star_tx_cursor (id, last_tx_at)
           VALUES (1, NOW())
           ON CONFLICT (id) DO NOTHING
       """)
   ```

3. **Recurring Subs Redundancy**
   - Consider merging with subscriptions table
   - Or enhance usage for better subscription tracking

---

## Risk Assessment Summary

| Table | Risk Level | Payment Impact | Action Required |
|-------|------------|----------------|-----------------|
| users | 🟢 LOW | None | None |
| subscriptions | 🟢 LOW | None | None |
| payments | 🟢 LOW | None | None |
| whitelist | 🟡 MEDIUM | Could affect access | Fix schema mismatch |
| recurring_subs | 🟢 LOW | None | Consider refactoring |
| funnel_events | 🟢 LOW | None | None |
| star_tx_cursor | 🟡 MEDIUM | Could break reconciliation | Add initialization |
| notifications_queue | 🟢 LOW | None | None |
| failed_payments_queue | 🟢 LOW | None | None |

---

## Recommendations

### Immediate Actions
1. ✅ Update `models.sql` to match actual whitelist schema
2. ✅ Add star_tx_cursor initialization on startup
3. ✅ Document correct table name (failed_payments_queue)

### Future Improvements
1. Consider consolidating recurring_subs into subscriptions table
2. Add more indexes for dashboard queries:
   ```sql
   CREATE INDEX idx_subscriptions_expires_status ON subscriptions(expires_at, status);
   CREATE INDEX idx_payments_user_created ON payments(user_id, created_at);
   ```
3. Add cleanup jobs for old funnel_events and notifications

### Database Health
- ✅ All critical payment tables have proper idempotency
- ✅ Foreign keys properly set up
- ✅ Unique constraints prevent duplicate subscriptions
- ⚠️ Some tables lack proper initialization checks

---

## Conclusion

The database is **PRODUCTION READY** with minor issues that won't affect payments. The main concerns are:
1. Schema documentation mismatch (not critical for running system)
2. Missing initialization for reconciliation cursor
3. Some redundant or underutilized tables

**Overall Risk: LOW-MEDIUM** - System will function correctly but needs cleanup for maintainability.