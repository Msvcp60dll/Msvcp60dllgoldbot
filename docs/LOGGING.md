# Structured Logging Guide

The Telegram Stars subscription bot uses structured logging with correlation IDs for production debugging and monitoring.

## Features

### 🔍 Correlation IDs
Every request gets a unique correlation ID that flows through the entire processing chain:
- Webhook receives update → correlation ID created
- Payment processed → same correlation ID
- Database operations → same correlation ID
- Background tasks → same correlation ID

This allows tracing a single user action across all logs.

### 📊 Business Events
Key business events are logged with consistent structure:
```python
log_business_event(
    BusinessEvents.PAYMENT_PROCESSED,
    user_id=user_id,
    charge_id=charge_id,
    amount=amount,
    duration_ms=duration_ms
)
```

### ⚡ Performance Monitoring
- Database queries over 100ms are logged as warnings
- Telegram API call latencies are tracked
- Webhook processing time is measured
- Background job durations are recorded

### 🎯 Structured Fields
Every log entry includes:
- `timestamp` - ISO format timestamp
- `level` - DEBUG, INFO, WARNING, ERROR
- `correlation_id` - Request tracking ID
- `user_id` - When available
- `environment` - development/staging/production
- `duration_ms` - For performance metrics

## Configuration

### Environment Variables

```bash
# Log level: DEBUG, INFO, WARNING, ERROR
LOG_LEVEL=INFO

# Log format: console (human-readable) or json (structured)
LOG_FORMAT=json

# Optional log file path
LOG_FILE=/var/log/telegram-bot.log

# Environment name
ENVIRONMENT=production
```

### Console Format (Development)
Human-readable colored output:
```
2025-01-05 12:00:00 [INFO] payment.processed | correlation_id=abc123 user_id=12345 amount=499 duration_ms=234
```

### JSON Format (Production)
Machine-parseable structured logs:
```json
{
  "timestamp": "2025-01-05T12:00:00Z",
  "level": "INFO",
  "event": "payment.processed",
  "correlation_id": "abc123",
  "user_id": 12345,
  "amount": 499,
  "duration_ms": 234,
  "environment": "production"
}
```

## Business Events

### Payment Flow
- `payment.initiated` - Payment started
- `payment.processed` - Payment successful
- `payment.failed` - Payment failed
- `payment.duplicate` - Duplicate payment detected

### Subscription Lifecycle
- `subscription.created` - New subscription
- `subscription.renewed` - Subscription renewed
- `subscription.expired` - Subscription expired
- `subscription.cancelled` - User cancelled

### Grace Period
- `grace_period.started` - Grace period began
- `grace_period.ended` - Grace period expired
- `grace_period.reminder` - Reminder sent

### Join Requests
- `join_request.received` - User requested to join
- `join_request.approved` - Request approved
- `join_request.auto_approved` - Auto-approved (has access)
- `join_request.rejected` - Request rejected

### Reconciliation
- `reconciliation.started` - Reconciliation job started
- `reconciliation.completed` - Job completed
- `reconciliation.payment_found` - Unrecorded payment found

## Usage Examples

### Basic Logging
```python
from app.logging_config import get_logger

logger = get_logger(__name__)

logger.info("user.action", user_id=123, action="subscribe")
logger.warning("api.slow_response", duration_ms=500, endpoint="/webhook")
logger.error("payment.failed", user_id=456, error="insufficient_funds")
```

### With Correlation ID
```python
from app.logging_config import set_correlation_id, set_user_id

# Set for current context
set_correlation_id("req-123")
set_user_id(789)

# All subsequent logs will include these
logger.info("processing.started")  # Will include correlation_id and user_id
```

### Performance Tracking
```python
from app.logging_config import log_performance

@log_performance("database.query")
async def get_user(user_id: int):
    # If this takes >100ms, warning logged automatically
    return await db.fetch("SELECT * FROM users WHERE id = $1", user_id)
```

### Business Events
```python
from app.logging_config import log_business_event, BusinessEvents

# Log standardized business events
log_business_event(
    BusinessEvents.PAYMENT_PROCESSED,
    user_id=user_id,
    charge_id=charge_id,
    amount=amount,
    payment_type="subscription"
)
```

### Error Handling
```python
from app.logging_config import log_error

try:
    await process_payment()
except Exception as e:
    log_error(
        "payment.processing_error",
        exception=e,
        user_id=user_id,
        charge_id=charge_id
    )
```

## Debugging Production Issues

### Finding a Specific Payment
```bash
# Search by correlation ID (traces entire flow)
grep "correlation_id=webhook-12345" /var/log/bot.log

# Search by charge ID
grep "charge_id=charge_abc123" /var/log/bot.log

# Search by user ID
grep "user_id=789" /var/log/bot.log
```

### Tracking Slow Queries
```bash
# Find all slow database queries
grep "database.slow_query" /var/log/bot.log | jq '.duration_ms'

# Find queries over 500ms
jq 'select(.event == "database.slow_query" and .duration_ms > 500)' /var/log/bot.log
```

### Payment Flow Analysis
```bash
# Track a payment from start to finish
correlation_id="webhook-1234567890-abcd"
grep "$correlation_id" /var/log/bot.log | jq '{time: .timestamp, event: .event}'
```

### Error Analysis
```bash
# Count errors by type
jq 'select(.level == "ERROR") | .event' /var/log/bot.log | sort | uniq -c

# Find all payment failures
jq 'select(.event == "payment.failed")' /var/log/bot.log
```

## Monitoring & Alerting

### Key Metrics to Monitor

1. **Payment Success Rate**
   - Alert if `payment.failed` / `payment.processed` > 5%

2. **Slow Queries**
   - Alert if `database.slow_query` count > 10/minute

3. **Grace Period Transitions**
   - Monitor `grace_period.started` vs `subscription.renewed`

4. **API Errors**
   - Alert on `telegram.rate_limit` or `telegram.api_error`

5. **Reconciliation Issues**
   - Alert if `reconciliation.payment_found` > 0 (missing payments)

### Sample CloudWatch Query
```
fields @timestamp, correlation_id, user_id, event, duration_ms
| filter event = "payment.processed"
| stats avg(duration_ms) as avg_duration,
        max(duration_ms) as max_duration,
        count() as total_payments
by bin(5m)
```

### Sample Datadog Query
```
service:telegram-bot event:payment.* | timechart count by event
```

## Testing

### Test Logging Output
```bash
# Test console format
LOG_FORMAT=console python test_logging.py

# Test JSON format
LOG_FORMAT=json python test_logging.py

# Test with debug level
LOG_LEVEL=DEBUG LOG_FORMAT=json python test_logging.py
```

### Verify Correlation IDs
```bash
# Start the app and send a test webhook
curl -X POST http://localhost:8080/webhook/YOUR_SECRET \
  -H "Content-Type: application/json" \
  -H "X-Correlation-ID: test-correlation-123" \
  -d '{"update_id": 12345}'

# Check logs for correlation ID
grep "test-correlation-123" /var/log/bot.log
```

## Best Practices

1. **Always use structured logging** - Never use print() or basic logger
2. **Set user_id early** - Call `set_user_id()` as soon as you have it
3. **Log business events** - Use `log_business_event()` for important actions
4. **Include context** - Add relevant fields to help debugging
5. **Use appropriate levels**:
   - DEBUG: Detailed diagnostic info
   - INFO: Normal business events
   - WARNING: Slow queries, retries
   - ERROR: Failures that need attention

## Troubleshooting

### Logs not appearing
- Check `LOG_LEVEL` environment variable
- Verify file permissions if using `LOG_FILE`
- Ensure structlog is installed: `pip install structlog==24.1.0`

### JSON parsing errors
- Ensure `LOG_FORMAT=json` is set correctly
- Check for print statements (use logger instead)
- Verify all log fields are JSON-serializable

### Missing correlation IDs
- Check middleware is registered in `main.py`
- Verify `set_correlation_id()` is called early
- For background tasks, manually set correlation ID

### Performance overhead
- Structured logging adds ~1-2ms overhead
- Use `LOG_LEVEL=WARNING` in production if needed
- Consider sampling for high-volume events