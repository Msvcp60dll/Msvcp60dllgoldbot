# Supabase Database Connection Guide

## Your Supabase Project Details
- **Project Name**: Msvcp60dllgoldbot
- **Project ID**: cudmllwhxpamaiqxohse
- **Project URL**: https://cudmllwhxpamaiqxohse.supabase.co
- **Publishable API Key**: sb_publishable_KAUyVYkNrayZT9y6Pmj2LQ_hkupO5GI
- **Secret API Key**: sb_secret_SIBInD2DwQYbi25ZaWdcTw_N4hrFDqS

## ⚠️ Important: Get Your Database Password

The **Service Role Key is NOT your database password**. You need to get the actual database password from Supabase dashboard.

### Steps to Get Database Password:

1. **Go to Supabase Dashboard**
   - Navigate to: https://app.supabase.com/project/cudmllwhxpamaiqxohse
   
2. **Find Database Settings**
   - Click on **Settings** (gear icon) in the left sidebar
   - Click on **Database** section

3. **Get Connection String**
   - Look for **Connection string** section
   - You'll see something like:
     ```
     URI: postgresql://postgres:[YOUR-PASSWORD]@db.cudmllwhxpamaiqxohse.supabase.co:5432/postgres
     ```
   
4. **Copy the Password**
   - The password is the part between `:` and `@` in the URI
   - It should look something like: `your-actual-database-password-here`
   
5. **Alternative: Reset Database Password**
   - If you can't find it, you can reset it:
   - Go to Settings → Database
   - Click "Reset Database Password"
   - Copy the new password immediately (it won't be shown again)

## Connection String Formats

Once you have the database password, use one of these formats:

### Direct Connection (Recommended for initial setup)
```
postgresql://postgres:[YOUR-DB-PASSWORD]@db.cudmllwhxpamaiqxohse.supabase.co:5432/postgres
```

### Pooler Connection - Session Mode
```
postgresql://postgres.cudmllwhxpamaiqxohse:[YOUR-DB-PASSWORD]@aws-0-us-west-1.pooler.supabase.com:5432/postgres
```

### Pooler Connection - Transaction Mode
```
postgresql://postgres.cudmllwhxpamaiqxohse:[YOUR-DB-PASSWORD]@aws-0-us-west-1.pooler.supabase.com:6543/postgres
```

## Update Your Configuration

1. **Update .env file**:
   ```env
   SUPABASE_DB_PASSWORD=[YOUR-DB-PASSWORD]
   ```

2. **Update app/config.py** to use the database password:
   ```python
   @property
   def database_url(self) -> str:
       project_id = "cudmllwhxpamaiqxohse"
       db_password = self.supabase_db_password  # Add this to Settings
       return f"postgresql://postgres:{db_password}@db.{project_id}.supabase.co:5432/postgres"
   ```

## Quick Test Script

After getting your database password, test it:

```bash
source venv/bin/activate
python -c "
import asyncio
import asyncpg

async def test():
    # Replace YOUR-DB-PASSWORD with actual password
    url = 'postgresql://postgres:YOUR-DB-PASSWORD@db.cudmllwhxpamaiqxohse.supabase.co:5432/postgres'
    try:
        conn = await asyncpg.connect(url)
        print('✅ Connected successfully!')
        await conn.close()
    except Exception as e:
        print(f'❌ Error: {e}')

asyncio.run(test())
"
```

## Common Issues

1. **"Tenant or user not found"** - Wrong password or using API key instead of DB password
2. **"nodename nor servname provided"** - DNS resolution issue, try direct IP
3. **"password authentication failed"** - Incorrect password

## Next Steps

1. Get the database password from Supabase dashboard
2. Update .env file with correct password
3. Test connection
4. Run database migrations
5. Deploy to Railway

---
**Note**: The Service Role Key (sb_secret_*) is for API access, not database connections. You need the actual PostgreSQL password from the Supabase dashboard.