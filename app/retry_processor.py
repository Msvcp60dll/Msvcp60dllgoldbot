"""
Retry queue processor for failed critical operations.
Processes queued operations with exponential backoff.
"""

import asyncio
import time
from typing import Optional, Callable, Dict, Any
from datetime import datetime, timedelta

from app.db import db
from app.bot import bot
from app.telegram_resilient import create_resilient_bot
from app.resilience import operation_queue
from app.logging_config import get_logger
from app.config import settings

logger = get_logger(__name__)


class RetryProcessor:
    """Processes failed operations from the retry queue"""
    
    def __init__(self, interval_seconds: int = 60):
        self.interval_seconds = interval_seconds
        self.running = False
        self.resilient_bot = None
        self._handlers: Dict[str, Callable] = {}
        
        # Register default handlers
        self._register_default_handlers()
    
    def _register_default_handlers(self):
        """Register default operation handlers"""
        self._handlers = {
            "send_message": self._retry_send_message,
            "approve_join": self._retry_approve_join,
            "send_invoice": self._retry_send_invoice,
            "process_payment": self._retry_process_payment,
            "grant_access": self._retry_grant_access
        }
    
    async def _retry_send_message(self, operation: dict) -> bool:
        """Retry sending a message"""
        try:
            data = operation["data"]
            await self.resilient_bot.send_message(
                chat_id=data["chat_id"],
                text=data["text"],
                parse_mode=data.get("parse_mode")
            )
            
            logger.info(
                "retry_processor.message_sent",
                chat_id=data["chat_id"],
                attempts=operation["attempts"]
            )
            return True
            
        except Exception as e:
            logger.error(
                "retry_processor.message_failed",
                chat_id=data.get("chat_id"),
                exception=e,
                attempts=operation["attempts"]
            )
            return False
    
    async def _retry_approve_join(self, operation: dict) -> bool:
        """Retry approving a join request"""
        try:
            data = operation["data"]
            
            # Check if still pending approval
            subscription = await db.fetch_one("""
                SELECT status, expires_at
                FROM subscriptions
                WHERE user_id = $1
            """, data["user_id"])
            
            if not subscription or subscription["status"] != "active":
                logger.warning(
                    "retry_processor.join_skipped",
                    user_id=data["user_id"],
                    reason="No active subscription"
                )
                return True  # Don't retry
            
            # Try to approve
            result = await self.resilient_bot.approve_chat_join_request(
                chat_id=data["chat_id"],
                user_id=data["user_id"]
            )
            
            if result:
                await db.log_event(data["user_id"], "retry_approve_ok", {
                    "attempts": operation["attempts"]
                })
                
                logger.info(
                    "retry_processor.join_approved",
                    user_id=data["user_id"],
                    attempts=operation["attempts"]
                )
            
            return result
            
        except Exception as e:
            logger.error(
                "retry_processor.join_failed",
                user_id=data.get("user_id"),
                exception=e,
                attempts=operation["attempts"]
            )
            return False
    
    async def _retry_send_invoice(self, operation: dict) -> bool:
        """Retry sending an invoice"""
        try:
            data = operation["data"]
            
            # Check if user already paid
            payment = await db.fetch_one("""
                SELECT id FROM payments
                WHERE user_id = $1
                AND created_at > NOW() - INTERVAL '1 hour'
            """, data["chat_id"])
            
            if payment:
                logger.info(
                    "retry_processor.invoice_skipped",
                    user_id=data["chat_id"],
                    reason="Recent payment exists"
                )
                return True  # Don't retry
            
            # Try to send invoice
            await self.resilient_bot.send_invoice(
                chat_id=data["chat_id"],
                title=data["title"],
                description="Monthly subscription to the group",
                payload=data["payload"],
                currency="XTR",
                prices=[{"amount": settings.sub_stars, "label": "Monthly access"}]
            )
            
            logger.info(
                "retry_processor.invoice_sent",
                user_id=data["chat_id"],
                attempts=operation["attempts"]
            )
            return True
            
        except Exception as e:
            logger.error(
                "retry_processor.invoice_failed",
                user_id=data.get("chat_id"),
                exception=e,
                attempts=operation["attempts"]
            )
            return False
    
    async def _retry_process_payment(self, operation: dict) -> bool:
        """Retry processing a failed payment"""
        try:
            data = operation["data"]
            
            # Check if already processed
            existing = await db.fetch_one("""
                SELECT id FROM payments
                WHERE charge_id = $1
            """, data["charge_id"])
            
            if existing:
                logger.info(
                    "retry_processor.payment_skipped",
                    charge_id=data["charge_id"],
                    reason="Already processed"
                )
                return True
            
            # Process payment
            await db.execute("""
                INSERT INTO payments (
                    user_id, amount, charge_id, payment_type, created_at
                ) VALUES ($1, $2, $3, $4, NOW())
                ON CONFLICT (charge_id) DO NOTHING
            """, data["user_id"], data["amount"], data["charge_id"], data.get("payment_type", "one_time"))
            
            # Update subscription
            expires_at = datetime.now() + timedelta(days=settings.plan_days)
            await db.execute("""
                INSERT INTO subscriptions (user_id, status, expires_at, is_recurring)
                VALUES ($1, 'active', $2, $3)
                ON CONFLICT (user_id) DO UPDATE SET
                    status = 'active',
                    expires_at = GREATEST(subscriptions.expires_at, EXCLUDED.expires_at),
                    updated_at = NOW()
            """, data["user_id"], expires_at, data.get("is_recurring", False))
            
            logger.info(
                "retry_processor.payment_processed",
                user_id=data["user_id"],
                charge_id=data["charge_id"],
                attempts=operation["attempts"]
            )
            return True
            
        except Exception as e:
            logger.error(
                "retry_processor.payment_failed",
                charge_id=data.get("charge_id"),
                exception=e,
                attempts=operation["attempts"]
            )
            return False
    
    async def _retry_grant_access(self, operation: dict) -> bool:
        """Retry granting access to a user"""
        try:
            data = operation["data"]
            user_id = data["user_id"]
            
            # Check subscription
            subscription = await db.fetch_one("""
                SELECT status FROM subscriptions
                WHERE user_id = $1
            """, user_id)
            
            if not subscription or subscription["status"] != "active":
                logger.warning(
                    "retry_processor.access_skipped",
                    user_id=user_id,
                    reason="No active subscription"
                )
                return True
            
            # Try to approve if there's a pending request
            if data.get("chat_id") and data.get("approve"):
                await self.resilient_bot.approve_chat_join_request(
                    chat_id=data["chat_id"],
                    user_id=user_id
                )
            
            # Send success message
            await self.resilient_bot.send_message_with_fallback(
                chat_id=user_id,
                text="✅ Your access has been granted! Use /enter to join the group.",
                fallback_text="Access granted! Use /enter to join."
            )
            
            logger.info(
                "retry_processor.access_granted",
                user_id=user_id,
                attempts=operation["attempts"]
            )
            return True
            
        except Exception as e:
            logger.error(
                "retry_processor.access_failed",
                user_id=data.get("user_id"),
                exception=e,
                attempts=operation["attempts"]
            )
            return False
    
    async def process_operation(self, operation: dict) -> bool:
        """Process a single operation"""
        operation_type = operation.get("type")
        
        # Get handler
        handler = self._handlers.get(operation_type)
        if not handler:
            logger.error(
                "retry_processor.unknown_operation",
                operation_type=operation_type
            )
            return False
        
        # Execute handler
        try:
            return await handler(operation)
        except Exception as e:
            logger.error(
                "retry_processor.handler_error",
                operation_type=operation_type,
                exception=e
            )
            return False
    
    async def process_database_queue(self):
        """Process operations from database queue"""
        try:
            # Get pending operations from database
            operations = await db.fetch("""
                SELECT * FROM failed_payments_queue
                WHERE retry_count < 3
                AND last_retry < NOW() - INTERVAL '5 minutes'
                ORDER BY created_at
                LIMIT 10
            """)
            
            for op in operations:
                try:
                    # Process the operation
                    success = await self._retry_process_payment({
                        "data": {
                            "user_id": op["user_id"],
                            "charge_id": op["charge_id"],
                            "amount": op.get("amount", settings.sub_stars)
                        },
                        "attempts": op["retry_count"] + 1
                    })
                    
                    if success:
                        # Remove from queue
                        await db.execute("""
                            DELETE FROM failed_payments_queue
                            WHERE id = $1
                        """, op["id"])
                        
                        logger.info(
                            "retry_processor.db_queue_success",
                            queue_id=op["id"],
                            user_id=op["user_id"]
                        )
                    else:
                        # Update retry count
                        await db.execute("""
                            UPDATE failed_payments_queue
                            SET retry_count = retry_count + 1,
                                last_retry = NOW()
                            WHERE id = $1
                        """, op["id"])
                        
                except Exception as e:
                    logger.error(
                        "retry_processor.db_queue_error",
                        queue_id=op["id"],
                        exception=e
                    )
            
        except Exception as e:
            logger.error(
                "retry_processor.db_queue_failed",
                exception=e
            )
    
    async def run(self):
        """Run the retry processor"""
        if self.running:
            logger.warning("retry_processor.already_running")
            return
        
        self.running = True
        self.resilient_bot = create_resilient_bot(bot)
        
        logger.info(
            "retry_processor.started",
            interval_seconds=self.interval_seconds
        )
        
        while self.running:
            try:
                # Process in-memory queue
                await operation_queue.process(self.process_operation)
                
                # Process database queue
                await self.process_database_queue()
                
                # Wait before next cycle
                await asyncio.sleep(self.interval_seconds)
                
            except Exception as e:
                logger.error(
                    "retry_processor.cycle_error",
                    exception=e
                )
                await asyncio.sleep(self.interval_seconds)
    
    def stop(self):
        """Stop the retry processor"""
        self.running = False
        logger.info("retry_processor.stopped")


# Global retry processor instance
retry_processor = RetryProcessor()


async def start_retry_processor():
    """Start the global retry processor"""
    asyncio.create_task(retry_processor.run())
    logger.info("retry_processor.task_created")


def stop_retry_processor():
    """Stop the global retry processor"""
    retry_processor.stop()