"""
Input validation and sanitization utilities for the Telegram bot.
Provides Pydantic models for request validation and SQL injection prevention.
"""

import re
import html
import bleach
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from pydantic import BaseModel, Field, field_validator, conint, constr
from pydantic import ConfigDict


# Security constants
MAX_TEXT_LENGTH = 1000
MAX_DATE_RANGE_DAYS = 90
ALLOWED_TAGS = []  # No HTML tags allowed
ALLOWED_ATTRIBUTES = {}
SQL_INJECTION_PATTERNS = [
    r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|EXECUTE|UNION|FROM|WHERE|JOIN|ORDER\s+BY|GROUP\s+BY|HAVING)\b)",
    r"(--|#|/\*|\*/|;|\||&&|\|\||xp_|sp_)",
    r"('|\"|`|\\x27|\\x22|\\x60)",
]

# Telegram ID constraints
MAX_USER_ID = 9999999999  # Telegram user ID limit
MIN_GROUP_CHAT_ID = -1999999999999  # Telegram group chat ID limit


class DashboardParams(BaseModel):
    """Validate dashboard API parameters to prevent SQL injection"""
    
    start_date: Optional[datetime] = Field(None, description="Start date for filtering")
    end_date: Optional[datetime] = Field(None, description="End date for filtering")
    limit: conint(ge=1, le=1000) = Field(100, description="Result limit")
    offset: conint(ge=0) = Field(0, description="Result offset")
    user_id: Optional[conint(gt=0, le=MAX_USER_ID)] = Field(None, description="Filter by user ID")
    status: Optional[constr(pattern="^(active|grace|expired)$")] = Field(None, description="Filter by status")
    
    @field_validator('end_date')
    @classmethod
    def validate_date_range(cls, v, info):
        """Validate date range constraints"""
        if v and info.data.get('start_date'):
            if v < info.data['start_date']:
                raise ValueError('end_date must be after start_date')
            
            # Prevent excessive date ranges that could cause performance issues
            date_diff = v - info.data['start_date']
            if date_diff.days > MAX_DATE_RANGE_DAYS:
                raise ValueError(f'Date range cannot exceed {MAX_DATE_RANGE_DAYS} days')
        
        # Prevent future dates
        if v and v > datetime.now(timezone.utc):
            raise ValueError('end_date cannot be in the future')
            
        return v
    
    @field_validator('start_date')
    @classmethod
    def validate_start_date(cls, v):
        """Validate start date"""
        if v and v > datetime.now(timezone.utc):
            raise ValueError('start_date cannot be in the future')
        return v
    
    def to_sql_filters(self) -> tuple[str, list]:
        """Convert validated params to SQL WHERE clause components"""
        conditions = []
        params = []
        param_index = 1
        
        if self.start_date:
            conditions.append(f"created_at >= ${param_index}")
            params.append(self.start_date)
            param_index += 1
        
        if self.end_date:
            conditions.append(f"created_at <= ${param_index}")
            params.append(self.end_date)
            param_index += 1
        
        if self.user_id:
            conditions.append(f"user_id = ${param_index}")
            params.append(self.user_id)
            param_index += 1
        
        if self.status:
            conditions.append(f"status = ${param_index}")
            params.append(self.status)
            param_index += 1
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        return where_clause, params


class SubscriptionLinkParams(BaseModel):
    """Validate subscription link generation parameters"""
    
    user_id: conint(gt=0, le=MAX_USER_ID) = Field(..., description="User ID for subscription")
    plan_type: constr(pattern="^(one_time|subscription)$") = Field("one_time", description="Plan type")
    amount: conint(gt=0, le=100000) = Field(..., description="Amount in Stars")
    
    model_config = ConfigDict(
        extra='forbid',
        str_max_length=100
    )


class WebhookUpdateData(BaseModel):
    """Validate Telegram webhook update structure"""
    
    update_id: conint(gt=0) = Field(..., description="Telegram update ID")
    message: Optional[Dict[str, Any]] = None
    callback_query: Optional[Dict[str, Any]] = None
    pre_checkout_query: Optional[Dict[str, Any]] = None
    chat_join_request: Optional[Dict[str, Any]] = None
    chat_member: Optional[Dict[str, Any]] = None
    my_chat_member: Optional[Dict[str, Any]] = None
    
    @field_validator('update_id', mode='before')
    @classmethod
    def validate_update_id(cls, v):
        """Ensure update_id is valid"""
        if not isinstance(v, int) or v <= 0:
            raise ValueError('Invalid update_id')
        return v
    
    model_config = ConfigDict(
        extra='forbid',  # Reject unknown fields
        str_max_length=MAX_TEXT_LENGTH
    )


def sanitize_text(text: str, max_length: int = MAX_TEXT_LENGTH) -> str:
    """
    Sanitize user input text to prevent XSS and injection attacks
    
    Args:
        text: Raw user input
        max_length: Maximum allowed length
    
    Returns:
        Sanitized text safe for storage and display
    """
    if not text:
        return ""
    
    # Truncate to max length
    text = text[:max_length]
    
    # Remove any HTML tags and attributes
    text = bleach.clean(
        text,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        strip=True
    )
    
    # Escape HTML entities
    text = html.escape(text)
    
    # Remove null bytes
    text = text.replace('\x00', '')
    
    # Normalize whitespace
    text = ' '.join(text.split())
    
    return text


def sanitize_log_message(message: str) -> str:
    """
    Sanitize log messages to prevent log injection
    
    Args:
        message: Raw log message
    
    Returns:
        Sanitized log message
    """
    if not message:
        return ""
    
    # Remove newlines and carriage returns to prevent log injection
    message = message.replace('\n', ' ').replace('\r', ' ')
    
    # Remove ANSI escape codes
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    message = ansi_escape.sub('', message)
    
    # Truncate to reasonable length
    message = message[:500]
    
    return message


def validate_telegram_id(telegram_id: int) -> bool:
    """
    Validate Telegram user or chat ID
    
    Args:
        telegram_id: Telegram ID to validate
    
    Returns:
        True if valid, False otherwise
    """
    if telegram_id > 0:
        # User ID
        return telegram_id <= MAX_USER_ID
    else:
        # Group/channel ID
        return telegram_id >= MIN_GROUP_CHAT_ID


def detect_sql_injection(text: str) -> bool:
    """
    Detect potential SQL injection attempts
    
    Args:
        text: Input text to check
    
    Returns:
        True if potential SQL injection detected, False otherwise
    """
    if not text:
        return False
    
    text_upper = text.upper()
    
    for pattern in SQL_INJECTION_PATTERNS:
        if re.search(pattern, text_upper, re.IGNORECASE):
            return True
    
    return False


def constant_time_compare(a: str, b: str) -> bool:
    """
    Constant-time string comparison to prevent timing attacks
    
    Args:
        a: First string
        b: Second string
    
    Returns:
        True if strings match, False otherwise
    """
    import hmac
    return hmac.compare_digest(a, b)


def validate_webhook_signature(payload: bytes, signature: str, secret: str) -> bool:
    """
    Validate webhook signature using HMAC-SHA256
    
    Args:
        payload: Raw request body bytes
        signature: Provided signature header
        secret: Expected secret key
    
    Returns:
        True if signature is valid, False otherwise
    """
    import hmac
    import hashlib
    
    if not signature or not secret:
        return False
    
    # Remove 'sha256=' prefix if present
    if signature.startswith('sha256='):
        signature = signature[7:]
    
    # Calculate expected signature
    expected_signature = hmac.new(
        secret.encode('utf-8'),
        payload,
        hashlib.sha256
    ).hexdigest()
    
    # Use constant-time comparison
    return hmac.compare_digest(signature, expected_signature)


def validate_webhook_secret(provided_secret: str, expected_secret: str) -> bool:
    """
    Validate webhook secret in constant time to prevent timing attacks
    
    Args:
        provided_secret: Secret provided in the request
        expected_secret: Expected secret value
    
    Returns:
        True if secrets match, False otherwise
    """
    import hmac
    
    if not provided_secret or not expected_secret:
        return False
    
    # Use constant-time comparison to prevent timing attacks
    return hmac.compare_digest(provided_secret, expected_secret)