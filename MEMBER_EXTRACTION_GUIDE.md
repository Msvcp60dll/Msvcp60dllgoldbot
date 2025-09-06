# 🚨 CRITICAL: Extract Members BEFORE Deployment

## Why This Is Critical

**If you deploy the bot without whitelisting existing members, they will:**
- Be unable to access the group without paying
- Get kicked during grace period expiry
- Need to pay to rejoin their own group

**This script prevents that disaster!**

## Setup Instructions

### 1. Get Telegram API Credentials

1. Go to https://my.telegram.org
2. Log in with your phone number
3. Click "API development tools"
4. Create an app (any name/description)
5. Copy your:
   - **API ID** (number)
   - **API Hash** (string)

### 2. Install Requirements

```bash
pip install -r requirements_extract.txt
# or
pip install pyrogram tgcrypto
```

### 3. Configure the Script

Edit `extract_members.py` and set:
```python
API_ID = 12345678  # Your API ID
API_HASH = "your_api_hash_here"  # Your API Hash
GROUP_CHAT_ID = -100238460973  # Already set from your .env
```

### 4. Run the Extraction

```bash
python extract_members.py
```

You'll need to:
1. Enter your phone number (with country code)
2. Enter the verification code sent to Telegram
3. Confirm you want to extract members

## What the Script Does

1. **Connects to Telegram** using your account
2. **Verifies group access** and shows member count
3. **Extracts all members** excluding:
   - Deleted accounts
   - Bots (optional)
4. **Generates 3 files:**
   - `members_backup_YYYYMMDD_HHMMSS.csv` - Full backup
   - `whitelist_import_YYYYMMDD_HHMMSS.sql` - Import script
   - `admins_list_YYYYMMDD_HHMMSS.txt` - Admin reference

## Import Process

### 1. Review the SQL File

Open `whitelist_import_*.sql` and check:
- Member count looks correct
- No suspicious entries
- Admins are marked

### 2. Import to Supabase

1. Open Supabase dashboard
2. Go to SQL Editor
3. Paste the entire SQL file
4. Click "Run"
5. Verify with:
   ```sql
   SELECT COUNT(*) FROM whitelist WHERE source = 'initial_import';
   ```

### 3. Test with Your Account

```sql
-- Check if you're whitelisted
SELECT * FROM whitelist WHERE user_id = 306145881;
```

### 4. Deploy the Bot

**ONLY after whitelist is imported:**
```bash
railway up
```

## Verification After Deployment

1. **Existing members** should be able to stay in group
2. **New joins** should get payment request
3. **Whitelisted users** bypass payment

## Sample SQL Output

```sql
-- Whitelist import for existing group members
-- Generated: 2024-01-15T10:30:00
-- Group: Premium Trading Signals
-- Total members: 487

INSERT INTO whitelist (user_id, source, note, created_at)
VALUES
    (123456789, 'initial_import', 'Initial import - John (@johndoe)', NOW()),
    (987654321, 'initial_import', 'Initial import - Jane (@jane) [ADMIN]', NOW()),
    (456789123, 'initial_import', 'Initial import - Bob (@trader_bob)', NOW())
ON CONFLICT (user_id) DO NOTHING;
```

## Troubleshooting

### "FloodWait" Error
The script handles rate limits automatically. Just wait.

### "Not a member" Error
You must be in the group to extract members.

### Large Groups (1000+ members)
Extraction may take 5-10 minutes. The script shows progress every 100 members.

### Session File
After first run, a `member_extractor.session` file is created. Keep it to avoid re-authentication.

## Emergency Rollback

If you deployed without whitelisting:

1. **Quick fix** - Import whitelist immediately:
   ```sql
   -- Emergency whitelist all current members
   INSERT INTO whitelist (user_id, source, note)
   SELECT user_id, 'emergency', 'Emergency import after deployment'
   FROM users
   WHERE created_at < NOW()
   ON CONFLICT DO NOTHING;
   ```

2. **Stop the scheduler** to prevent kicks:
   - Set `SCHEDULER_ENABLED=false` in Railway
   - Redeploy

3. **Then run proper extraction** and import

## ⚠️ Final Warning

**DO NOT DEPLOY WITHOUT WHITELISTING EXISTING MEMBERS!**

This is a one-time setup that prevents a major disruption. Once done, the bot will:
- Keep all existing members free
- Charge only new joins
- Work exactly as intended

---

**Ready?** Run `python extract_members.py` now!