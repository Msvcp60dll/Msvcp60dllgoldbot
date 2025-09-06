#!/usr/bin/env python3
"""FORCE webhook to have ALL required updates"""

import requests
import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("PUBLIC_BASE_URL", "https://msvcp60dllgoldbot-production.up.railway.app")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "c4f9a1e2b73d58fa0c9e4b12d7a6f3e1")

if not BOT_TOKEN:
    print("❌ BOT_TOKEN not found in environment")
    exit(1)

FULL_URL = f"{WEBHOOK_URL}/webhook/{WEBHOOK_SECRET}"

print("🚨 FORCING WEBHOOK FIX")
print("=" * 60)
print(f"Bot Token: {BOT_TOKEN[:20]}...")
print(f"Webhook URL: {FULL_URL}")

# Delete existing webhook
print("\n🗑️ Deleting existing webhook...")
response = requests.post(
    f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook"
)
print(f"Delete result: {response.json()}")

# Set new webhook with ALL updates
print("\n🔧 Setting webhook with ALL critical updates...")
response = requests.post(
    f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook",
    json={
        "url": FULL_URL,
        "allowed_updates": [
            "message",
            "callback_query",
            "chat_join_request",  # CRITICAL for join requests
            "chat_member",
            "pre_checkout_query",
            "successful_payment"  # CRITICAL for payments
        ],
        "drop_pending_updates": False,
        "secret_token": WEBHOOK_SECRET
    }
)

result = response.json()
print(f"Set webhook result: {result}")

# Verify
print("\n✅ Verifying webhook...")
response = requests.get(
    f"https://api.telegram.org/bot{BOT_TOKEN}/getWebhookInfo"
)
info = response.json().get("result", {})

print(f"URL: {info.get('url')}")
print(f"Allowed updates: {info.get('allowed_updates')}")

critical = ["chat_join_request", "successful_payment"]
missing = [u for u in critical if u not in (info.get("allowed_updates") or [])]

if missing:
    print(f"\n❌ STILL MISSING: {missing}")
else:
    print("\n✅ ALL CRITICAL UPDATES ENABLED!")
    print("   - Join requests will work")
    print("   - Payments will work")