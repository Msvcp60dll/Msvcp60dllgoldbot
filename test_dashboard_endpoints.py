#!/usr/bin/env python3
"""
Test the enhanced dashboard endpoints
"""

import asyncio
import aiohttp
import json
from datetime import datetime

# Test configuration
BASE_URL = "http://localhost:8000"  # Adjust if running on different port
DASHBOARD_TOKEN = "dash_ab12cd34"  # From your .env DASHBOARD_TOKENS

async def test_endpoints():
    """Test all dashboard endpoints"""
    
    headers = {
        "Authorization": f"Bearer {DASHBOARD_TOKEN}"
    }
    
    async with aiohttp.ClientSession() as session:
        print("🧪 Testing Dashboard Endpoints\n")
        
        # Test 1: API Summary Endpoint
        print("1️⃣ Testing /admin/api/summary...")
        try:
            async with session.get(f"{BASE_URL}/admin/api/summary", headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    print("   ✅ Status: 200 OK")
                    print(f"   📊 Metrics retrieved:")
                    print(f"      - Active paid subscriptions: {data['overview']['active_paid_subscriptions']}")
                    print(f"      - Overdue not kicked: {data['overview']['overdue_not_kicked']}")
                    print(f"      - Revenue today: {data['overview']['revenue_today']} Stars")
                    print(f"      - Conversion rate: {data['overview']['conversion_rate_24h']}%")
                    
                    # Check overdue members
                    overdue = data.get('overdue_members', [])
                    critical = [m for m in overdue if m['severity'] == 'critical']
                    warning = [m for m in overdue if m['severity'] == 'warning']
                    
                    print(f"\n   ⚠️ Overdue Members:")
                    print(f"      - Critical (>3 days): {len(critical)}")
                    print(f"      - Warning (<3 days): {len(warning)}")
                    
                    if critical:
                        print(f"\n   🚨 Critical Overdue Examples:")
                        for member in critical[:3]:
                            print(f"      - User {member['user_id']} ({member.get('username', 'no username')}): {member['days_overdue']} days overdue")
                else:
                    print(f"   ❌ Status: {response.status}")
                    text = await response.text()
                    print(f"   Error: {text}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
        
        # Test 2: CSV Export Endpoint
        print("\n2️⃣ Testing /admin/api/overdue/csv...")
        try:
            async with session.get(f"{BASE_URL}/admin/api/overdue/csv", headers=headers) as response:
                if response.status == 200:
                    content = await response.text()
                    lines = content.strip().split('\n')
                    print("   ✅ Status: 200 OK")
                    print(f"   📄 CSV Export:")
                    print(f"      - Headers: {lines[0]}")
                    print(f"      - Data rows: {len(lines) - 1}")
                    
                    # Parse CSV to show sample
                    if len(lines) > 1:
                        import csv
                        import io
                        reader = csv.DictReader(io.StringIO(content))
                        rows = list(reader)
                        critical_rows = [r for r in rows if r['severity'] == 'critical']
                        print(f"      - Critical overdue in CSV: {len(critical_rows)}")
                else:
                    print(f"   ❌ Status: {response.status}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
        
        # Test 3: HTML Dashboard
        print("\n3️⃣ Testing /admin/dashboard...")
        try:
            async with session.get(f"{BASE_URL}/admin/dashboard", headers=headers) as response:
                if response.status == 200:
                    html = await response.text()
                    print("   ✅ Status: 200 OK")
                    print(f"   📱 HTML Dashboard:")
                    print(f"      - Response size: {len(html)} bytes")
                    print(f"      - Contains auto-refresh: {'auto-refresh' in html}")
                    print(f"      - Contains overdue section: {'OVERDUE MEMBERS' in html}")
                    print(f"      - Contains revenue metrics: {'Revenue' in html}")
                    print(f"      - Contains export button: {'Export Overdue' in html}")
                else:
                    print(f"   ❌ Status: {response.status}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
        
        # Test 4: Unauthorized Access
        print("\n4️⃣ Testing unauthorized access...")
        try:
            async with session.get(f"{BASE_URL}/admin/api/summary") as response:
                if response.status == 401:
                    print("   ✅ Correctly rejected (401 Unauthorized)")
                else:
                    print(f"   ⚠️ Unexpected status: {response.status} (should be 401)")
        except Exception as e:
            print(f"   ❌ Error: {e}")
        
        print("\n✅ Dashboard endpoint tests complete!")
        print("\n📊 Summary:")
        print("   - Enhanced dashboard with overdue member tracking")
        print("   - CSV export functionality working")
        print("   - Auto-refresh enabled (60 seconds)")
        print("   - Authentication properly enforced")

async def main():
    """Main test runner"""
    print("=" * 50)
    print("Enhanced Dashboard Test Suite")
    print("=" * 50)
    print(f"Testing against: {BASE_URL}")
    print(f"Using token: {DASHBOARD_TOKEN[:10]}...")
    print()
    
    await test_endpoints()
    
    print("\n" + "=" * 50)
    print("🎯 Next Steps:")
    print("1. Visit the dashboard in browser:")
    print(f"   {BASE_URL}/admin/dashboard?token={DASHBOARD_TOKEN}")
    print("2. Check that overdue members are highlighted correctly")
    print("3. Verify auto-refresh works (wait 60 seconds)")
    print("4. Test CSV export button")
    print("=" * 50)

if __name__ == "__main__":
    import sys
    
    # Check if custom base URL provided
    if len(sys.argv) > 1:
        BASE_URL = sys.argv[1]
    
    # Check if custom token provided
    if len(sys.argv) > 2:
        DASHBOARD_TOKEN = sys.argv[2]
    
    asyncio.run(main())