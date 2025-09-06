# WHITELIST SAFETY SYSTEM - PATCH SUMMARY

## Problem Solved
The bot lacks protection for existing group members (~1186 users). Without safeguards, enabling kick functionality would immediately remove all expired members, including long-standing community members who joined before the bot was implemented.

## Solution Implemented
A comprehensive whitelist system with multiple safety layers:
1. **Feature flags** - Global kill switch for kick functionality (defaults to OFF)
2. **Whitelist table** - Persistent protection for specific users
3. **Burn rules** - Automatic revocation on join requests or leaves
4. **Telethon seeding** - Bulk import of existing members
5. **Owner controls** - Commands for managing the system
6. **Dry-run capabilities** - Preview impact before enabling

## Architecture

```
┌─────────────────────────────────────────────┐
│           KICK DECISION FLOW                │
├─────────────────────────────────────────────┤
│                                             │
│  User Expired? ──No──> Keep in group       │
│       │                                     │
│      Yes                                    │
│       │                                     │
│  kicks_enabled? ──No──> Keep (protected)   │
│       │                                     │
│      Yes                                    │
│       │                                     │
│  Is Whitelisted? ──Yes──> Keep (protected) │
│       │                                     │
│       No                                    │
│       │                                     │
│    KICK USER                                │
└─────────────────────────────────────────────┘
```

## Files Created/Modified

### 1. `/migrations/001_feature_flags.sql`
```sql
CREATE TABLE IF NOT EXISTS feature_flags (
    key TEXT PRIMARY KEY,
    bool_value BOOLEAN NOT NULL DEFAULT FALSE
);
-- Default: kick_enabled = FALSE (safe by default)
```

### 2. `/migrations/002_whitelist.sql`
```sql
CREATE TABLE IF NOT EXISTS whitelist (
    telegram_id BIGINT PRIMARY KEY,
    granted_at TIMESTAMPTZ DEFAULT NOW(),
    revoked_at TIMESTAMPTZ,  -- NULL = active
    source TEXT DEFAULT 'manual',
    note TEXT
);
```

### 3. `/app/db.py`
Added comprehensive whitelist functions:
- `grant_whitelist()` - Add user to whitelist (idempotent)
- `revoke_whitelist()` - Remove from whitelist (burn rule)
- `is_whitelisted()` - Check protection status
- `is_kicks_enabled()` - Check feature flag
- `get_whitelist_stats()` - Analytics
- `get_expired_non_whitelisted()` - Dry-run preview

### 4. `/app/routers/commands.py`
Added owner-only commands:

**Kick Control:**
- `/kicks_off` - Disable kicks globally (default)
- `/kicks_on` - Enable kicks (requires confirmation)
- `/kicks_status` - View current state

**Whitelist Management:**
- `/wl_add <user_id> [note]` - Add user to whitelist
- `/wl_remove <user_id> [reason]` - Remove from whitelist
- `/wl_status [user_id]` - Check user's whitelist status
- `/wl_stats` - View whitelist statistics
- `/wl_report` - Comprehensive system report
- `/dryrun_expired` - Preview who would be kicked

### 5. `/scripts/seed_whitelist.py`
Telethon-based seeding script:
- Connects as user account (not bot)
- Fetches ALL group members
- Seeds whitelist in bulk
- Dry-run mode for testing
- Session persistence

## Deployment Runbook

### Phase 1: Deploy Safety Rails (COMPLETED)
```bash
# 1. Apply migrations
psql $DATABASE_URL < migrations/001_feature_flags.sql
psql $DATABASE_URL < migrations/002_whitelist.sql

# 2. Verify feature flag is OFF
psql $DATABASE_URL -c "SELECT * FROM feature_flags WHERE key='kick_enabled';"
# Should show: bool_value = false

# 3. Deploy code changes
railway up --detach
```

### Phase 2: Seed Existing Members
```bash
# 1. Install Telethon dependencies
pip install -r scripts/requirements_telethon.txt

# 2. Set environment variables
export TELETHON_API_ID="your_api_id"        # From https://my.telegram.org
export TELETHON_API_HASH="your_api_hash"
export DATABASE_URL="postgresql://..."
export GROUP_CHAT_ID="-1001234567890"

# 3. Dry-run first
python scripts/seed_whitelist.py --dry-run

# 4. If looks good, run for real
python scripts/seed_whitelist.py
# Enter phone number when prompted
# Enter verification code

# 5. Verify in bot
# Send: /wl_stats
# Should show ~1186 whitelisted users
```

### Phase 3: Test & Verify
```bash
# 1. Check who would be kicked
# Send: /dryrun_expired
# Review the list carefully

# 2. Verify whitelist coverage
# Send: /wl_report
# Check "Users at risk" count

# 3. Test with specific user
# Send: /wl_status 123456789
```

### Phase 4: Enable Kicks (DANGER)
```bash
# ONLY after verification!

# 1. Final check
# Send: /kicks_status
# Verify whitelist count matches expectations

# 2. Enable kicks
# Send: /kicks_on
# Send: /kicks_on_confirm

# 3. Monitor logs
railway logs --tail
```

## Burn Rules

The whitelist automatically revokes (burns) in these cases:

1. **User requests to join** - If whitelisted user sends join request, they're considered "new" and whitelist is burned
2. **User leaves group** - When user leaves voluntarily, whitelist is revoked
3. **Manual removal** - Owner uses `/wl_remove` command

## Safety Features

1. **Double-confirmation** for enabling kicks
2. **Dry-run commands** to preview impact
3. **Feature flag** defaults to FALSE
4. **Idempotent operations** - Safe to run multiple times
5. **Audit logging** - All actions tracked in funnel_events
6. **No auto-enable** - Kicks never turn on automatically

## Rollback Procedures

### To disable kicks immediately:
```bash
# Via bot command (fastest)
# Send: /kicks_off

# Via database (if bot is down)
psql $DATABASE_URL -c "UPDATE feature_flags SET bool_value=false WHERE key='kick_enabled';"
```

### To restore accidentally removed whitelist:
```bash
# Whitelist specific user
# Send: /wl_add 123456789 Restored after accident

# Re-run seeding (will restore all current members)
python scripts/seed_whitelist.py
```

## Monitoring

Check system health:
```bash
# Overall status
/kicks_status

# Detailed report
/wl_report

# Preview kicks
/dryrun_expired
```

Monitor logs for issues:
```bash
railway logs --tail | grep -E "(kick|whitelist|revoke)"
```

## Common Operations

### Protect specific VIP:
```
/wl_add 123456789 VIP member - never kick
```

### Check if user is protected:
```
/wl_status 123456789
```

### Remove protection:
```
/wl_remove 123456789 No longer VIP
```

### Emergency stop:
```
/kicks_off
```

## Database Queries

### Check feature flag:
```sql
SELECT * FROM feature_flags WHERE key = 'kick_enabled';
```

### View all whitelisted users:
```sql
SELECT telegram_id, source, granted_at, note 
FROM whitelist 
WHERE revoked_at IS NULL 
ORDER BY granted_at DESC;
```

### Find users at risk:
```sql
SELECT s.user_id, u.username, u.first_name
FROM subscriptions s
JOIN users u ON s.user_id = u.user_id
WHERE s.status = 'expired'
AND NOT EXISTS (
    SELECT 1 FROM whitelist w 
    WHERE w.telegram_id = s.user_id 
    AND w.revoked_at IS NULL
);
```

## Testing Checklist

- [ ] Feature flag defaults to FALSE
- [ ] /kicks_off command works
- [ ] /kicks_on requires confirmation
- [ ] /wl_add protects user
- [ ] /wl_remove revokes protection
- [ ] /dryrun_expired shows correct users
- [ ] Telethon script connects successfully
- [ ] Telethon script seeds whitelist
- [ ] /wl_stats shows correct counts
- [ ] /wl_report generates report

## Summary

The whitelist safety system provides comprehensive protection for existing group members with multiple fail-safes:

1. **Kicks disabled by default** - Must be explicitly enabled
2. **Bulk seeding via Telethon** - Protects all current members
3. **Owner-only controls** - Only trusted users can manage
4. **Dry-run capabilities** - Preview before committing
5. **Burn rules** - Automatic cleanup for leavers
6. **Audit trail** - All actions logged

**Current Status:** 
- ✅ Database migrations applied
- ✅ Safety functions implemented
- ✅ Owner commands added
- ✅ Telethon script created
- ⏳ Awaiting seeding execution
- ⏳ Kicks remain DISABLED (safe)