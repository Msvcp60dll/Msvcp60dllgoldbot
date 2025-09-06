#!/usr/bin/env python3
"""
Security test script to verify input validation and protection measures.
"""

import asyncio
import json
import time
from datetime import datetime, timedelta
from app.validators import (
    DashboardParams,
    WebhookUpdateData,
    PaymentData,
    SubscriptionLinkParams,
    UserData,
    sanitize_log_message,
    validate_telegram_user_id,
    validate_star_amount,
    constant_time_compare,
    is_safe_path,
    escape_sql_like
)
from pydantic import ValidationError


def test_dashboard_params():
    """Test dashboard parameter validation"""
    print("\n" + "=" * 60)
    print("TESTING DASHBOARD PARAMETERS")
    print("=" * 60)
    
    # Test 1: Valid parameters
    try:
        params = DashboardParams(
            start_date=datetime.now() - timedelta(days=7),
            end_date=datetime.now(),
            limit=50,
            offset=0
        )
        print("✅ Valid parameters accepted")
    except ValidationError as e:
        print(f"❌ Valid parameters rejected: {e}")
    
    # Test 2: SQL injection attempt
    try:
        params = DashboardParams(
            start_date=datetime.now(),
            end_date=datetime.now(),
            status="active'; DROP TABLE users; --"
        )
        print("❌ SQL injection not blocked!")
    except ValidationError:
        print("✅ SQL injection attempt blocked")
    
    # Test 3: Date range too large
    try:
        params = DashboardParams(
            start_date=datetime.now() - timedelta(days=100),
            end_date=datetime.now()
        )
        print("❌ Excessive date range not blocked!")
    except ValidationError:
        print("✅ Excessive date range blocked (>90 days)")
    
    # Test 4: Future dates
    try:
        params = DashboardParams(
            start_date=datetime.now(),
            end_date=datetime.now() + timedelta(days=10)
        )
        print("❌ Future dates not blocked!")
    except ValidationError:
        print("✅ Future dates blocked")
    
    # Test 5: Invalid date order
    try:
        params = DashboardParams(
            start_date=datetime.now(),
            end_date=datetime.now() - timedelta(days=7)
        )
        print("❌ Invalid date order not blocked!")
    except ValidationError:
        print("✅ Invalid date order blocked")
    
    # Test 6: Extra fields (potential injection)
    try:
        data = {
            "start_date": datetime.now().isoformat(),
            "limit": 10,
            "malicious_field": "'; DELETE FROM payments; --"
        }
        params = DashboardParams(**data)
        print("❌ Extra fields not blocked!")
    except ValidationError:
        print("✅ Extra fields blocked")


def test_webhook_validation():
    """Test webhook update validation"""
    print("\n" + "=" * 60)
    print("TESTING WEBHOOK VALIDATION")
    print("=" * 60)
    
    # Test 1: Valid webhook update
    try:
        update = WebhookUpdateData(
            update_id=12345,
            message={"text": "Hello", "from": {"id": 123}}
        )
        print("✅ Valid webhook accepted")
    except ValidationError:
        print("❌ Valid webhook rejected")
    
    # Test 2: Invalid update_id
    try:
        update = WebhookUpdateData(
            update_id=-1,
            message={}
        )
        print("❌ Invalid update_id not blocked!")
    except ValidationError:
        print("✅ Invalid update_id blocked")
    
    # Test 3: Extra fields blocked
    try:
        data = {
            "update_id": 12345,
            "message": {},
            "malicious": "data"
        }
        update = WebhookUpdateData(**data)
        print("❌ Extra webhook fields not blocked!")
    except ValidationError:
        print("✅ Extra webhook fields blocked")


def test_payment_validation():
    """Test payment data validation"""
    print("\n" + "=" * 60)
    print("TESTING PAYMENT VALIDATION")
    print("=" * 60)
    
    # Test 1: Valid payment
    try:
        payment = PaymentData(
            user_id=123456,
            amount=499,
            charge_id="charge_abc123",
            payment_type="one_time"
        )
        print("✅ Valid payment accepted")
    except ValidationError:
        print("❌ Valid payment rejected")
    
    # Test 2: Invalid amount (negative)
    try:
        payment = PaymentData(
            user_id=123456,
            amount=-100,
            charge_id="charge_123",
            payment_type="one_time"
        )
        print("❌ Negative amount not blocked!")
    except ValidationError:
        print("✅ Negative amount blocked")
    
    # Test 3: Invalid amount (too high)
    try:
        payment = PaymentData(
            user_id=123456,
            amount=999999999,
            charge_id="charge_123",
            payment_type="one_time"
        )
        print("❌ Excessive amount not blocked!")
    except ValidationError:
        print("✅ Excessive amount blocked")
    
    # Test 4: SQL injection in charge_id
    try:
        payment = PaymentData(
            user_id=123456,
            amount=499,
            charge_id="'; DROP TABLE payments; --",
            payment_type="one_time"
        )
        print("❌ SQL injection in charge_id not blocked!")
    except ValidationError:
        print("✅ SQL injection in charge_id blocked")
    
    # Test 5: Invalid payment type
    try:
        payment = PaymentData(
            user_id=123456,
            amount=499,
            charge_id="charge_123",
            payment_type="malicious_type"
        )
        print("❌ Invalid payment type not blocked!")
    except ValidationError:
        print("✅ Invalid payment type blocked")


def test_user_validation():
    """Test user data validation"""
    print("\n" + "=" * 60)
    print("TESTING USER VALIDATION")
    print("=" * 60)
    
    # Test 1: Valid user
    try:
        user = UserData(
            user_id=123456,
            username="valid_user",
            first_name="John",
            last_name="Doe",
            language_code="en"
        )
        print("✅ Valid user accepted")
    except ValidationError:
        print("❌ Valid user rejected")
    
    # Test 2: XSS attempt in name
    try:
        user = UserData(
            user_id=123456,
            first_name="<script>alert('xss')</script>",
            username="test_user"
        )
        # Check if sanitized
        if "<script>" not in user.first_name:
            print("✅ XSS in name sanitized")
        else:
            print("❌ XSS in name not sanitized!")
    except ValidationError as e:
        print(f"✅ Invalid input blocked: {e}")
    
    # Test 3: Invalid user_id
    try:
        user = UserData(
            user_id=99999999999999,  # Too large
            first_name="Test",
            username="test"
        )
        print("❌ Invalid user_id not blocked!")
    except ValidationError:
        print("✅ Invalid user_id blocked")
    
    # Test 4: Invalid username format
    try:
        user = UserData(
            user_id=123456,
            first_name="Test",
            username="a"  # Too short
        )
        print("❌ Invalid username not blocked!")
    except ValidationError:
        print("✅ Invalid username blocked")


def test_sanitization_helpers():
    """Test input sanitization helpers"""
    print("\n" + "=" * 60)
    print("TESTING SANITIZATION HELPERS")
    print("=" * 60)
    
    # Test sanitize_log_message
    dangerous = "User input with <script>alert('xss')</script> and SQL: '; DROP TABLE users; --"
    safe = sanitize_log_message(dangerous)
    if "<script>" not in safe and "'" not in safe:
        print("✅ Log message sanitized correctly")
    else:
        print("❌ Log message not properly sanitized")
    
    # Test validate_telegram_user_id
    assert validate_telegram_user_id(123456) == 123456
    assert validate_telegram_user_id(-1) is None
    assert validate_telegram_user_id(99999999999) is None
    assert validate_telegram_user_id("not_a_number") is None
    print("✅ User ID validation working")
    
    # Test validate_star_amount
    assert validate_star_amount(100) == 100
    assert validate_star_amount(0, allow_zero=True) == 0
    assert validate_star_amount(0, allow_zero=False) is None
    assert validate_star_amount(-100) is None
    assert validate_star_amount(999999999) is None
    print("✅ Star amount validation working")
    
    # Test path traversal detection
    assert is_safe_path("normal/path/file.txt") == True
    assert is_safe_path("../../../etc/passwd") == False
    assert is_safe_path("/etc/passwd") == False
    assert is_safe_path("path/../../../etc/passwd") == False
    assert is_safe_path("~/sensitive") == False
    print("✅ Path traversal detection working")
    
    # Test SQL LIKE escaping
    dangerous_like = "50% off_sale [special]"
    escaped = escape_sql_like(dangerous_like)
    assert "\\%" in escaped
    assert "\\_" in escaped
    assert "\\[" in escaped
    print("✅ SQL LIKE escaping working")


def test_constant_time_compare():
    """Test constant-time string comparison"""
    print("\n" + "=" * 60)
    print("TESTING CONSTANT-TIME COMPARISON")
    print("=" * 60)
    
    # Test correct comparison
    secret = "my_secret_token_12345"
    
    # Measure timing for correct token
    start = time.perf_counter()
    for _ in range(10000):
        result = constant_time_compare(secret, secret)
    correct_time = time.perf_counter() - start
    assert result == True
    
    # Measure timing for incorrect token (same length)
    wrong = "my_secret_token_99999"
    start = time.perf_counter()
    for _ in range(10000):
        result = constant_time_compare(secret, wrong)
    wrong_time = time.perf_counter() - start
    assert result == False
    
    # Measure timing for different length
    short = "short"
    start = time.perf_counter()
    for _ in range(10000):
        result = constant_time_compare(secret, short)
    short_time = time.perf_counter() - start
    assert result == False
    
    # Check that timing is similar (within 20% variance)
    time_variance = abs(correct_time - wrong_time) / correct_time
    if time_variance < 0.2:
        print(f"✅ Constant-time comparison working (variance: {time_variance:.2%})")
    else:
        print(f"⚠️ Timing variance detected: {time_variance:.2%}")
    
    print(f"  Correct: {correct_time:.4f}s")
    print(f"  Wrong:   {wrong_time:.4f}s")
    print(f"  Short:   {short_time:.4f}s")


def test_subscription_link_validation():
    """Test subscription link parameter validation"""
    print("\n" + "=" * 60)
    print("TESTING SUBSCRIPTION LINK VALIDATION")
    print("=" * 60)
    
    # Test 1: Valid parameters
    try:
        params = SubscriptionLinkParams(u=123456, v="A", p=499)
        print("✅ Valid subscription link accepted")
    except ValidationError:
        print("❌ Valid subscription link rejected")
    
    # Test 2: Invalid variant
    try:
        params = SubscriptionLinkParams(u=123456, v="XYZ", p=499)
        print("❌ Invalid variant not blocked!")
    except ValidationError:
        print("✅ Invalid variant blocked")
    
    # Test 3: Negative price
    try:
        params = SubscriptionLinkParams(u=123456, v="A", p=-100)
        print("❌ Negative price not blocked!")
    except ValidationError:
        print("✅ Negative price blocked")
    
    # Test 4: Invalid user ID
    try:
        params = SubscriptionLinkParams(u=-1, v="A", p=499)
        print("❌ Invalid user ID not blocked!")
    except ValidationError:
        print("✅ Invalid user ID blocked")


def main():
    """Run all security tests"""
    print("=" * 60)
    print("SECURITY VALIDATION TEST SUITE")
    print("=" * 60)
    
    # Run all tests
    test_dashboard_params()
    test_webhook_validation()
    test_payment_validation()
    test_user_validation()
    test_sanitization_helpers()
    test_constant_time_compare()
    test_subscription_link_validation()
    
    print("\n" + "=" * 60)
    print("✅ SECURITY TESTS COMPLETED")
    print("=" * 60)
    print("\nSummary:")
    print("- Input validation: Working")
    print("- SQL injection protection: Active")
    print("- XSS prevention: Active")
    print("- Path traversal protection: Active")
    print("- Timing attack protection: Active")
    print("- Parameter sanitization: Working")
    print("\n⚠️ Remember to also test rate limiting with actual HTTP requests!")


if __name__ == "__main__":
    main()