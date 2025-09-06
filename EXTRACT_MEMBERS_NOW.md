# 🚨 EXTRACT MEMBERS NOW - Before Deployment!

## Quick Start (2 Minutes)

### 1. Install Dependencies
```bash
pip install -r requirements_extract.txt
```

### 2. Run the Script
```bash
python extract_members.py
```

### 3. Follow the Interactive Prompts

The script will:
1. Ask you to choose an option (press `2` for auto-import)
2. Connect to Telegram (uses existing session or asks for phone)
3. If first time, enter your phone: `+447859838833`
4. Enter the code sent to Telegram
5. Shows group info and member count
6. Extracts all members with progress bar
7. Auto-imports to Supabase (reads credentials from .env)
8. Saves backup CSV regardless

## What You'll See

```
🚀 Telegram Whitelist Import
═══════════════════════════

Choose an option:
[1] Extract and save to file only
[2] Extract and import to Supabase  ← Choose this
[3] Dry run (preview only)
Choice: 2

📱 Connecting to Telegram...
✅ Logged in as: Anton (@your_username)

Group: Your Premium Group
┌──────────┬─────────────┐
│ Chat ID  │ -1002384609739 │
│ Type     │ ChatType.SUPERGROUP │
│ Members  │ 523 │
│ Your Status │ ADMINISTRATOR │
└──────────┴─────────────┘

📥 Extracting members from group -1002384609739...
Extracted 421 valid members... ████████████████ 100%

✅ Extraction complete!
   Valid members: 421
   Bots skipped: 12
   Deleted accounts skipped: 90

Checking for existing whitelist entries...
Will import 421 new members
Proceed with import? (y/n): y

Importing batch 1/5... ████████ 100%

✅ Import complete!
   Successfully imported: 421

📁 Backup saved: members_backup_20250106_143022.csv

🎉 Operation completed successfully!
```

## Features

### Automatic Features
- ✅ **Auto-detects** existing Telegram session (no re-auth needed)
- ✅ **Progress bars** for extraction and import
- ✅ **Duplicate checking** - skips already whitelisted members
- ✅ **Batch imports** - 100 members at a time for speed
- ✅ **Auto-saves backup** CSV regardless of import choice
- ✅ **Handles rate limits** automatically

### Interactive Options
1. **Extract and save** - Creates CSV + SQL files only
2. **Extract and import** - Direct to Supabase (recommended)
3. **Dry run** - Preview without saving

### Error Handling
- Network timeouts → Automatic retry
- Rate limits → Waits and continues
- Duplicate members → Skips silently
- Missing Supabase creds → Falls back to file export

## Configuration Already Set

The script has these hardcoded:
```python
API_ID = 28661564
API_HASH = "177feaf3caf64cd8d89613ce7d5d3a83"
GROUP_CHAT_ID = -1002384609739
```

Supabase credentials are read from your `.env` file:
- `SUPABASE_URL`
- `SUPABASE_SERVICE_KEY`

## After Import

1. **Verify in Supabase:**
   ```sql
   SELECT COUNT(*) FROM whitelist WHERE source = 'initial_import';
   ```

2. **Deploy the bot:**
   ```bash
   railway up
   ```

3. **Result:**
   - All current members: Free access forever
   - New members: Must pay 3800/2500 Stars

## Troubleshooting

### "Module not found"
```bash
pip install -r requirements_extract.txt
```

### "Authentication failed"
- Make sure phone number includes country code: `+447859838833`
- Check the code in Telegram app (not SMS)
- If 2FA enabled, enter your password when prompted

### "Supabase connection failed"
- Check `.env` has `SUPABASE_URL` and `SUPABASE_SERVICE_KEY`
- Script will create SQL file as fallback

### "Rate limited"
- Script handles this automatically - just wait

## Files Created

- `members_backup_YYYYMMDD_HHMMSS.csv` - Full backup (always created)
- `whitelist_import_YYYYMMDD_HHMMSS.sql` - Manual import (if Supabase fails)
- `member_extractor.session` - Telegram session (keep for next time)

## Run It Now!

```bash
python extract_members.py
```

Choose option `2` and follow the prompts. Takes ~2 minutes for 500 members.

**DO NOT DEPLOY WITHOUT RUNNING THIS FIRST!**