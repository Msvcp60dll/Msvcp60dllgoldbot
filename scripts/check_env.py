#!/usr/bin/env python3
import os
import sys

required = [
    "BOT_TOKEN",
    "GROUP_CHAT_ID",
    "OWNER_IDS",
    "DATABASE_URL",
    "SUPABASE_URL",
    "SUPABASE_SERVICE_KEY",
    "WEBHOOK_SECRET",
]

missing = []
present = []
for var in required:
    val = os.getenv(var)
    if val:
        present.append(var)
    else:
        missing.append(var)

public_base = os.getenv("WEBHOOK_HOST") or os.getenv("PUBLIC_BASE_URL")
if not public_base:
    missing.append("WEBHOOK_HOST or PUBLIC_BASE_URL")

db_url = os.getenv("DATABASE_URL", "")
if db_url and "sslmode=require" not in db_url:
    print("ERROR: DATABASE_URL must include sslmode=require", file=sys.stderr)
    sys.exit(2)

if present:
    print("Present:", ", ".join(sorted(present)))
if missing:
    print("Missing:", ", ".join(sorted(set(missing))), file=sys.stderr)
    sys.exit(1)

print("All required environment variables are set.")
sys.exit(0)

