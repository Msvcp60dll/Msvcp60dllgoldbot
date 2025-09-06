"""
Resilience patterns for handling failures gracefully.
Includes circuit breaker, retry logic, and timeout protection.
"""

import asyncio
import time
import random
from enum import Enum
from typing import Any, Callable, Optional, TypeVar, Dict
from functools import wraps
from datetime import datetime, timedelta
import logging
from dataclasses import dataclass, field
from collections import deque

from app.logging_config import get_logger

logger = get_logger(__name__)

T = TypeVar('T')

class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, not allowing calls
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker"""
    failure_threshold: int = 5  # Failures before opening
    recovery_timeout: int = 30  # Seconds before trying again
    expected_exception: type = Exception  # Exceptions to catch
    success_threshold: int = 2  # Successes needed to close from half-open


@dataclass
class CircuitBreakerStats:
    """Statistics for circuit breaker monitoring"""
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    state_changes: list = field(default_factory=list)
    last_failure_time: Optional[float] = None
    consecutive_failures: int = 0
    consecutive_successes: int = 0


class CircuitBreaker:
    """Circuit breaker implementation for external service calls"""
    
    def __init__(self, name: str, config: Optional[CircuitBreakerConfig] = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitState.CLOSED
        self.stats = CircuitBreakerStats()
        self._state_changed_at = time.time()
        self._lock = asyncio.Lock()
        
        logger.info(
            "circuit_breaker.initialized",
            name=name,
            failure_threshold=self.config.failure_threshold,
            recovery_timeout=self.config.recovery_timeout
        )
    
    @property
    def is_open(self) -> bool:
        """Check if circuit is open (failing)"""
        return self.state == CircuitState.OPEN
    
    @property
    def is_closed(self) -> bool:
        """Check if circuit is closed (normal)"""
        return self.state == CircuitState.CLOSED
    
    @property
    def should_attempt_reset(self) -> bool:
        """Check if enough time has passed to try resetting"""
        if self.state != CircuitState.OPEN:
            return False
        
        elapsed = time.time() - self._state_changed_at
        return elapsed >= self.config.recovery_timeout
    
    async def _change_state(self, new_state: CircuitState):
        """Change circuit state with logging"""
        old_state = self.state
        self.state = new_state
        self._state_changed_at = time.time()
        
        self.stats.state_changes.append({
            "from": old_state.value,
            "to": new_state.value,
            "timestamp": datetime.now().isoformat()
        })
        
        logger.warning(
            "circuit_breaker.state_changed",
            name=self.name,
            old_state=old_state.value,
            new_state=new_state.value,
            consecutive_failures=self.stats.consecutive_failures
        )
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection"""
        async with self._lock:
            self.stats.total_calls += 1
            
            # Check if circuit should attempt reset
            if self.should_attempt_reset:
                await self._change_state(CircuitState.HALF_OPEN)
                logger.info(
                    "circuit_breaker.attempting_recovery",
                    name=self.name
                )
            
            # If circuit is open, fail fast
            if self.state == CircuitState.OPEN:
                logger.error(
                    "circuit_breaker.call_rejected",
                    name=self.name,
                    state=self.state.value
                )
                raise Exception(f"Circuit breaker {self.name} is OPEN")
            
            try:
                # Execute the function
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)
                
                # Success - update stats
                self.stats.successful_calls += 1
                self.stats.consecutive_failures = 0
                self.stats.consecutive_successes += 1
                
                # If half-open and enough successes, close circuit
                if self.state == CircuitState.HALF_OPEN:
                    if self.stats.consecutive_successes >= self.config.success_threshold:
                        await self._change_state(CircuitState.CLOSED)
                        logger.info(
                            "circuit_breaker.recovered",
                            name=self.name,
                            consecutive_successes=self.stats.consecutive_successes
                        )
                
                return result
                
            except self.config.expected_exception as e:
                # Failure - update stats
                self.stats.failed_calls += 1
                self.stats.consecutive_failures += 1
                self.stats.consecutive_successes = 0
                self.stats.last_failure_time = time.time()
                
                logger.error(
                    "circuit_breaker.call_failed",
                    name=self.name,
                    state=self.state.value,
                    consecutive_failures=self.stats.consecutive_failures,
                    exception=str(e)
                )
                
                # If failures exceed threshold, open circuit
                if self.stats.consecutive_failures >= self.config.failure_threshold:
                    if self.state != CircuitState.OPEN:
                        await self._change_state(CircuitState.OPEN)
                
                # If half-open and failed, reopen immediately
                elif self.state == CircuitState.HALF_OPEN:
                    await self._change_state(CircuitState.OPEN)
                
                raise
    
    def get_stats(self) -> dict:
        """Get circuit breaker statistics"""
        return {
            "name": self.name,
            "state": self.state.value,
            "total_calls": self.stats.total_calls,
            "successful_calls": self.stats.successful_calls,
            "failed_calls": self.stats.failed_calls,
            "failure_rate": (
                self.stats.failed_calls / self.stats.total_calls 
                if self.stats.total_calls > 0 else 0
            ),
            "consecutive_failures": self.stats.consecutive_failures,
            "consecutive_successes": self.stats.consecutive_successes,
            "last_failure_time": self.stats.last_failure_time,
            "state_changes": self.stats.state_changes[-5:]  # Last 5 changes
        }


# Global circuit breakers
circuit_breakers: Dict[str, CircuitBreaker] = {}


def get_circuit_breaker(
    name: str,
    config: Optional[CircuitBreakerConfig] = None
) -> CircuitBreaker:
    """Get or create a circuit breaker"""
    if name not in circuit_breakers:
        circuit_breakers[name] = CircuitBreaker(name, config)
    return circuit_breakers[name]


def with_circuit_breaker(
    name: str,
    failure_threshold: int = 5,
    recovery_timeout: int = 30,
    expected_exception: type = Exception
):
    """Decorator to add circuit breaker to a function"""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            config = CircuitBreakerConfig(
                failure_threshold=failure_threshold,
                recovery_timeout=recovery_timeout,
                expected_exception=expected_exception
            )
            breaker = get_circuit_breaker(name, config)
            return await breaker.call(func, *args, **kwargs)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            config = CircuitBreakerConfig(
                failure_threshold=failure_threshold,
                recovery_timeout=recovery_timeout,
                expected_exception=expected_exception
            )
            breaker = get_circuit_breaker(name, config)
            return asyncio.run(breaker.call(func, *args, **kwargs))
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator


class RetryConfig:
    """Configuration for retry logic"""
    def __init__(
        self,
        max_attempts: int = 3,
        initial_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
        exceptions: tuple = (Exception,)
    ):
        self.max_attempts = max_attempts
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.exceptions = exceptions


async def exponential_backoff_with_jitter(
    attempt: int,
    config: RetryConfig
) -> float:
    """Calculate delay with exponential backoff and jitter"""
    delay = min(
        config.initial_delay * (config.exponential_base ** attempt),
        config.max_delay
    )
    
    if config.jitter:
        # Add random jitter (0.5x to 1.5x the delay)
        delay = delay * (0.5 + random.random())
    
    return delay


def with_retry(
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    exceptions: tuple = (Exception,)
):
    """Decorator to add retry logic with exponential backoff"""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            config = RetryConfig(
                max_attempts=max_attempts,
                initial_delay=initial_delay,
                max_delay=max_delay,
                exponential_base=exponential_base,
                jitter=jitter,
                exceptions=exceptions
            )
            
            last_exception = None
            for attempt in range(config.max_attempts):
                try:
                    return await func(*args, **kwargs)
                except config.exceptions as e:
                    last_exception = e
                    
                    if attempt < config.max_attempts - 1:
                        delay = await exponential_backoff_with_jitter(attempt, config)
                        logger.warning(
                            "retry.attempt_failed",
                            function=func.__name__,
                            attempt=attempt + 1,
                            max_attempts=config.max_attempts,
                            delay=round(delay, 2),
                            exception=str(e)
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error(
                            "retry.all_attempts_failed",
                            function=func.__name__,
                            attempts=config.max_attempts,
                            exception=str(e)
                        )
            
            if last_exception:
                raise last_exception
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            config = RetryConfig(
                max_attempts=max_attempts,
                initial_delay=initial_delay,
                max_delay=max_delay,
                exponential_base=exponential_base,
                jitter=jitter,
                exceptions=exceptions
            )
            
            last_exception = None
            for attempt in range(config.max_attempts):
                try:
                    return func(*args, **kwargs)
                except config.exceptions as e:
                    last_exception = e
                    
                    if attempt < config.max_attempts - 1:
                        delay = asyncio.run(
                            exponential_backoff_with_jitter(attempt, config)
                        )
                        logger.warning(
                            "retry.attempt_failed",
                            function=func.__name__,
                            attempt=attempt + 1,
                            max_attempts=config.max_attempts,
                            delay=round(delay, 2),
                            exception=str(e)
                        )
                        time.sleep(delay)
                    else:
                        logger.error(
                            "retry.all_attempts_failed",
                            function=func.__name__,
                            attempts=config.max_attempts,
                            exception=str(e)
                        )
            
            if last_exception:
                raise last_exception
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator


def with_timeout(seconds: float):
    """Decorator to add timeout protection"""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await asyncio.wait_for(
                    func(*args, **kwargs),
                    timeout=seconds
                )
            except asyncio.TimeoutError:
                logger.error(
                    "timeout.exceeded",
                    function=func.__name__,
                    timeout_seconds=seconds
                )
                raise TimeoutError(f"Function {func.__name__} exceeded timeout of {seconds}s")
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # For sync functions, we can't easily add timeout
            # Log a warning and execute normally
            logger.warning(
                "timeout.not_supported_for_sync",
                function=func.__name__
            )
            return func(*args, **kwargs)
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator


class OperationQueue:
    """Queue for retrying failed critical operations"""
    
    def __init__(self, max_size: int = 1000):
        self.queue = deque(maxlen=max_size)
        self.processing = False
        self._lock = asyncio.Lock()
        
        logger.info(
            "operation_queue.initialized",
            max_size=max_size
        )
    
    async def add(self, operation: dict):
        """Add failed operation to retry queue"""
        async with self._lock:
            self.queue.append({
                **operation,
                "queued_at": time.time(),
                "attempts": 0
            })
            
            logger.info(
                "operation_queue.operation_added",
                operation_type=operation.get("type"),
                queue_size=len(self.queue)
            )
    
    async def process(self, handler: Callable):
        """Process queued operations"""
        if self.processing:
            logger.warning("operation_queue.already_processing")
            return
        
        self.processing = True
        processed = 0
        failed = 0
        
        try:
            while self.queue:
                async with self._lock:
                    if not self.queue:
                        break
                    operation = self.queue.popleft()
                
                operation["attempts"] += 1
                
                try:
                    await handler(operation)
                    processed += 1
                    
                    logger.info(
                        "operation_queue.operation_processed",
                        operation_type=operation.get("type"),
                        attempts=operation["attempts"]
                    )
                    
                except Exception as e:
                    failed += 1
                    
                    # Re-queue if not too many attempts
                    if operation["attempts"] < 3:
                        async with self._lock:
                            self.queue.append(operation)
                        
                        logger.warning(
                            "operation_queue.operation_requeued",
                            operation_type=operation.get("type"),
                            attempts=operation["attempts"],
                            exception=str(e)
                        )
                    else:
                        logger.error(
                            "operation_queue.operation_abandoned",
                            operation_type=operation.get("type"),
                            attempts=operation["attempts"],
                            exception=str(e)
                        )
        
        finally:
            self.processing = False
            
            logger.info(
                "operation_queue.processing_completed",
                processed=processed,
                failed=failed,
                remaining=len(self.queue)
            )
    
    def get_stats(self) -> dict:
        """Get queue statistics"""
        return {
            "queue_size": len(self.queue),
            "processing": self.processing,
            "oldest_operation": (
                time.time() - self.queue[0]["queued_at"]
                if self.queue else None
            )
        }


# Global operation queue
operation_queue = OperationQueue()


async def queue_critical_operation(
    operation_type: str,
    data: dict,
    retry_handler: Optional[Callable] = None
):
    """Queue a critical operation for retry"""
    await operation_queue.add({
        "type": operation_type,
        "data": data,
        "handler": retry_handler,
        "timestamp": datetime.now().isoformat()
    })


def get_resilience_stats() -> dict:
    """Get overall resilience statistics"""
    return {
        "circuit_breakers": {
            name: breaker.get_stats()
            for name, breaker in circuit_breakers.items()
        },
        "operation_queue": operation_queue.get_stats(),
        "timestamp": datetime.now().isoformat()
    }