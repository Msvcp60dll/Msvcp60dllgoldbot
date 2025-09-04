# Telegram Stars Membership Bot v1.3

Production-ready Telegram bot for selling group access via Telegram Stars payments (one-time and recurring subscriptions).

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

1. Connect your GitHub repository to Railway
2. Set all environment variables in Railway dashboard
3. Deploy using the provided `railway.toml` configuration
4. Set webhook URL in your bot:
   - URL format: `https://your-app.railway.app/webhook/{WEBHOOK_SECRET}`

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