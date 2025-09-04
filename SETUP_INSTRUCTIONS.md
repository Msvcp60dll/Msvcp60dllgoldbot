# 🚀 Complete Setup Instructions for Msvcp60dll Bot

## Current Status
✅ **GitHub Repository**: https://github.com/Msvcp60dll/Msvcp60dllgoldbot
✅ **Railway Project**: https://railway.com/project/71267480-b6dc-471d-ad70-88127a5ed26c
✅ **Deployment Started**: Build in progress

## 📋 STEP 1: Set Up Supabase Tables (Do This First!)

### Manual Steps Required:
1. **Open Supabase SQL Editor**: 
   https://supabase.com/dashboard/project/cudmllwhxpamaiqxohse/sql

2. **Click "New Query"**

3. **Copy the ENTIRE SQL schema from**: `app/models.sql`
   Or run this command to see it:
   ```bash
   cat app/models.sql
   ```

4. **Paste into SQL Editor and click "Run"**

5. **Verify tables were created**:
   - Go to Table Editor in Supabase
   - You should see these tables:
     - users
     - subscriptions
     - payments
     - whitelist
     - funnel_events
     - recurring_subs
     - star_tx_cursor
     - failed_payments_queue
     - notifications_queue

## 📋 STEP 2: Complete Railway Setup

### Go to Railway Dashboard:
https://railway.com/project/71267480-b6dc-471d-ad70-88127a5ed26c

### 1. Connect GitHub (if not already connected):
- Go to service Settings → Source
- Connect to: `Msvcp60dll/Msvcp60dllgoldbot`
- Set branch: `main`

### 2. Set ALL Environment Variables:
Go to Variables tab and add these (copy exactly):

```
BOT_TOKEN=8263837787:AAE_kJD3YYM5L_7Hd28uCkgvvjqxFylCIWQ
GROUP_CHAT_ID=-100238460973
OWNER_IDS=306145881
SUPABASE_URL=https://cudmllwhxpamaiqxohse.supabase.co
SUPABASE_SERVICE_KEY=sb_secret_10UN2tVL4bV5mLYVQ1z3Kg_x2s5yIr1
WEBHOOK_SECRET=railway_webhook_secret_2024
WEBHOOK_HOST=
PLAN_STARS=499
SUB_STARS=449
PLAN_DAYS=30
GRACE_HOURS=48
RECONCILE_WINDOW_DAYS=3
DAYS_BEFORE_EXPIRE=3
INVITE_TTL_MIN=5
DASHBOARD_TOKENS=dashboard_token_2024,admin_token_secure
LOG_LEVEL=INFO
TIMEZONE=UTC
PORT=8080
PYTHONUNBUFFERED=1
PYTHONDONTWRITEBYTECODE=1
```

### 3. Enable Public Networking:
- Go to Settings → Networking
- Click "Generate Domain"
- Copy the URL (e.g., `msvcp60dll-bot-production.up.railway.app`)

### 4. Update WEBHOOK_HOST:
- Go back to Variables
- Update `WEBHOOK_HOST` with your Railway URL:
  ```
  WEBHOOK_HOST=https://YOUR-DOMAIN.up.railway.app
  ```

### 5. Redeploy:
- Click "Redeploy" or push any change to GitHub

## 📋 STEP 3: Verify Everything Works

### 1. Check Health Endpoint:
```bash
curl https://YOUR-DOMAIN.up.railway.app/health
```

Should return:
```json
{
  "status": "healthy",
  "service": "msvcp60dll-bot",
  "bot": "telegram-stars-membership",
  "version": "1.3"
}
```

### 2. Check Main Endpoint:
```bash
curl https://YOUR-DOMAIN.up.railway.app/
```

### 3. Check Dashboard:
Visit: `https://YOUR-DOMAIN.up.railway.app/admin/dashboard`

Use this header for authentication:
```
Authorization: Bearer dashboard_token_2024
```

### 4. Test Bot:
1. Start chat with your bot
2. Send `/start`
3. Request to join your group: https://t.me/c/238460973
4. Bot should send you payment options

## 🔧 Troubleshooting

### If deployment fails:
1. Check Railway logs in dashboard
2. Common issues:
   - Missing environment variables
   - Database tables not created
   - Port configuration issues

### If bot doesn't respond:
1. Check webhook is set:
   - Should auto-set when WEBHOOK_HOST is configured
2. Verify bot token is correct
3. Check GROUP_CHAT_ID is correct (must be negative)

### If payments don't work:
1. Ensure Supabase tables are created
2. Check SUPABASE_SERVICE_KEY is correct
3. Verify Telegram Stars are available in your region

## 🎯 Key Features

Once running, your bot will:
- ✅ Handle join requests to your group
- ✅ Send payment offers (499 Stars one-time, 449 Stars/month)
- ✅ Auto-approve after payment
- ✅ Manage subscriptions with 48-hour grace periods
- ✅ Reconcile missed payments
- ✅ Provide `/enter` command for self-service access
- ✅ Show analytics dashboard

## 📊 Bot Commands

### User Commands:
- `/start` - Start interaction
- `/status` - Check subscription
- `/enter` - Get group access (if paid)
- `/cancel_sub` - Cancel auto-renewal
- `/help` - Get help

### Owner Commands (for user 306145881):
- `/stats` - View bot statistics

## 🔐 Important URLs

- **GitHub**: https://github.com/Msvcp60dll/Msvcp60dllgoldbot
- **Railway**: https://railway.com/project/71267480-b6dc-471d-ad70-88127a5ed26c
- **Supabase**: https://supabase.com/dashboard/project/cudmllwhxpamaiqxohse
- **Build Logs**: https://railway.com/project/71267480-b6dc-471d-ad70-88127a5ed26c/service/46867db3-6825-459a-8a86-4cf996d36e91

## ✅ Final Checklist

- [ ] Supabase tables created (Step 1)
- [ ] Railway environment variables set (Step 2.2)
- [ ] Public domain generated (Step 2.3)
- [ ] WEBHOOK_HOST updated with domain (Step 2.4)
- [ ] Health endpoint responds (Step 3.1)
- [ ] Bot responds to /start (Step 3.4)
- [ ] Join request triggers payment offer
- [ ] Dashboard accessible with Bearer token

## 💡 Next Steps

After everything is working:
1. Test a real payment flow
2. Monitor via dashboard
3. Check logs regularly: Railway dashboard → Logs
4. Set up monitoring alerts (optional)

---

**Need help?** Check the logs in Railway dashboard for detailed error messages.