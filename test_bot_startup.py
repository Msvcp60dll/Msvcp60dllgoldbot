#!/usr/bin/env python3
"""Test if bot can start up without errors"""

import sys
import os

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test if all imports work"""
    print("Testing imports...")
    
    try:
        print("  Testing webhook_config...")
        from app.webhook_config import REQUIRED_WEBHOOK_UPDATES
        print(f"  ✅ webhook_config OK: {len(REQUIRED_WEBHOOK_UPDATES)} updates")
    except Exception as e:
        print(f"  ❌ webhook_config error: {e}")
        return False
    
    try:
        print("  Testing config...")
        from app.config import settings
        print(f"  ✅ config OK")
    except Exception as e:
        print(f"  ❌ config error: {e}")
        return False
    
    try:
        print("  Testing bot...")
        from app.bot import bot, dp
        print(f"  ✅ bot OK")
    except Exception as e:
        print(f"  ❌ bot error: {e}")
        return False
    
    try:
        print("  Testing routers...")
        from app.routers import join, payments, commands, members
        print(f"  ✅ routers OK")
    except Exception as e:
        print(f"  ❌ routers error: {e}")
        return False
    
    return True

if __name__ == "__main__":
    print("=" * 60)
    print("BOT STARTUP TEST")
    print("=" * 60)
    
    if test_imports():
        print("\n✅ All imports successful - bot should start")
    else:
        print("\n❌ Import errors - bot won't start")
        sys.exit(1)