"""
Middleware for request tracking and correlation IDs
"""

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import uuid
import time
from app.logging_config import (
    get_logger, 
    set_correlation_id, 
    set_request_start,
    BusinessEvents
)

logger = get_logger(__name__)


class CorrelationIDMiddleware(BaseHTTPMiddleware):
    """Add correlation IDs to all requests for tracing"""
    
    async def dispatch(self, request: Request, call_next):
        # Extract or generate correlation ID
        correlation_id = (
            request.headers.get("X-Correlation-ID") or
            request.headers.get("X-Request-ID") or
            str(uuid.uuid4())
        )
        
        # Set for the current context
        set_correlation_id(correlation_id)
        set_request_start()
        
        # Log request start
        logger.info(
            "request.started",
            method=request.method,
            path=request.url.path,
            correlation_id=correlation_id
        )
        
        start_time = time.time()
        
        try:
            # Process request
            response = await call_next(request)
            
            # Calculate duration
            duration_ms = int((time.time() - start_time) * 1000)
            
            # Add correlation ID to response headers
            response.headers["X-Correlation-ID"] = correlation_id
            
            # Log request completion
            logger.info(
                "request.completed",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=duration_ms,
                correlation_id=correlation_id
            )
            
            return response
            
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            
            # Log request failure
            logger.error(
                "request.failed",
                method=request.method,
                path=request.url.path,
                duration_ms=duration_ms,
                correlation_id=correlation_id,
                exception=e
            )
            raise


class WebhookLoggingMiddleware:
    """Special logging for Telegram webhook requests"""
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and "/webhook/" in scope["path"]:
            # This is a webhook request
            request = Request(scope, receive)
            
            # Extract Telegram update ID if present in body
            update_id = None
            try:
                if request.headers.get("content-type") == "application/json":
                    body = await request.body()
                    import json
                    data = json.loads(body)
                    update_id = data.get("update_id")
                    
                    # Create new receive that returns the cached body
                    async def receive_with_body():
                        return {
                            "type": "http.request",
                            "body": body,
                        }
                    
                    # Replace receive function
                    receive = receive_with_body
                    
            except Exception:
                pass
            
            # Generate correlation ID based on update ID if available
            correlation_id = f"webhook-{update_id}" if update_id else str(uuid.uuid4())
            set_correlation_id(correlation_id)
            set_request_start()
            
            logger.info(
                BusinessEvents.WEBHOOK_RECEIVED,
                update_id=update_id,
                correlation_id=correlation_id,
                path=scope["path"]
            )
        
        await self.app(scope, receive, send)