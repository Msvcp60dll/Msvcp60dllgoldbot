# Manual Test Checklist for Telegram Stars Bot

## Prerequisites
- [ ] Bot deployed to Railway
- [ ] Database connected
- [ ] Webhook configured
- [ ] Test Telegram account ready
- [ ] BOT_OWNER_ID set to receive daily stats

## Test Sequence

### 1. Whitelist Test
```sql
-- Add yourself to whitelist (run in Supabase)
INSERT INTO whitelist (user_id, source, note) 
VALUES (YOUR_USER_ID, 'manual', 'Testing');
```

- [ ] Send join request to group
- [ ] ✅ Should auto-approve WITHOUT payment request
- [ ] Check database: whitelist entry should have `burned_at` timestamp

### 2. Payment Flow Test (Non-Whitelisted)

Remove yourself from whitelist:
```sql
DELETE FROM whitelist WHERE user_id = YOUR_USER_ID;
```

- [ ] Send join request to group
- [ ] ✅ Should receive DM with payment options:
  - One-time (30 Stars) 
  - Monthly Subscription (30 Stars)
- [ ] Click "One-time" button
- [ ] ✅ Should receive invoice for 30 Stars
- [ ] Complete payment
- [ ] ✅ Should receive confirmation message
- [ ] Send `/enter` command
- [ ] ✅ Should get approved to group

### 3. Access Control Test

- [ ] Send `/status` command
- [ ] ✅ Should show active subscription with expiry date
- [ ] Send `/enter` command
- [ ] ✅ Should create invite link or approve pending request

### 4. Subscription Test

- [ ] Click subscription link from payment offer
- [ ] ✅ Should open Telegram Stars payment with 30 Stars
- [ ] Complete subscription payment
- [ ] ✅ Should show "auto-renews" in confirmation
- [ ] Send `/cancel_sub` to test cancellation
- [ ] ✅ Should cancel auto-renewal

### 5. Daily Operations

- [ ] Check Railway logs for:
  - [ ] "🚀 Bot started successfully"
  - [ ] "✅ Webhook configured"
  - [ ] "scheduler.started" with jobs list
- [ ] Wait for daily stats (9 AM UTC or manually trigger)
- [ ] ✅ Bot owner should receive stats message

### 6. Idempotency Test

- [ ] Simulate duplicate webhook (if possible)
- [ ] ✅ Should not create duplicate payment
- [ ] Check database: only one payment record

## Database Verification

Run these queries to verify state:

```sql
-- Check recent payments
SELECT user_id, amount, charge_id, created_at 
FROM payments 
ORDER BY created_at DESC 
LIMIT 5;

-- Check active subscriptions
SELECT user_id, status, expires_at, is_recurring 
FROM subscriptions 
WHERE status = 'active';

-- Check whitelist
SELECT user_id, burned_at, created_at 
FROM whitelist 
ORDER BY created_at DESC;

-- Check funnel events
SELECT user_id, event_type, created_at 
FROM funnel_events 
ORDER BY created_at DESC 
LIMIT 20;
```

## Common Issues

### Bot doesn't respond to /start
- Check BOT_TOKEN is valid
- Check webhook is configured: `/health/detailed`
- Check Railway logs for errors

### Payment doesn't work
- Ensure bot has payments enabled in @BotFather
- Check currency is "XTR" for Stars
- Verify prices in environment variables

### Join request not approved after payment
- Check `finalize_access` in logs
- Verify GROUP_ID is correct
- Check bot has admin rights in group

### Daily stats not received
- Verify BOT_OWNER_ID is set
- Check scheduler is running in logs
- Manually trigger: run `send_daily_stats()` 

## Success Criteria

✅ **Core flow works if:**
1. Whitelisted users join without payment
2. Non-whitelisted users must pay
3. Payment grants access for 30 days
4. Expired users enter grace period
5. Daily stats are sent to owner

That's it. The bot takes money and gives access. Simple.