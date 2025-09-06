"""
Resilient Telegram API operations with circuit breaker and retry logic.
"""

from typing import Optional, List, Union
from aiogram import Bot
from aiogram.types import (
    InlineKeyboardMarkup,
    Message,
    ChatJoinRequest
)
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import (
    TelegramAPIError,
    TelegramNetworkError,
    TelegramRetryAfter,
    TelegramBadRequest
)

from app.resilience import (
    with_circuit_breaker,
    with_retry,
    with_timeout,
    queue_critical_operation
)
from app.logging_config import get_logger

logger = get_logger(__name__)


class ResilientTelegramBot:
    """Wrapper for Telegram bot with resilience patterns"""
    
    def __init__(self, bot: Bot):
        self.bot = bot
    
    @with_circuit_breaker(
        name="telegram_send_message",
        failure_threshold=5,
        recovery_timeout=30,
        expected_exception=(TelegramAPIError, TelegramNetworkError)
    )
    @with_retry(
        max_attempts=3,
        initial_delay=1.0,
        max_delay=10.0,
        jitter=True,
        exceptions=(TelegramNetworkError, TelegramRetryAfter)
    )
    @with_timeout(10.0)
    async def send_message(
        self,
        chat_id: int,
        text: str,
        parse_mode: Optional[str] = None,
        reply_markup: Optional[InlineKeyboardMarkup] = None,
        disable_notification: bool = False
    ) -> Optional[Message]:
        """Send message with resilience"""
        try:
            return await self.bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode=parse_mode,
                reply_markup=reply_markup,
                disable_notification=disable_notification
            )
        except TelegramBadRequest as e:
            # Log but don't retry bad requests
            logger.error(
                "telegram.send_message_bad_request",
                chat_id=chat_id,
                error=str(e)
            )
            return None
        except TelegramRetryAfter as e:
            # Telegram asks us to wait
            logger.warning(
                "telegram.rate_limited",
                retry_after=e.retry_after,
                chat_id=chat_id
            )
            raise  # Let retry decorator handle this
        except Exception as e:
            logger.error(
                "telegram.send_message_failed",
                chat_id=chat_id,
                exception=e
            )
            
            # Queue for retry if critical
            await queue_critical_operation(
                operation_type="send_message",
                data={
                    "chat_id": chat_id,
                    "text": text[:100],  # Truncate for logging
                    "parse_mode": parse_mode
                }
            )
            raise
    
    @with_circuit_breaker(
        name="telegram_approve_join",
        failure_threshold=5,
        recovery_timeout=30,
        expected_exception=(TelegramAPIError, TelegramNetworkError)
    )
    @with_retry(
        max_attempts=3,
        initial_delay=1.0,
        max_delay=10.0,
        jitter=True,
        exceptions=(TelegramNetworkError, TelegramRetryAfter)
    )
    @with_timeout(10.0)
    async def approve_chat_join_request(
        self,
        chat_id: int,
        user_id: int
    ) -> bool:
        """Approve join request with resilience"""
        try:
            result = await self.bot.approve_chat_join_request(
                chat_id=chat_id,
                user_id=user_id
            )
            
            logger.info(
                "telegram.join_request_approved",
                chat_id=chat_id,
                user_id=user_id
            )
            
            return result
            
        except TelegramBadRequest as e:
            if "USER_ALREADY_PARTICIPANT" in str(e):
                # User is already in the chat
                logger.info(
                    "telegram.user_already_member",
                    chat_id=chat_id,
                    user_id=user_id
                )
                return True
            
            logger.error(
                "telegram.approve_join_bad_request",
                chat_id=chat_id,
                user_id=user_id,
                error=str(e)
            )
            return False
            
        except Exception as e:
            logger.error(
                "telegram.approve_join_failed",
                chat_id=chat_id,
                user_id=user_id,
                exception=e
            )
            
            # Queue for retry
            await queue_critical_operation(
                operation_type="approve_join",
                data={
                    "chat_id": chat_id,
                    "user_id": user_id
                }
            )
            raise
    
    @with_circuit_breaker(
        name="telegram_decline_join",
        failure_threshold=5,
        recovery_timeout=30,
        expected_exception=(TelegramAPIError, TelegramNetworkError)
    )
    @with_retry(
        max_attempts=2,  # Less retries for declines
        initial_delay=1.0,
        max_delay=5.0,
        jitter=True,
        exceptions=(TelegramNetworkError,)
    )
    @with_timeout(10.0)
    async def decline_chat_join_request(
        self,
        chat_id: int,
        user_id: int
    ) -> bool:
        """Decline join request with resilience"""
        try:
            result = await self.bot.decline_chat_join_request(
                chat_id=chat_id,
                user_id=user_id
            )
            
            logger.info(
                "telegram.join_request_declined",
                chat_id=chat_id,
                user_id=user_id
            )
            
            return result
            
        except TelegramBadRequest as e:
            # Log but don't retry bad requests
            logger.error(
                "telegram.decline_join_bad_request",
                chat_id=chat_id,
                user_id=user_id,
                error=str(e)
            )
            return False
            
        except Exception as e:
            logger.error(
                "telegram.decline_join_failed",
                chat_id=chat_id,
                user_id=user_id,
                exception=e
            )
            # Don't queue declines for retry
            return False
    
    @with_circuit_breaker(
        name="telegram_get_member",
        failure_threshold=10,  # Higher threshold for read operations
        recovery_timeout=20,
        expected_exception=(TelegramAPIError, TelegramNetworkError)
    )
    @with_retry(
        max_attempts=2,
        initial_delay=0.5,
        max_delay=3.0,
        jitter=True,
        exceptions=(TelegramNetworkError,)
    )
    @with_timeout(5.0)
    async def get_chat_member(
        self,
        chat_id: int,
        user_id: int
    ) -> Optional[ChatMemberStatus]:
        """Get chat member status with resilience"""
        try:
            member = await self.bot.get_chat_member(
                chat_id=chat_id,
                user_id=user_id
            )
            return member.status if member else None
            
        except TelegramBadRequest as e:
            if "user not found" in str(e).lower():
                return None
            
            logger.error(
                "telegram.get_member_bad_request",
                chat_id=chat_id,
                user_id=user_id,
                error=str(e)
            )
            return None
            
        except Exception as e:
            logger.error(
                "telegram.get_member_failed",
                chat_id=chat_id,
                user_id=user_id,
                exception=e
            )
            return None
    
    @with_circuit_breaker(
        name="telegram_send_invoice",
        failure_threshold=3,  # Lower threshold for payment operations
        recovery_timeout=60,  # Longer recovery for payments
        expected_exception=(TelegramAPIError, TelegramNetworkError)
    )
    @with_retry(
        max_attempts=3,
        initial_delay=2.0,
        max_delay=15.0,
        jitter=True,
        exceptions=(TelegramNetworkError, TelegramRetryAfter)
    )
    @with_timeout(15.0)
    async def send_invoice(
        self,
        chat_id: int,
        title: str,
        description: str,
        payload: str,
        currency: str,
        prices: list,
        **kwargs
    ) -> Optional[Message]:
        """Send invoice with resilience"""
        try:
            return await self.bot.send_invoice(
                chat_id=chat_id,
                title=title,
                description=description,
                payload=payload,
                currency=currency,
                prices=prices,
                **kwargs
            )
        except TelegramBadRequest as e:
            logger.error(
                "telegram.send_invoice_bad_request",
                chat_id=chat_id,
                error=str(e)
            )
            return None
        except Exception as e:
            logger.error(
                "telegram.send_invoice_failed",
                chat_id=chat_id,
                exception=e
            )
            
            # Queue critical payment operation
            await queue_critical_operation(
                operation_type="send_invoice",
                data={
                    "chat_id": chat_id,
                    "title": title,
                    "payload": payload
                }
            )
            raise
    
    async def send_message_with_fallback(
        self,
        chat_id: int,
        text: str,
        fallback_text: Optional[str] = None,
        **kwargs
    ) -> bool:
        """Send message with graceful fallback"""
        try:
            # Try to send the full message
            result = await self.send_message(
                chat_id=chat_id,
                text=text,
                **kwargs
            )
            return result is not None
            
        except Exception as e:
            logger.warning(
                "telegram.send_message_fallback",
                chat_id=chat_id,
                exception=e
            )
            
            # Try fallback message if provided
            if fallback_text:
                try:
                    result = await self.send_message(
                        chat_id=chat_id,
                        text=fallback_text,
                        parse_mode=None  # Remove formatting
                    )
                    return result is not None
                except Exception as fallback_error:
                    logger.error(
                        "telegram.send_message_fallback_failed",
                        chat_id=chat_id,
                        exception=fallback_error
                    )
            
            return False
    
    async def batch_send_messages(
        self,
        messages: List[dict],
        continue_on_error: bool = True
    ) -> dict:
        """Send multiple messages with resilience"""
        results = {
            "sent": 0,
            "failed": 0,
            "errors": []
        }
        
        for msg in messages:
            try:
                await self.send_message(**msg)
                results["sent"] += 1
                
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({
                    "chat_id": msg.get("chat_id"),
                    "error": str(e)
                })
                
                if not continue_on_error:
                    break
        
        logger.info(
            "telegram.batch_send_completed",
            sent=results["sent"],
            failed=results["failed"]
        )
        
        return results


# Helper function to create resilient bot
def create_resilient_bot(bot: Bot) -> ResilientTelegramBot:
    """Create a resilient bot wrapper"""
    return ResilientTelegramBot(bot)