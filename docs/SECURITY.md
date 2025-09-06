# Security Hardening Documentation

## Overview

This document describes the comprehensive security enhancements implemented in the Telegram Stars subscription bot to protect against common vulnerabilities and attacks.

## 🛡️ Security Features

### 1. Input Validation (Pydantic)

All user inputs are validated using Pydantic models before processing:

- **Dashboard Parameters**: Date ranges, limits, user IDs
- **Webhook Data**: Telegram update structure validation  
- **Payment Data**: Amounts, charge IDs, payment types
- **User Data**: IDs, usernames, names with XSS prevention

Example:
```python
class DashboardParams(BaseModel):
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    limit: conint(ge=1, le=1000) = 100
    
    @validator('end_date')
    def validate_date_range(cls, v, values):
        # Prevents excessive date ranges
        if (v - values['start_date']).days > 90:
            raise ValueError('Date range cannot exceed 90 days')
```

### 2. SQL Injection Prevention

**FIXED VULNERABILITY**: Dashboard API previously vulnerable to SQL injection through string formatting.

**Solution**: All database queries now use parameterized queries:

```python
# VULNERABLE (old):
query = f"SELECT * FROM users WHERE status = '{status}'"  # ❌ SQL injection risk!

# SECURE (new):
query = "SELECT * FROM users WHERE status = $1"  # ✅ Parameterized
await db.fetch(query, status)
```

**Protection measures**:
- Parameterized queries throughout
- Input validation before queries
- Whitelist-only column names for ORDER BY
- No dynamic SQL construction from user input

### 3. Rate Limiting

Protects against abuse and DoS attacks:

| Endpoint | Limit | Window | Key |
|----------|-------|--------|-----|
| `/r/sub` | 10 requests | 60 seconds | Per user ID |
| `/admin/api/summary` | 100 requests | 60 seconds | Per token |
| `/webhook/` | 1000 requests | 60 seconds | Global |
| Default | 60 requests | 60 seconds | Per IP |

Response on rate limit:
```http
HTTP/1.1 429 Too Many Requests
Retry-After: 45
X-RateLimit-Limit: 10
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1704123456

{
    "error": "Too Many Requests",
    "retry_after": 45
}
```

### 4. Request Security

#### Size Limits
- Webhooks: 1MB maximum
- Admin endpoints: 100KB maximum  
- Default: 10KB maximum

#### Timeout Protection
- All requests: 30-second timeout
- Prevents slowloris attacks

#### Security Headers
```http
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Referrer-Policy: strict-origin-when-cross-origin
```

### 5. Webhook Security

#### Constant-Time Comparison
Prevents timing attacks on webhook secret:

```python
def constant_time_compare(a: str, b: str) -> bool:
    if len(a) != len(b):
        return False
    
    result = 0
    for x, y in zip(a.encode(), b.encode()):
        result |= x ^ y
    
    return result == 0
```

#### Validation Pipeline
1. Check Content-Type is `application/json`
2. Verify secret token (constant time)
3. Validate JSON structure with Pydantic
4. Process only valid updates

### 6. XSS Prevention

All user-generated content is sanitized:

```python
def sanitize_text(text: str) -> str:
    # Remove control characters
    text = ''.join(char for char in text if ord(char) >= 32)
    # HTML escape
    text = html.escape(text)
    return text
```

Applied to:
- Usernames
- First/last names
- Bio text
- Any text shown in dashboard

### 7. Path Traversal Protection

File paths are validated to prevent directory traversal:

```python
def is_safe_path(path: str) -> bool:
    # Check for traversal attempts
    if '..' in path or path.startswith('/'):
        return False
    
    # Check for suspicious patterns
    dangerous = ['~/', 'etc/passwd', 'windows/system']
    for pattern in dangerous:
        if pattern in path.lower():
            return False
    
    return True
```

## 🔐 Authentication & Authorization

### Dashboard Authentication
- Bearer token authentication
- Tokens stored in environment variables
- No user IDs or sensitive data in URLs

### Webhook Authentication
- Secret token in URL path
- Additional header validation
- Constant-time comparison

## 📊 Monitoring & Alerts

### Security Events Logged
- Failed authentication attempts
- Rate limit violations
- Invalid input attempts
- SQL injection attempts
- XSS attempts
- Slow queries (potential DoS)

### Alert Thresholds
- Rate limit exceeded: >10 violations/minute
- Auth failures: >5 attempts/minute  
- Invalid webhooks: >20/minute
- Slow queries: >100ms

## 🧪 Testing

### Run Security Tests
```bash
python test_security.py
```

Tests include:
- Input validation
- SQL injection prevention
- XSS sanitization
- Path traversal detection
- Constant-time comparison
- Rate limiting

### Manual Testing

#### Test Rate Limiting
```bash
# Exceed rate limit
for i in {1..15}; do
    curl "http://localhost:8080/r/sub?u=123&v=A&p=499"
done
```

#### Test SQL Injection
```bash
# Should be blocked
curl -X GET "http://localhost:8080/admin/api/summary?status=active'; DROP TABLE users; --" \
     -H "Authorization: Bearer YOUR_TOKEN"
```

#### Test XSS
```bash
# Should be sanitized
curl -X POST "http://localhost:8080/webhook/SECRET" \
     -H "Content-Type: application/json" \
     -d '{"update_id": 123, "message": {"text": "<script>alert(1)</script>"}}'
```

## 🚨 Incident Response

### If Rate Limit is Hit
1. Check logs for source
2. Identify if legitimate or attack
3. Adjust limits if needed
4. Consider IP blocking for persistent abuse

### If SQL Injection is Attempted
1. Alert immediately (logged automatically)
2. Review all recent queries from that source
3. Check database integrity
4. Update WAF rules if pattern emerges

### If XSS is Attempted
1. Verify sanitization worked
2. Check dashboard output
3. Review user data for patterns
4. Consider user suspension

## 🔧 Configuration

### Environment Variables
```bash
# Rate limiting (optional overrides)
RATE_LIMIT_SUBSCRIPTION=10,60    # requests,seconds
RATE_LIMIT_DASHBOARD=100,60
RATE_LIMIT_WEBHOOK=1000,60

# Request limits
MAX_REQUEST_SIZE_WEBHOOK=1048576  # 1MB in bytes
MAX_REQUEST_SIZE_DEFAULT=10240    # 10KB in bytes

# Timeouts
REQUEST_TIMEOUT=30  # seconds

# Dashboard security
DASHBOARD_TOKENS=token1,token2,token3
DASHBOARD_ALLOWED_ORIGINS=https://admin.example.com
```

## 📋 Security Checklist

### Pre-Deployment
- [ ] All environment variables set
- [ ] Dashboard tokens generated (32+ chars)
- [ ] Webhook secret configured (32+ chars)
- [ ] Rate limits appropriate for load
- [ ] Security tests passing

### Post-Deployment
- [ ] Monitor rate limit hits
- [ ] Check for validation errors
- [ ] Review security logs daily
- [ ] Update tokens quarterly
- [ ] Penetration test annually

## 🆘 Common Issues

### "Too Many Requests" for legitimate users
- Increase rate limit for specific endpoint
- Consider per-user limits vs global
- Implement token bucket algorithm

### Dashboard not loading
- Check bearer token is correct
- Verify CORS settings if cross-origin
- Check date range parameters

### Webhooks failing validation
- Verify secret token matches
- Check Content-Type header
- Validate JSON structure

## 📚 Security Best Practices

1. **Never trust user input** - Always validate and sanitize
2. **Use parameterized queries** - Never concatenate SQL
3. **Fail securely** - Default to denying access
4. **Log security events** - But don't log sensitive data
5. **Keep dependencies updated** - Regular security patches
6. **Use HTTPS only** - Encrypt all traffic
7. **Implement defense in depth** - Multiple layers of security
8. **Regular security audits** - Test your defenses

## 🔗 References

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [SQL Injection Prevention](https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html)
- [XSS Prevention](https://cheatsheetseries.owasp.org/cheatsheets/Cross_Site_Scripting_Prevention_Cheat_Sheet.html)
- [Rate Limiting Best Practices](https://www.nginx.com/blog/rate-limiting-nginx/)
- [Telegram Bot Security](https://core.telegram.org/bots/webhooks#security)