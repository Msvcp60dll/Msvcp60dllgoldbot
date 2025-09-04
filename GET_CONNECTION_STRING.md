# 🔴 IMPORTANT: Get Your Connection String from Supabase

## Quick Steps to Get the Correct Connection String:

1. **Go to your Supabase Dashboard**
   👉 https://app.supabase.com/project/cudmllwhxpamaiqxohse/settings/database

2. **Click on "Connection string" section**
   - You'll see several tabs: URI, PSQL, etc.

3. **Copy the URI** (it should look like one of these):
   ```
   Direct connection:
   postgresql://postgres:[YOUR-PASSWORD]@db.cudmllwhxpamaiqxohse.supabase.co:5432/postgres
   
   OR
   
   Pooler connection:
   postgresql://postgres.cudmllwhxpamaiqxohse:[YOUR-PASSWORD]@aws-0-[REGION].pooler.supabase.com:5432/postgres
   ```

4. **Replace [YOUR-PASSWORD]** with: `Msvcp60.dll173323519`

## Alternative: Check Connection Pooler Settings

1. Go to: https://app.supabase.com/project/cudmllwhxpamaiqxohse/settings/database
2. Look for **"Connection Pooling"** section
3. Toggle "Connection pooling enabled" if it's off
4. Copy the **"Connection string"** shown there
5. Note the **region** (e.g., us-west-1, us-east-1, etc.)

## Test Your Connection String

Once you have the correct string, test it:

```bash
source venv/bin/activate
python -c "
import asyncio
import asyncpg

url = 'PASTE_YOUR_CONNECTION_STRING_HERE'
asyncio.run(asyncpg.connect(url))
print('✅ Connection successful!')
"
```

## Common Connection Strings to Try:

Based on your project, try these (replace PASSWORD with Msvcp60.dll173323519):

1. **Direct (if pooling is disabled):**
   ```
   postgresql://postgres:PASSWORD@db.cudmllwhxpamaiqxohse.supabase.co:5432/postgres
   ```

2. **Pooler US-West-2:**
   ```
   postgresql://postgres.cudmllwhxpamaiqxohse:PASSWORD@aws-0-us-west-2.pooler.supabase.com:5432/postgres
   ```

3. **Pooler US-East-2:**
   ```
   postgresql://postgres.cudmllwhxpamaiqxohse:PASSWORD@aws-0-us-east-2.pooler.supabase.com:5432/postgres
   ```

## What We Need:

Please go to your Supabase dashboard and copy the EXACT connection string shown there. The region part is critical - we've tried common regions but your project might be in a different one.

---
**Note**: The connection string format depends on:
- Whether connection pooling is enabled
- Which region your Supabase project is in
- Whether you're using direct or pooler connection