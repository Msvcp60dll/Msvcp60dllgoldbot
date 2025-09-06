#!/usr/bin/env python3
"""
Test script for resilience mechanisms.
Tests circuit breakers, retry logic, and health checks.
"""

import asyncio
import aiohttp
import time
import json
from datetime import datetime

# Configuration
BASE_URL = "http://localhost:8080"
ADMIN_TOKEN = "test_admin_token_123"  # Update with actual token


class ResilienceTests:
    """Test suite for resilience features"""
    
    def __init__(self):
        self.session = None
        self.results = {
            "passed": [],
            "failed": [],
            "warnings": []
        }
    
    async def setup(self):
        """Setup test environment"""
        self.session = aiohttp.ClientSession()
        print("=" * 60)
        print("RESILIENCE MECHANISMS TEST SUITE")
        print("=" * 60)
        print(f"Testing against: {BASE_URL}")
        print(f"Start time: {datetime.now()}")
        print("=" * 60)
    
    async def teardown(self):
        """Cleanup test environment"""
        if self.session:
            await self.session.close()
    
    async def test_health_endpoints(self):
        """Test all health check endpoints"""
        print("\n📊 Testing Health Check Endpoints")
        print("-" * 40)
        
        # Test liveness check
        try:
            async with self.session.get(f"{BASE_URL}/health/live") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("status") == "alive":
                        self.results["passed"].append("Liveness check")
                        print("✅ Liveness check: PASSED")
                    else:
                        self.results["failed"].append("Liveness check - wrong status")
                        print(f"❌ Liveness check: Wrong status - {data}")
                else:
                    self.results["failed"].append(f"Liveness check - HTTP {resp.status}")
                    print(f"❌ Liveness check: HTTP {resp.status}")
        except Exception as e:
            self.results["failed"].append(f"Liveness check - {str(e)}")
            print(f"❌ Liveness check failed: {e}")
        
        # Test readiness check
        try:
            async with self.session.get(f"{BASE_URL}/health/ready") as resp:
                data = await resp.json()
                if resp.status == 200:
                    self.results["passed"].append("Readiness check")
                    print(f"✅ Readiness check: PASSED - {data.get('status')}")
                elif resp.status == 503:
                    self.results["warnings"].append("Service not ready")
                    print(f"⚠️ Readiness check: Service not ready - {data}")
                else:
                    self.results["failed"].append(f"Readiness check - HTTP {resp.status}")
                    print(f"❌ Readiness check: HTTP {resp.status}")
        except Exception as e:
            self.results["failed"].append(f"Readiness check - {str(e)}")
            print(f"❌ Readiness check failed: {e}")
        
        # Test detailed health check
        try:
            async with self.session.get(f"{BASE_URL}/health/detailed") as resp:
                data = await resp.json()
                if resp.status in [200, 503]:
                    print(f"📋 Detailed health: {data.get('status')}")
                    
                    # Check components
                    components = data.get("components", [])
                    for comp in components:
                        status = comp.get("status")
                        name = comp.get("name")
                        if status == "healthy":
                            print(f"  ✅ {name}: {status}")
                        elif status == "degraded":
                            print(f"  ⚠️ {name}: {status}")
                        else:
                            print(f"  ❌ {name}: {status}")
                    
                    self.results["passed"].append("Detailed health check")
                else:
                    self.results["failed"].append(f"Detailed health - HTTP {resp.status}")
                    print(f"❌ Detailed health check: HTTP {resp.status}")
        except Exception as e:
            self.results["failed"].append(f"Detailed health - {str(e)}")
            print(f"❌ Detailed health check failed: {e}")
    
    async def test_rate_limiting(self):
        """Test rate limiting on various endpoints"""
        print("\n🚦 Testing Rate Limiting")
        print("-" * 40)
        
        # Test subscription link rate limit (10 requests per 60 seconds)
        endpoint = f"{BASE_URL}/r/sub?u=123456&v=A&p=499"
        limit = 10
        
        print(f"Testing {endpoint} (limit: {limit}/60s)")
        
        hit_limit = False
        for i in range(limit + 5):
            try:
                async with self.session.get(endpoint) as resp:
                    if resp.status == 429:
                        hit_limit = True
                        retry_after = resp.headers.get("Retry-After")
                        print(f"✅ Rate limit hit at request {i+1} (retry after: {retry_after}s)")
                        self.results["passed"].append("Rate limiting - subscription link")
                        break
                    elif resp.status in [307, 302]:
                        # Redirect is normal for this endpoint
                        continue
                    else:
                        print(f"  Request {i+1}: HTTP {resp.status}")
            except Exception as e:
                print(f"  Request {i+1} error: {e}")
        
        if not hit_limit:
            self.results["failed"].append("Rate limiting not enforced")
            print("❌ Rate limit not hit after exceeding limit")
        
        # Wait for rate limit to reset
        print("  Waiting 5 seconds for partial reset...")
        await asyncio.sleep(5)
    
    async def test_circuit_breaker_simulation(self):
        """Simulate circuit breaker behavior"""
        print("\n⚡ Testing Circuit Breaker Simulation")
        print("-" * 40)
        
        # This would need the actual bot to be running
        # We'll test by checking the health endpoint for circuit breaker status
        
        try:
            async with self.session.get(f"{BASE_URL}/health/detailed") as resp:
                if resp.status in [200, 503]:
                    data = await resp.json()
                    components = data.get("components", [])
                    
                    # Find circuit breaker component
                    cb_component = next(
                        (c for c in components if c.get("name") == "circuit_breakers"),
                        None
                    )
                    
                    if cb_component:
                        status = cb_component.get("status")
                        details = cb_component.get("details", {})
                        
                        print(f"Circuit breakers status: {status}")
                        
                        if details:
                            for name, info in details.items():
                                state = info.get("state")
                                failure_rate = info.get("failure_rate", 0)
                                print(f"  • {name}: {state} (failure rate: {failure_rate:.2%})")
                        
                        self.results["passed"].append("Circuit breaker monitoring")
                    else:
                        self.results["warnings"].append("Circuit breaker component not found")
                        print("⚠️ Circuit breaker component not found in health check")
        except Exception as e:
            self.results["failed"].append(f"Circuit breaker check - {str(e)}")
            print(f"❌ Circuit breaker check failed: {e}")
    
    async def test_timeout_protection(self):
        """Test timeout protection on endpoints"""
        print("\n⏱️ Testing Timeout Protection")
        print("-" * 40)
        
        # Test webhook endpoint with large payload
        webhook_url = f"{BASE_URL}/webhook/test_secret"
        
        # Create a large payload that might trigger timeout
        large_payload = {
            "update_id": 12345,
            "message": {
                "text": "x" * 1000000,  # 1MB of text
                "from": {"id": 123456}
            }
        }
        
        try:
            timeout = aiohttp.ClientTimeout(total=35)  # 35 seconds client timeout
            start = time.time()
            
            async with self.session.post(
                webhook_url,
                json=large_payload,
                timeout=timeout
            ) as resp:
                duration = time.time() - start
                
                if duration < 31:  # Should timeout at 30 seconds
                    print(f"✅ Request completed in {duration:.2f}s (HTTP {resp.status})")
                    self.results["passed"].append("Timeout protection")
                else:
                    print(f"⚠️ Request took {duration:.2f}s - might not have timeout protection")
                    self.results["warnings"].append("Timeout might not be enforced")
                    
        except asyncio.TimeoutError:
            duration = time.time() - start
            if duration >= 30 and duration <= 32:
                print(f"✅ Server timeout at ~30s (actual: {duration:.2f}s)")
                self.results["passed"].append("Server timeout protection")
            else:
                print(f"⚠️ Timeout at {duration:.2f}s (expected ~30s)")
                self.results["warnings"].append(f"Unexpected timeout duration: {duration:.2f}s")
        except Exception as e:
            self.results["failed"].append(f"Timeout test - {str(e)}")
            print(f"❌ Timeout test failed: {e}")
    
    async def test_graceful_degradation(self):
        """Test graceful degradation features"""
        print("\n🔄 Testing Graceful Degradation")
        print("-" * 40)
        
        # Test dashboard with authentication
        headers = {"Authorization": f"Bearer {ADMIN_TOKEN}"}
        
        try:
            async with self.session.get(
                f"{BASE_URL}/admin/api/summary",
                headers=headers
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    # Check if we get partial data even if some components fail
                    if "overview" in data:
                        print("✅ Dashboard returns data even with potential failures")
                        self.results["passed"].append("Graceful degradation - dashboard")
                    else:
                        print("⚠️ Dashboard data structure unexpected")
                        self.results["warnings"].append("Dashboard data structure")
                elif resp.status == 401:
                    print("⚠️ Dashboard requires valid token (update ADMIN_TOKEN)")
                    self.results["warnings"].append("Dashboard auth - need valid token")
                else:
                    print(f"❌ Dashboard returned HTTP {resp.status}")
                    self.results["failed"].append(f"Dashboard - HTTP {resp.status}")
        except Exception as e:
            self.results["failed"].append(f"Graceful degradation - {str(e)}")
            print(f"❌ Graceful degradation test failed: {e}")
    
    async def test_operation_queue(self):
        """Test operation queue status"""
        print("\n📦 Testing Operation Queue")
        print("-" * 40)
        
        try:
            async with self.session.get(f"{BASE_URL}/health/detailed") as resp:
                if resp.status in [200, 503]:
                    data = await resp.json()
                    components = data.get("components", [])
                    
                    # Find operation queue component
                    queue_component = next(
                        (c for c in components if c.get("name") == "operation_queue"),
                        None
                    )
                    
                    if queue_component:
                        status = queue_component.get("status")
                        details = queue_component.get("details", {})
                        queue_size = details.get("queue_size", 0)
                        processing = details.get("processing", False)
                        
                        print(f"Operation queue status: {status}")
                        print(f"  • Queue size: {queue_size}")
                        print(f"  • Processing: {processing}")
                        
                        if status == "healthy":
                            self.results["passed"].append("Operation queue healthy")
                        elif status == "degraded":
                            self.results["warnings"].append(f"Operation queue degraded - size: {queue_size}")
                        else:
                            self.results["failed"].append(f"Operation queue unhealthy - size: {queue_size}")
                    else:
                        self.results["warnings"].append("Operation queue component not found")
                        print("⚠️ Operation queue component not found")
        except Exception as e:
            self.results["failed"].append(f"Operation queue check - {str(e)}")
            print(f"❌ Operation queue check failed: {e}")
    
    def print_summary(self):
        """Print test results summary"""
        print("\n" + "=" * 60)
        print("TEST RESULTS SUMMARY")
        print("=" * 60)
        
        total = len(self.results["passed"]) + len(self.results["failed"]) + len(self.results["warnings"])
        
        print(f"\n✅ Passed: {len(self.results['passed'])}/{total}")
        for test in self.results["passed"]:
            print(f"   • {test}")
        
        if self.results["warnings"]:
            print(f"\n⚠️ Warnings: {len(self.results['warnings'])}/{total}")
            for test in self.results["warnings"]:
                print(f"   • {test}")
        
        if self.results["failed"]:
            print(f"\n❌ Failed: {len(self.results['failed'])}/{total}")
            for test in self.results["failed"]:
                print(f"   • {test}")
        
        print("\n" + "=" * 60)
        
        if not self.results["failed"]:
            print("🎉 All critical tests passed!")
        elif len(self.results["failed"]) <= 2:
            print("⚠️ Some tests failed - review and fix issues")
        else:
            print("❌ Multiple failures detected - immediate attention required")
        
        print("=" * 60)
        print(f"End time: {datetime.now()}")
    
    async def run_all_tests(self):
        """Run all resilience tests"""
        await self.setup()
        
        try:
            # Run test suite
            await self.test_health_endpoints()
            await self.test_rate_limiting()
            await self.test_circuit_breaker_simulation()
            await self.test_timeout_protection()
            await self.test_graceful_degradation()
            await self.test_operation_queue()
            
        except Exception as e:
            print(f"\n❌ Test suite error: {e}")
            self.results["failed"].append(f"Test suite error - {str(e)}")
        
        finally:
            self.print_summary()
            await self.teardown()


async def main():
    """Main test runner"""
    tests = ResilienceTests()
    await tests.run_all_tests()


if __name__ == "__main__":
    print("Starting resilience tests...")
    print(f"Make sure the application is running on {BASE_URL}")
    print("Press Ctrl+C to cancel\n")
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nTests cancelled by user")
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")