"""
Structured logging configuration for Telegram Stars subscription bot.
Provides correlation IDs, performance metrics, and consistent log formatting.
"""

import logging
import sys
import time
import os
from typing import Any, Dict, Optional, Callable
from contextvars import ContextVar
from functools import wraps
from datetime import datetime, timezone
import uuid

import structlog
from structlog.processors import CallsiteParameter
from pythonjsonlogger import jsonlogger

# Context variables for request-scoped data
correlation_id_var: ContextVar[Optional[str]] = ContextVar('correlation_id', default=None)
user_id_var: ContextVar[Optional[int]] = ContextVar('user_id', default=None)
request_start_var: ContextVar[Optional[float]] = ContextVar('request_start', default=None)

# Get configuration from environment
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()
LOG_FORMAT = os.getenv('LOG_FORMAT', 'console').lower()  # 'json' or 'console'
LOG_FILE = os.getenv('LOG_FILE')  # Optional log file path
ENVIRONMENT = os.getenv('ENVIRONMENT', 'development')


def add_context(logger, method_name, event_dict):
    """Add context variables to all log entries"""
    # Add correlation ID if present
    correlation_id = correlation_id_var.get()
    if correlation_id:
        event_dict['correlation_id'] = correlation_id
    
    # Add user ID if present
    user_id = user_id_var.get()
    if user_id:
        event_dict['user_id'] = user_id
    
    # Add request duration if we're tracking it
    request_start = request_start_var.get()
    if request_start:
        event_dict['request_duration_ms'] = int((time.time() - request_start) * 1000)
    
    # Add environment
    event_dict['environment'] = ENVIRONMENT
    
    # Add timestamp in ISO format
    if 'timestamp' not in event_dict:
        event_dict['timestamp'] = datetime.now(timezone.utc).isoformat()
    
    return event_dict


def extract_from_exception(logger, method_name, event_dict):
    """Extract and format exception information"""
    if 'exception' in event_dict:
        exc_info = event_dict.pop('exception')
        if exc_info:
            event_dict['error_type'] = exc_info.__class__.__name__
            event_dict['error_message'] = str(exc_info)
            # Add stack trace in development
            if ENVIRONMENT == 'development':
                import traceback
                event_dict['stack_trace'] = traceback.format_exception(
                    type(exc_info), exc_info, exc_info.__traceback__
                )
    return event_dict


def setup_logging():
    """Configure structured logging for the application"""
    
    # Configure processors based on format
    shared_processors = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        add_context,
        extract_from_exception,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]
    
    if LOG_FORMAT == 'json':
        # JSON format for production
        processors = shared_processors + [
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer()
        ]
    else:
        # Console format for development
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(
                colors=True,
                pad_event=30,
                repr_native_str=False,
            )
        ]
    
    # Configure structlog
    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Configure stdlib logging to use structlog
    if LOG_FORMAT == 'json':
        # JSON formatter for stdlib
        formatter = jsonlogger.JsonFormatter(
            '%(timestamp)s %(level)s %(name)s %(message)s',
            rename_fields={'level': 'severity', 'name': 'logger'}
        )
    else:
        # Standard formatter for development
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, LOG_LEVEL))
    
    # Clear existing handlers
    root_logger.handlers = []
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # File handler if configured
    if LOG_FILE:
        file_handler = logging.FileHandler(LOG_FILE)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    
    # Reduce noise from libraries
    logging.getLogger('aiogram').setLevel(logging.WARNING)
    logging.getLogger('uvicorn.access').setLevel(logging.WARNING)
    logging.getLogger('asyncio').setLevel(logging.WARNING)
    
    return structlog.get_logger()


def get_logger(name: str = None) -> structlog.BoundLogger:
    """Get a structured logger instance"""
    if name:
        return structlog.get_logger(name)
    return structlog.get_logger()


def set_correlation_id(correlation_id: str = None) -> str:
    """Set or generate a correlation ID for the current context"""
    if not correlation_id:
        correlation_id = str(uuid.uuid4())
    correlation_id_var.set(correlation_id)
    return correlation_id


def set_user_id(user_id: int):
    """Set the user ID for the current context"""
    user_id_var.set(user_id)


def set_request_start():
    """Mark the start of a request for duration tracking"""
    request_start_var.set(time.time())


def log_performance(operation: str = None):
    """Decorator to log performance metrics for a function"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            logger = get_logger(func.__module__)
            op_name = operation or f"{func.__module__}.{func.__name__}"
            start_time = time.time()
            
            try:
                logger.debug(f"{op_name}.started")
                result = await func(*args, **kwargs)
                duration_ms = int((time.time() - start_time) * 1000)
                
                # Log slow operations
                if duration_ms > 100:
                    logger.warning(
                        f"{op_name}.slow",
                        duration_ms=duration_ms,
                        threshold_ms=100
                    )
                else:
                    logger.debug(
                        f"{op_name}.completed",
                        duration_ms=duration_ms
                    )
                
                return result
                
            except Exception as e:
                duration_ms = int((time.time() - start_time) * 1000)
                logger.error(
                    f"{op_name}.failed",
                    duration_ms=duration_ms,
                    exception=e
                )
                raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            logger = get_logger(func.__module__)
            op_name = operation or f"{func.__module__}.{func.__name__}"
            start_time = time.time()
            
            try:
                logger.debug(f"{op_name}.started")
                result = func(*args, **kwargs)
                duration_ms = int((time.time() - start_time) * 1000)
                
                if duration_ms > 100:
                    logger.warning(
                        f"{op_name}.slow",
                        duration_ms=duration_ms,
                        threshold_ms=100
                    )
                else:
                    logger.debug(
                        f"{op_name}.completed",
                        duration_ms=duration_ms
                    )
                
                return result
                
            except Exception as e:
                duration_ms = int((time.time() - start_time) * 1000)
                logger.error(
                    f"{op_name}.failed",
                    duration_ms=duration_ms,
                    exception=e
                )
                raise
        
        # Return appropriate wrapper based on function type
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def log_business_event(event_name: str, **kwargs):
    """Log a business event with consistent structure"""
    logger = get_logger('business_events')
    logger.info(event_name, **kwargs)


def log_error(error_name: str, exception: Exception = None, **kwargs):
    """Log an error with consistent structure"""
    logger = get_logger('errors')
    logger.error(error_name, exception=exception, **kwargs)


# Business event constants for consistency
class BusinessEvents:
    # Payment events
    PAYMENT_INITIATED = "payment.initiated"
    PAYMENT_PROCESSED = "payment.processed"
    PAYMENT_FAILED = "payment.failed"
    PAYMENT_DUPLICATE = "payment.duplicate"
    
    # Subscription events
    SUBSCRIPTION_CREATED = "subscription.created"
    SUBSCRIPTION_RENEWED = "subscription.renewed"
    SUBSCRIPTION_EXPIRED = "subscription.expired"
    SUBSCRIPTION_CANCELLED = "subscription.cancelled"
    
    # Grace period events
    GRACE_PERIOD_STARTED = "grace_period.started"
    GRACE_PERIOD_ENDED = "grace_period.ended"
    GRACE_PERIOD_REMINDER = "grace_period.reminder"
    
    # Reconciliation events
    RECONCILIATION_STARTED = "reconciliation.started"
    RECONCILIATION_COMPLETED = "reconciliation.completed"
    RECONCILIATION_PAYMENT_FOUND = "reconciliation.payment_found"
    
    # Join request events
    JOIN_REQUEST_RECEIVED = "join_request.received"
    JOIN_REQUEST_APPROVED = "join_request.approved"
    JOIN_REQUEST_REJECTED = "join_request.rejected"
    JOIN_REQUEST_AUTO_APPROVED = "join_request.auto_approved"
    
    # User events
    USER_WHITELISTED = "user.whitelisted"
    USER_WHITELIST_BURNED = "user.whitelist_burned"
    USER_BANNED = "user.banned"
    USER_UNBANNED = "user.unbanned"
    
    # Dashboard events
    DASHBOARD_ACCESS_GRANTED = "dashboard.access_granted"
    DASHBOARD_ACCESS_DENIED = "dashboard.access_denied"
    
    # Webhook events
    WEBHOOK_RECEIVED = "webhook.received"
    WEBHOOK_PROCESSED = "webhook.processed"
    WEBHOOK_FAILED = "webhook.failed"


# Initialize logging on import
logger = setup_logging()