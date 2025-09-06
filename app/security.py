"""
Security middleware for rate limiting, request validation, and protection.
"""

import time
import json
from typing import Dict, Optional, Tuple
from collections import defaultdict, deque
from datetime import datetime, timedelta
from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import asyncio

from app.logging_config import get_logger
from app.validators import constant_time_compare, validate_webhook_signature

logger = get_logger(__name__)

# Rate limiting configuration
RATE_LIMITS = {
    "/r/sub": (10, 60),           # 10 requests per 60 seconds per user
    "/admin/api/summary": (100, 60),  # 100 requests per 60 seconds per token
    "/webhook/": (1000, 60),      # 1000 webhooks per 60 seconds total
    "default": (60, 60),          # 60 requests per minute default
}

# Request size limits (in bytes)
MAX_REQUEST_SIZES = {
    "/webhook/": 1024 * 1024,     # 1MB for webhooks
    "/admin/": 100 * 1024,         # 100KB for admin endpoints
    "default": 10 * 1024,          # 10KB default
}

REQUEST_TIMEOUT = 30  # seconds


class RateLimiter:
    """Simple in-memory rate limiter using sliding window"""
    
    def __init__(self):
        # Store request timestamps for each key
        self.requests: Dict[str, deque] = defaultdict(lambda: deque())
        self.lock = asyncio.Lock()
    
    async def check_rate_limit(self, key: str, max_requests: int, window_seconds: int) -> Tuple[bool, int]:
        """
        Check if request is within rate limit.
        Returns (allowed, remaining_requests)
        """
        async with self.lock:
            now = time.time()
            window_start = now - window_seconds
            
            # Get request history for this key
            request_times = self.requests[key]
            
            # Remove old requests outside the window
            while request_times and request_times[0] < window_start:
                request_times.popleft()
            
            # Check if limit exceeded
            if len(request_times) >= max_requests:
                # Calculate when the oldest request will expire
                retry_after = int(request_times[0] + window_seconds - now) + 1
                return False, retry_after
            
            # Add current request
            request_times.append(now)
            remaining = max_requests - len(request_times)
            
            return True, remaining
    
    async def cleanup_old_entries(self):
        """Periodically clean up old entries to prevent memory growth"""
        async with self.lock:
            now = time.time()
            max_age = 3600  # Keep entries for max 1 hour
            
            keys_to_delete = []
            for key, times in self.requests.items():
                # Remove old timestamps
                while times and times[0] < now - max_age:
                    times.popleft()
                
                # Mark empty keys for deletion
                if not times:
                    keys_to_delete.append(key)
            
            # Delete empty keys
            for key in keys_to_delete:
                del self.requests[key]


# Global rate limiter instance
rate_limiter = RateLimiter()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware to enforce rate limits on endpoints"""
    
    async def dispatch(self, request: Request, call_next):
        # Determine rate limit for this endpoint
        path = request.url.path
        limit_config = None
        
        for pattern, config in RATE_LIMITS.items():
            if pattern in path:
                limit_config = config
                break
        
        if not limit_config:
            limit_config = RATE_LIMITS["default"]
        
        max_requests, window_seconds = limit_config
        
        # Generate rate limit key
        # For /r/sub, use user_id from query params
        if "/r/sub" in path:
            user_id = request.query_params.get("u", "unknown")
            rate_key = f"sub:{user_id}"
        # For admin endpoints, use bearer token
        elif "/admin/" in path:
            auth_header = request.headers.get("authorization", "")
            token = auth_header[7:] if auth_header.startswith("Bearer ") else "unknown"
            rate_key = f"admin:{token[:20]}"  # Use first 20 chars of token
        # For webhooks, use global limit
        elif "/webhook/" in path:
            rate_key = "webhook:global"
        # Default: use IP address
        else:
            client_ip = request.client.host if request.client else "unknown"
            rate_key = f"ip:{client_ip}"
        
        # Check rate limit
        allowed, retry_after = await rate_limiter.check_rate_limit(
            rate_key, max_requests, window_seconds
        )
        
        if not allowed:
            logger.warning(
                "rate_limit.exceeded",
                path=path,
                key=rate_key,
                retry_after=retry_after
            )
            
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Too Many Requests",
                    "retry_after": retry_after
                },
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(max_requests),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(time.time() + retry_after))
                }
            )
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(max_requests)
        response.headers["X-RateLimit-Remaining"] = str(max_requests - 1)
        response.headers["X-RateLimit-Reset"] = str(int(time.time() + window_seconds))
        
        return response


class SecurityMiddleware(BaseHTTPMiddleware):
    """Middleware for request security validation"""
    
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        
        # 1. Check request size
        max_size = self._get_max_size(path)
        content_length = request.headers.get("content-length")
        
        if content_length and int(content_length) > max_size:
            logger.warning(
                "security.request_too_large",
                path=path,
                size=content_length,
                max_size=max_size
            )
            return JSONResponse(
                status_code=413,
                content={"error": "Request Entity Too Large"}
            )
        
        # 2. Validate Content-Type for POST requests
        if request.method == "POST":
            content_type = request.headers.get("content-type", "")
            
            # Webhook must be JSON
            if "/webhook/" in path and "application/json" not in content_type:
                logger.warning(
                    "security.invalid_content_type",
                    path=path,
                    content_type=content_type
                )
                return JSONResponse(
                    status_code=400,
                    content={"error": "Invalid Content-Type, expected application/json"}
                )
        
        # 3. Add security headers to response
        response = await call_next(request)
        
        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # CORS headers for dashboard (if needed)
        if "/admin/" in path and request.method == "GET":
            # Only allow specific origins if dashboard needs CORS
            allowed_origins = os.getenv("DASHBOARD_ALLOWED_ORIGINS", "").split(",")
            origin = request.headers.get("origin")
            
            if origin and origin in allowed_origins:
                response.headers["Access-Control-Allow-Origin"] = origin
                response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
                response.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
                response.headers["Access-Control-Max-Age"] = "86400"
        
        return response
    
    def _get_max_size(self, path: str) -> int:
        """Get maximum allowed request size for path"""
        for pattern, size in MAX_REQUEST_SIZES.items():
            if pattern in path:
                return size
        return MAX_REQUEST_SIZES["default"]


class TimeoutMiddleware(BaseHTTPMiddleware):
    """Middleware to enforce request timeout"""
    
    async def dispatch(self, request: Request, call_next):
        try:
            # Add timeout to request processing
            response = await asyncio.wait_for(
                call_next(request),
                timeout=REQUEST_TIMEOUT
            )
            return response
            
        except asyncio.TimeoutError:
            logger.error(
                "security.request_timeout",
                path=request.url.path,
                method=request.method,
                timeout=REQUEST_TIMEOUT
            )
            return JSONResponse(
                status_code=504,
                content={"error": "Request timeout"}
            )


async def validate_webhook_request(request: Request, secret: str) -> bool:
    """
    Validate webhook request authenticity.
    Uses constant-time comparison to prevent timing attacks.
    """
    # Check for secret token header
    provided_token = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    
    if not provided_token:
        logger.warning(
            "webhook.missing_secret",
            path=request.url.path
        )
        return False
    
    # Constant time comparison to prevent timing attacks
    if not constant_time_compare(provided_token, secret):
        logger.warning(
            "webhook.invalid_secret",
            path=request.url.path
        )
        return False
    
    # Optional: Validate signature if Telegram starts providing it
    signature = request.headers.get("X-Telegram-Bot-Api-Signature")
    if signature:
        # Read body for signature validation
        body = await request.body()
        
        if not validate_webhook_signature(body, signature, secret):
            logger.warning(
                "webhook.invalid_signature",
                path=request.url.path
            )
            return False
    
    return True


# Cleanup task for rate limiter
async def cleanup_rate_limiter():
    """Periodic cleanup of old rate limit entries"""
    while True:
        try:
            await asyncio.sleep(300)  # Run every 5 minutes
            await rate_limiter.cleanup_old_entries()
            logger.debug("rate_limiter.cleanup_completed")
        except Exception as e:
            logger.error("rate_limiter.cleanup_failed", exception=e)


# SQL injection prevention helpers
def build_safe_query(base_query: str, filters: Dict[str, any]) -> Tuple[str, list]:
    """
    Build a safe SQL query with parameterized values.
    Never use string formatting for SQL queries!
    """
    conditions = []
    params = []
    param_index = 1
    
    for field, value in filters.items():
        if value is not None:
            # Use parameterized queries
            conditions.append(f"{field} = ${param_index}")
            params.append(value)
            param_index += 1
    
    if conditions:
        where_clause = " WHERE " + " AND ".join(conditions)
        query = base_query + where_clause
    else:
        query = base_query
    
    return query, params


def sanitize_order_by(column: str, allowed_columns: list) -> Optional[str]:
    """
    Safely validate ORDER BY column to prevent SQL injection.
    Only allow whitelisted column names.
    """
    if not column:
        return None
    
    # Remove any SQL special characters
    column = re.sub(r'[^a-zA-Z0-9_]', '', column)
    
    # Check against whitelist
    if column not in allowed_columns:
        logger.warning(
            "security.invalid_order_by",
            column=column,
            allowed=allowed_columns
        )
        return None
    
    return column


import os
import re