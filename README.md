# Telegram Stars Membership Bot v1.3

Production-ready Telegram bot for selling group access via Telegram Stars payments (one-time and recurring subscriptions).

## 🚨 Deployment Status

✅ **READY FOR DEPLOYMENT** - All 1,198 existing members have been whitelisted!
- Existing members: Free access forever (whitelisted)  
- New members: Must pay 3,800 Stars (one-time) or 2,500 Stars/month (subscription)
- Deploy now: `railway up`

## Features

- 💎 **Telegram Stars Payments**: One-time passes and monthly subscriptions
- 🚪 **Join-by-Request Funnel**: Automatic approval after payment
- 🔄 **Idempotent Payment Processing**: Unique indexes prevent duplicate charges
- ⏰ **Grace Periods**: 48-hour grace period after subscription expiry
- 🔍 **Transaction Reconciliation**: Sliding window reconciliation for missed webhooks
- 📊 **Analytics Dashboard**: Real-time metrics with Bearer token authentication
- 🎯 **Self-Service Access**: `/enter` command for instant group access
- 🛡️ **Whitelist System**: Protect existing members from removal

## Architecture

- **Python 3.11+** with type hints
- **aiogram v3** for Telegram Bot API
- **FastAPI** for webhook handling
- **Supabase/PostgreSQL** for data persistence
- **APScheduler** for background tasks
- **Railway** deployment ready

## Quick Start

### 1. Prerequisites

- Python 3.11+
- PostgreSQL database (Supabase recommended)
- Telegram Bot Token (from @BotFather)
- Telegram Group/Supergroup with join requests enabled

### 2. Setup Database

Run the SQL schema:
```bash
psql $DATABASE_URL < app/models.sql
```

### 3. Configure Environment

Copy `.env.example` to `.env` and fill in your values:
```bash
cp .env.example .env
```

Key variables:
- `BOT_TOKEN`: Your bot token from @BotFather
- `GROUP_CHAT_ID`: Your group ID (negative number)
- `OWNER_IDS`: Comma-separated admin user IDs
- `SUPABASE_URL`: Your Supabase project URL
- `SUPABASE_SERVICE_KEY`: Service role key
- `WEBHOOK_SECRET`: Random string (16+ characters)

### 4. Install Dependencies

```bash
pip install -r requirements.txt
```

### 5. Run Locally

```bash
python main.py
```

## Deployment to Railway

### Pre-Deployment Checklist ✅

1. **Whitelist Import** (COMPLETED ✅)
   - 1,198 existing members imported to whitelist table
   - Source: `initial_import` 
   - These members have permanent free access
   
2. **Environment Variables** (Set in Railway dashboard)
   - All variables from `.env` file are configured
   - Prices set to production values (3800/2500 Stars)

3. **Deploy Command**
   ```bash
   railway up
   ```

### Deployment Steps

1. Connect your GitHub repository to Railway
2. Set all environment variables in Railway dashboard
3. Deploy using the provided `railway.toml` configuration
4. Set webhook URL in your bot:
   - URL format: `https://your-app.railway.app/webhook/{WEBHOOK_SECRET}`

### Production switch & webhook

If a domain already exists (e.g., https://msvcp60dllgoldbot-production.up.railway.app):
- Set `WEBHOOK_HOST=https://<domain>` and (for compatibility) `PUBLIC_BASE_URL=https://<domain>` in Railway Variables.
- Verify required envs: `BOT_TOKEN`, `GROUP_CHAT_ID`, `OWNER_IDS`, `DATABASE_URL` (must include `sslmode=require`), `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `WEBHOOK_SECRET`.
- Deploy with full start (`start_wrapper.py`) — health remains at `/health` and `/healthz`.
- Webhook is auto-installed on startup when public URL and secret exist. Fallback:
  ```bash
  bash scripts/set_webhook.sh
  ```

Migrations:
```bash
bash scripts/apply_schema.sh
```

Checks:
```bash
curl -sS $PUBLIC_BASE_URL/health | jq .
curl -sS $PUBLIC_BASE_URL/healthz | jq .
```

### First Deploy → Domain → Switch back (Railway)

1) First deploy to get a domain
- `railway.toml` currently uses `startCommand = "python start_wrapper_min.py"`.
- Deploy on Railway. The minimal health server will pass `/health` without any secrets set.

2) Set domain as public base URL
- In Railway Variables add `WEBHOOK_HOST=https://<your-domain>`.
- For compatibility, you may also set `PUBLIC_BASE_URL` to the same value.

3) Switch to full wrapper and redeploy
- Change `startCommand` to `python start_wrapper.py` and redeploy.
- Ensure `BOT_TOKEN`, `DATABASE_URL`, and `WEBHOOK_SECRET` are set. The app auto-sets the webhook when `WEBHOOK_HOST`/`PUBLIC_BASE_URL` exists.

4) If webhook isn’t set automatically
- The code sets it with a secret token; if needed, set manually:
  ```bash
  curl -X POST "https://api.telegram.org/bot<token>/setWebhook" \
    -H 'Content-Type: application/json' \
    -d '{"url":"https://<your-domain>/webhook/<WEBHOOK_SECRET>","secret_token":"<WEBHOOK_SECRET>"}'
  ```

## Bot Commands

### User Commands
- `/start` - Start interaction with bot
- `/status` - Check subscription status
- `/enter` - Get instant group access (if subscribed)
- `/cancel_sub` - Cancel auto-renewal
- `/help` - Get help

### Owner Commands
- `/stats` - View bot statistics (owner only)

## Payment Flow

1. User requests to join the group
2. Bot sends payment options via DM
3. User chooses one-time or subscription
4. Payment processed through Telegram Stars
5. Automatic group approval
6. Self-service `/enter` if approval fails

## Dashboard Access

Access the analytics dashboard at:
```
https://your-bot.railway.app/admin/dashboard
```

Authentication via Bearer token:
```
Authorization: Bearer your_dashboard_token
```

## Whitelist Management

### Initial Import (COMPLETED)
- **1,198 members** imported from Msvcp60dll group
- All have permanent free access (won't be kicked)
- Import timestamp: 2025-09-06 03:18:46 UTC

### Whitelist Table Structure
```sql
telegram_id  BIGINT       -- User's Telegram ID
granted_at   TIMESTAMP    -- When access was granted
revoked_at   TIMESTAMP    -- If/when access was revoked
source       TEXT         -- 'initial_import', 'owner', 'manual', etc.
note         TEXT         -- Additional notes
```

### Managing Whitelist
```python
# Check import status
python verify_import.py

# Import additional members from CSV
python import_whitelist.py

# View in Supabase dashboard
SELECT * FROM whitelist WHERE source = 'initial_import';
```

## Key Features

### Idempotency
- Unique indexes on `charge_id` and `star_tx_id`
- Prevents duplicate payment processing
- Safe webhook retries

### Grace Period
- 48-hour grace after subscription expiry
- Automatic status transitions
- Soft bans after grace expires

### Reconciliation
- Sliding window transaction sync
- Recovers missed webhook payments
- Runs every 6 hours automatically

## Security

- Webhook secret validation
- Bearer token dashboard auth
- No refunds policy (access always delivered)
- Whitelist protection for existing members

## Monitoring

Health check endpoint:
```
GET /healthz
```

Returns:
```json
{
  "status": "healthy",
  "bot": "your_bot_username",
  "database": "connected",
  "version": "1.3"
}
```

## Troubleshooting

### Bot not responding to join requests
- Check `GROUP_CHAT_ID` is correct (must be negative)
- Ensure bot is admin with "Add Users" permission
- Verify join requests are enabled in group settings

### Payments not processing
- Check webhook URL is correctly set
- Verify `WEBHOOK_SECRET` matches in bot and environment
- Check database connection and migrations

### Dashboard not loading
- Verify `DASHBOARD_TOKENS` is set
- Check Bearer token in request header
- Ensure database has read permissions

## License

Private project - All rights reserved

## Support

Contact bot owners via the configured `OWNER_IDS` for support.
