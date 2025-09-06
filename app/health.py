"""
Health check endpoints for monitoring application health.
Includes liveness, readiness, and detailed health checks.
"""

import asyncio
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from enum import Enum

from app.db import db
from app.bot import bot
from app.config import settings
from app.logging_config import get_logger
from app.resilience import circuit_breakers, operation_queue

logger = get_logger(__name__)


class HealthStatus(Enum):
    """Health check status levels"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class ComponentHealth:
    """Health status for a component"""
    def __init__(
        self,
        name: str,
        status: HealthStatus,
        message: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        response_time: Optional[float] = None
    ):
        self.name = name
        self.status = status
        self.message = message or status.value
        self.details = details or {}
        self.response_time = response_time
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON response"""
        result = {
            "name": self.name,
            "status": self.status.value,
            "message": self.message
        }
        
        if self.response_time is not None:
            result["response_time_ms"] = round(self.response_time * 1000, 2)
        
        if self.details:
            result["details"] = self.details
        
        return result


async def check_database_health() -> ComponentHealth:
    """Check database connectivity and performance"""
    start = time.time()
    
    try:
        # Simple query to check connection
        result = await db.fetchval("SELECT 1")
        
        if result != 1:
            return ComponentHealth(
                name="database",
                status=HealthStatus.UNHEALTHY,
                message="Database query returned unexpected result"
            )
        
        # Check connection pool stats if available
        pool_stats = {}
        if hasattr(db, 'pool') and db.pool:
            pool_stats = {
                "size": db.pool.get_size(),
                "free": db.pool.get_idle_size(),
                "used": db.pool.get_size() - db.pool.get_idle_size(),
                "max_size": db.pool.get_max_size()
            }
        
        response_time = time.time() - start
        
        # Check if response time is acceptable
        if response_time > 1.0:  # 1 second threshold
            return ComponentHealth(
                name="database",
                status=HealthStatus.DEGRADED,
                message=f"Slow response time: {response_time:.2f}s",
                details=pool_stats,
                response_time=response_time
            )
        
        return ComponentHealth(
            name="database",
            status=HealthStatus.HEALTHY,
            message="Database is responsive",
            details=pool_stats,
            response_time=response_time
        )
        
    except Exception as e:
        logger.error(
            "health_check.database_failed",
            exception=e
        )
        return ComponentHealth(
            name="database",
            status=HealthStatus.UNHEALTHY,
            message=f"Database check failed: {str(e)}",
            response_time=time.time() - start
        )


async def check_telegram_bot_health() -> ComponentHealth:
    """Check Telegram bot connectivity"""
    start = time.time()
    
    try:
        # Get bot info to check connection
        me = await bot.get_me()
        
        if not me:
            return ComponentHealth(
                name="telegram_bot",
                status=HealthStatus.UNHEALTHY,
                message="Failed to get bot info"
            )
        
        # Check webhook status
        webhook_info = await bot.get_webhook_info()
        webhook_details = {
            "bot_username": me.username,
            "webhook_url": webhook_info.url if webhook_info else None,
            "pending_updates": webhook_info.pending_update_count if webhook_info else 0
        }
        
        response_time = time.time() - start
        
        # Check for issues
        if webhook_info and webhook_info.pending_update_count > 100:
            return ComponentHealth(
                name="telegram_bot",
                status=HealthStatus.DEGRADED,
                message=f"High pending updates: {webhook_info.pending_update_count}",
                details=webhook_details,
                response_time=response_time
            )
        
        if response_time > 2.0:  # 2 second threshold for Telegram API
            return ComponentHealth(
                name="telegram_bot",
                status=HealthStatus.DEGRADED,
                message=f"Slow response time: {response_time:.2f}s",
                details=webhook_details,
                response_time=response_time
            )
        
        return ComponentHealth(
            name="telegram_bot",
            status=HealthStatus.HEALTHY,
            message="Bot is connected and responsive",
            details=webhook_details,
            response_time=response_time
        )
        
    except Exception as e:
        logger.error(
            "health_check.telegram_bot_failed",
            exception=e
        )
        return ComponentHealth(
            name="telegram_bot",
            status=HealthStatus.UNHEALTHY,
            message=f"Bot check failed: {str(e)}",
            response_time=time.time() - start
        )


async def check_circuit_breakers_health() -> ComponentHealth:
    """Check circuit breaker states"""
    unhealthy_breakers = []
    degraded_breakers = []
    
    details = {}
    for name, breaker in circuit_breakers.items():
        stats = breaker.get_stats()
        details[name] = {
            "state": stats["state"],
            "failure_rate": round(stats["failure_rate"], 2),
            "consecutive_failures": stats["consecutive_failures"]
        }
        
        if breaker.is_open:
            unhealthy_breakers.append(name)
        elif breaker.state.value == "half_open":
            degraded_breakers.append(name)
    
    if unhealthy_breakers:
        return ComponentHealth(
            name="circuit_breakers",
            status=HealthStatus.UNHEALTHY,
            message=f"Open circuits: {', '.join(unhealthy_breakers)}",
            details=details
        )
    
    if degraded_breakers:
        return ComponentHealth(
            name="circuit_breakers",
            status=HealthStatus.DEGRADED,
            message=f"Half-open circuits: {', '.join(degraded_breakers)}",
            details=details
        )
    
    return ComponentHealth(
        name="circuit_breakers",
        status=HealthStatus.HEALTHY,
        message=f"All {len(circuit_breakers)} circuits closed",
        details=details if circuit_breakers else None
    )


async def check_operation_queue_health() -> ComponentHealth:
    """Check operation queue status"""
    stats = operation_queue.get_stats()
    
    if stats["queue_size"] > 500:  # High queue size
        return ComponentHealth(
            name="operation_queue",
            status=HealthStatus.UNHEALTHY,
            message=f"Queue overloaded: {stats['queue_size']} operations",
            details=stats
        )
    
    if stats["queue_size"] > 100:  # Moderate queue size
        return ComponentHealth(
            name="operation_queue",
            status=HealthStatus.DEGRADED,
            message=f"Queue building up: {stats['queue_size']} operations",
            details=stats
        )
    
    return ComponentHealth(
        name="operation_queue",
        status=HealthStatus.HEALTHY,
        message=f"Queue size: {stats['queue_size']}",
        details=stats
    )


async def liveness_check() -> dict:
    """
    Liveness probe - checks if application is running.
    Returns 200 if alive, 503 if not.
    """
    return {
        "status": "alive",
        "service": "telegram-stars-membership",
        "version": "1.3",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


async def readiness_check() -> tuple[dict, int]:
    """
    Readiness probe - checks if application is ready to serve requests.
    Returns 200 if ready, 503 if not.
    """
    # Quick checks for readiness
    checks = []
    
    # Check database
    try:
        await asyncio.wait_for(
            db.fetchval("SELECT 1"),
            timeout=2.0
        )
        checks.append(("database", True))
    except Exception:
        checks.append(("database", False))
    
    # Check bot
    try:
        await asyncio.wait_for(
            bot.get_me(),
            timeout=2.0
        )
        checks.append(("telegram_bot", True))
    except Exception:
        checks.append(("telegram_bot", False))
    
    # Determine overall readiness
    all_ready = all(status for _, status in checks)
    
    response = {
        "status": "ready" if all_ready else "not_ready",
        "checks": {name: status for name, status in checks},
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    return response, 200 if all_ready else 503


async def detailed_health_check() -> tuple[dict, int]:
    """
    Detailed health check with component status.
    Returns comprehensive health information.
    """
    components = []
    
    # Run all health checks concurrently
    checks = await asyncio.gather(
        check_database_health(),
        check_telegram_bot_health(),
        check_circuit_breakers_health(),
        check_operation_queue_health(),
        return_exceptions=True
    )
    
    # Process results
    for check in checks:
        if isinstance(check, Exception):
            components.append(
                ComponentHealth(
                    name="unknown",
                    status=HealthStatus.UNHEALTHY,
                    message=f"Check failed: {str(check)}"
                ).to_dict()
            )
        else:
            components.append(check.to_dict())
    
    # Determine overall status
    statuses = [c.get("status") for c in components]
    
    if any(s == "unhealthy" for s in statuses):
        overall_status = "unhealthy"
        status_code = 503
    elif any(s == "degraded" for s in statuses):
        overall_status = "degraded"
        status_code = 200  # Still return 200 for degraded
    else:
        overall_status = "healthy"
        status_code = 200
    
    # Add metrics
    metrics = await get_health_metrics()
    
    response = {
        "status": overall_status,
        "service": "telegram-stars-membership",
        "version": "1.3",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "components": components,
        "metrics": metrics
    }
    
    logger.info(
        "health_check.completed",
        overall_status=overall_status,
        components_checked=len(components)
    )
    
    return response, status_code


async def get_health_metrics() -> dict:
    """Get application metrics for health check"""
    try:
        # Get database metrics
        db_metrics = await db.fetch_one("""
            SELECT 
                COUNT(DISTINCT user_id) as total_users,
                COUNT(DISTINCT CASE 
                    WHEN last_interaction > NOW() - INTERVAL '24 hours' 
                    THEN user_id 
                END) as active_24h
            FROM users
        """)
        
        # Get subscription metrics
        sub_metrics = await db.fetch_one("""
            SELECT 
                COUNT(*) FILTER (WHERE status = 'active') as active_subs,
                COUNT(*) FILTER (WHERE status = 'grace') as grace_subs,
                COUNT(*) FILTER (
                    WHERE status = 'active' 
                    AND expires_at < NOW() + INTERVAL '24 hours'
                ) as expiring_24h
            FROM subscriptions
        """)
        
        # Get payment metrics
        payment_metrics = await db.fetch_one("""
            SELECT 
                COUNT(*) as payments_24h,
                COALESCE(SUM(amount), 0) as revenue_24h
            FROM payments
            WHERE created_at > NOW() - INTERVAL '24 hours'
        """)
        
        return {
            "users": {
                "total": db_metrics["total_users"] if db_metrics else 0,
                "active_24h": db_metrics["active_24h"] if db_metrics else 0
            },
            "subscriptions": {
                "active": sub_metrics["active_subs"] if sub_metrics else 0,
                "grace": sub_metrics["grace_subs"] if sub_metrics else 0,
                "expiring_24h": sub_metrics["expiring_24h"] if sub_metrics else 0
            },
            "payments": {
                "count_24h": payment_metrics["payments_24h"] if payment_metrics else 0,
                "revenue_24h": payment_metrics["revenue_24h"] if payment_metrics else 0
            }
        }
        
    except Exception as e:
        logger.error(
            "health_metrics.failed",
            exception=e
        )
        return {}