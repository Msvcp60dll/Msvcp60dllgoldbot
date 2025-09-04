# Deployment Instructions for Msvcp60dll Bot

## ✅ Completed Setup

1. **GitHub Repository Created**: https://github.com/Msvcp60dll/Msvcp60dllgoldbot
2. **Railway Project Created**: https://railway.com/project/71267480-b6dc-471d-ad70-88127a5ed26c
3. **Initial deployment started**

## 🚀 Steps to Complete Railway Deployment

### 1. Open Railway Dashboard
Go to: https://railway.com/project/71267480-b6dc-471d-ad70-88127a5ed26c

### 2. Connect GitHub Repository
1. In Railway dashboard, click on your service
2. Go to "Settings" → "Source"
3. Connect GitHub repository: `Msvcp60dll/Msvcp60dllgoldbot`
4. Set branch to `main`

### 3. Set Environment Variables
In Railway dashboard, go to "Variables" and add these:

```
BOT_TOKEN=8263837787:AAE_kJD3YYM5L_7Hd28uCkgvvjqxFylCIWQ
GROUP_CHAT_ID=-100238460973
OWNER_IDS=306145881
SUPABASE_URL=https://cudmllwhxpamaiqxohse.supabase.co
SUPABASE_SERVICE_KEY=sb_secret_10UN2tVL4bV5mLYVQ1z3Kg_x2s5yIr1
WEBHOOK_SECRET=railway_webhook_secret_2024
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
```

### 4. Enable Public Networking
1. Go to Settings → Networking
2. Click "Generate Domain"
3. Copy the generated URL (e.g., `msvcp60dll-bot-production.up.railway.app`)

### 5. Update WEBHOOK_HOST
After getting your public URL:
1. Add another environment variable:
   ```
   WEBHOOK_HOST=https://YOUR-APP.up.railway.app
   ```
2. Replace `YOUR-APP` with your actual Railway domain

### 6. Set Up Supabase Database

#### Option A: Using Supabase REST API (Recommended)
The bot is configured to work with Supabase REST API using the service key.
No additional database password needed!

1. Go to Supabase Dashboard: https://supabase.com/dashboard/project/cudmllwhxpamaiqxohse
2. Go to SQL Editor
3. Copy contents of `app/models.sql`
4. Run the SQL to create all tables

#### Option B: Direct PostgreSQL (If needed)
If you prefer direct database connection:
1. Get database password from Supabase (Settings → Database)
2. Add to Railway variables:
   ```
   DATABASE_PASSWORD=your_actual_db_password
   ```
3. Update `app/config.py` to use the password

### 7. Verify Deployment

Check deployment status:
```bash
railway logs
```

Test health endpoint:
```bash
curl https://YOUR-APP.up.railway.app/healthz
```

### 8. Set Webhook in Telegram

After deployment is running, the bot will automatically set its webhook to:
```
https://YOUR-APP.up.railway.app/webhook/railway_webhook_secret_2024
```

## 🔧 Troubleshooting

### If deployment fails:
1. Check logs: `railway logs`
2. Verify all environment variables are set
3. Ensure Supabase tables are created

### If bot doesn't respond:
1. Check webhook is set correctly
2. Verify GROUP_CHAT_ID is correct (must be negative)
3. Ensure bot is admin in the group

### Database connection issues:
The bot uses Supabase REST API by default, so no database password is needed.
Just ensure SUPABASE_SERVICE_KEY is correct.

## 📊 Monitoring

### Dashboard Access
Visit: `https://YOUR-APP.up.railway.app/admin/dashboard`

Use Bearer token authentication:
```
Authorization: Bearer dashboard_token_2024
```

### Health Check
`https://YOUR-APP.up.railway.app/healthz`

### View Logs
```bash
railway logs
```

## 🎯 Next Steps

1. Complete Railway setup (steps 1-6)
2. Create Supabase tables
3. Test bot by requesting to join your group
4. Monitor via dashboard

## 📝 Important URLs

- **GitHub**: https://github.com/Msvcp60dll/Msvcp60dllgoldbot
- **Railway Project**: https://railway.com/project/71267480-b6dc-471d-ad70-88127a5ed26c
- **Supabase**: https://supabase.com/dashboard/project/cudmllwhxpamaiqxohse
- **Telegram Group**: -100238460973

## 🔐 Credentials Summary

- **Bot Token**: 8263837787:AAE_kJD3YYM5L_7Hd28uCkgvvjqxFylCIWQ
- **Owner ID**: 306145881
- **Dashboard Token**: dashboard_token_2024
- **Webhook Secret**: railway_webhook_secret_2024