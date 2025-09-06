#!/usr/bin/env python3
"""
Test script to demonstrate structured logging output
"""

import asyncio
import json
import os
import time
from datetime import datetime, timezone

# Set different log formats for testing
os.environ['LOG_FORMAT'] = os.getenv('LOG_FORMAT', 'console')  # or 'json'
os.environ['LOG_LEVEL'] = os.getenv('LOG_LEVEL', 'DEBUG')

from app.logging_config import (
    get_logger,
    set_correlation_id,
    set_user_id,
    log_performance,
    log_business_event,
    log_error,
    BusinessEvents
)

logger = get_logger(__name__)


@log_performance("database.query")
async def simulate_database_query():
    """Simulate a database query"""
    await asyncio.sleep(0.15)  # Simulate 150ms query (triggers slow query warning)
    return {"user_id": 12345, "status": "active"}


@log_performance("api.call")
async def simulate_api_call():
    """Simulate a Telegram API call"""
    await asyncio.sleep(0.05)  # Simulate 50ms API call
    return {"ok": True}


async def simulate_payment_flow():
    """Simulate a complete payment flow"""
    # Set correlation ID for this flow
    correlation_id = "payment-test-001"
    set_correlation_id(correlation_id)
    
    user_id = 12345
    set_user_id(user_id)
    
    logger.info("=" * 60)
    logger.info("Starting payment flow simulation")
    logger.info(f"Correlation ID: {correlation_id}")
    logger.info(f"User ID: {user_id}")
    logger.info("=" * 60)
    
    # 1. Payment initiated
    log_business_event(
        BusinessEvents.PAYMENT_INITIATED,
        user_id=user_id,
        amount=499,
        currency="XTR"
    )
    
    # 2. Simulate database operations
    logger.info("Checking user subscription status...")
    try:
        user_data = await simulate_database_query()
        logger.debug(
            "user.data_retrieved",
            user_data=user_data
        )
    except Exception as e:
        log_error("database.query_failed", exception=e)
    
    # 3. Process payment
    charge_id = "test_charge_123"
    logger.info(
        "payment.processing",
        charge_id=charge_id,
        amount=499
    )
    
    # Simulate some processing time
    await asyncio.sleep(0.1)
    
    # 4. Payment processed successfully
    log_business_event(
        BusinessEvents.PAYMENT_PROCESSED,
        user_id=user_id,
        charge_id=charge_id,
        amount=499,
        payment_type="one_time"
    )
    
    # 5. Create subscription
    log_business_event(
        BusinessEvents.SUBSCRIPTION_CREATED,
        user_id=user_id,
        expires_at=datetime.now(timezone.utc).isoformat(),
        is_recurring=False
    )
    
    # 6. Approve join request
    logger.info("Approving join request...")
    api_result = await simulate_api_call()
    
    log_business_event(
        BusinessEvents.JOIN_REQUEST_APPROVED,
        user_id=user_id,
        api_result=api_result
    )
    
    logger.info("Payment flow completed successfully")


async def simulate_grace_period_flow():
    """Simulate grace period transitions"""
    correlation_id = "grace-test-001"
    set_correlation_id(correlation_id)
    
    user_id = 67890
    set_user_id(user_id)
    
    logger.info("\n" + "=" * 60)
    logger.info("Starting grace period flow simulation")
    logger.info("=" * 60)
    
    # 1. Start grace period
    log_business_event(
        BusinessEvents.GRACE_PERIOD_STARTED,
        user_id=user_id,
        expires_at=datetime.now(timezone.utc).isoformat(),
        grace_hours=48
    )
    
    # 2. Send reminder
    log_business_event(
        BusinessEvents.GRACE_PERIOD_REMINDER,
        user_id=user_id,
        hours_remaining=24
    )
    
    # 3. Grace period ends
    log_business_event(
        BusinessEvents.GRACE_PERIOD_ENDED,
        user_id=user_id
    )
    
    # 4. Subscription expires
    log_business_event(
        BusinessEvents.SUBSCRIPTION_EXPIRED,
        user_id=user_id,
        was_banned=True
    )
    
    logger.info("Grace period flow completed")


async def simulate_error_flow():
    """Simulate error handling"""
    correlation_id = "error-test-001"
    set_correlation_id(correlation_id)
    
    user_id = 99999
    set_user_id(user_id)
    
    logger.info("\n" + "=" * 60)
    logger.info("Starting error flow simulation")
    logger.info("=" * 60)
    
    try:
        # Simulate a payment that fails
        log_business_event(
            BusinessEvents.PAYMENT_INITIATED,
            user_id=user_id,
            amount=449
        )
        
        # Simulate an error
        raise ValueError("Simulated payment processing error")
        
    except Exception as e:
        log_error(
            BusinessEvents.PAYMENT_FAILED,
            exception=e,
            user_id=user_id,
            amount=449,
            charge_id="failed_charge_456"
        )
        
        logger.error(
            "payment.recovery_attempted",
            user_id=user_id,
            strategy="queue_for_manual_review"
        )
    
    logger.info("Error flow simulation completed")


def demonstrate_log_formats():
    """Show different log format outputs"""
    print("\n" + "=" * 60)
    print("STRUCTURED LOGGING DEMONSTRATION")
    print("=" * 60)
    
    current_format = os.getenv('LOG_FORMAT', 'console')
    print(f"\nCurrent log format: {current_format}")
    print("To see JSON format, run: LOG_FORMAT=json python test_logging.py")
    print("To see console format, run: LOG_FORMAT=console python test_logging.py")
    print("\n" + "=" * 60 + "\n")


async def main():
    """Run all simulations"""
    demonstrate_log_formats()
    
    # Run simulations
    await simulate_payment_flow()
    await simulate_grace_period_flow()
    await simulate_error_flow()
    
    # Show sample JSON output if in console mode
    if os.getenv('LOG_FORMAT') != 'json':
        print("\n" + "=" * 60)
        print("SAMPLE JSON OUTPUT")
        print("=" * 60)
        print("\nExample of what the logs look like in JSON format:")
        
        sample_log = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": "INFO",
            "logger": "app.routers.payments",
            "event": "payment.processed",
            "correlation_id": "webhook-1234567890-abcd1234",
            "user_id": 12345,
            "charge_id": "charge_abc123",
            "amount": 499,
            "payment_type": "subscription",
            "duration_ms": 234,
            "environment": "production"
        }
        
        print(json.dumps(sample_log, indent=2))
        
        print("\nThis JSON format is ideal for:")
        print("- Log aggregation systems (ELK, Datadog, CloudWatch)")
        print("- Searching and filtering by any field")
        print("- Creating dashboards and alerts")
        print("- Debugging production issues with correlation IDs")
    
    print("\n" + "=" * 60)
    print("DEMONSTRATION COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())