import asyncio
import asyncpg
from asyncpg import Pool, UniqueViolationError
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta, timezone
import logging
from contextlib import asynccontextmanager
from app.config import settings

logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        self.pool: Optional[Pool] = None
    
    async def _init_connection(self, connection):
        """Initialize connection with JSON codec"""
        import json
        await connection.set_type_codec(
            'json',
            encoder=json.dumps,
            decoder=json.loads,
            schema='pg_catalog'
        )
        await connection.set_type_codec(
            'jsonb',
            encoder=json.dumps,
            decoder=json.loads,
            schema='pg_catalog'
        )
    
    async def connect(self):
        """Create connection pool with retry logic"""
        import json
        max_retries = 5
        retry_delay = 1
        
        for attempt in range(max_retries):
            try:
                self.pool = await asyncpg.create_pool(
                    settings.database_url,
                    min_size=2,
                    max_size=10,
                    max_queries=50000,
                    max_inactive_connection_lifetime=300,
                    command_timeout=60,
                    init=self._init_connection
                )
                logger.info("Database connection pool created")
                return
            except Exception as e:
                logger.error(f"Database connection attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    raise
    
    async def disconnect(self):
        """Close connection pool"""
        if self.pool:
            await self.pool.close()
            logger.info("Database connection pool closed")
    
    @asynccontextmanager
    async def acquire(self):
        """Acquire connection from pool"""
        async with self.pool.acquire() as conn:
            yield conn
    
    async def execute(self, query: str, *args):
        """Execute query without returning results"""
        async with self.acquire() as conn:
            return await conn.execute(query, *args)
    
    async def fetch(self, query: str, *args):
        """Fetch multiple rows"""
        async with self.acquire() as conn:
            return await conn.fetch(query, *args)
    
    async def fetchrow(self, query: str, *args):
        """Fetch single row"""
        async with self.acquire() as conn:
            return await conn.fetchrow(query, *args)
    
    async def fetchval(self, query: str, *args):
        """Fetch single value"""
        async with self.acquire() as conn:
            return await conn.fetchval(query, *args)
    
    # User management
    async def upsert_user(self, user_id: int, username: str = None, 
                         first_name: str = None, last_name: str = None,
                         language_code: str = 'en') -> dict:
        """Insert or update user"""
        return await self.fetchrow("""
            INSERT INTO users (user_id, username, first_name, last_name, language_code, last_seen_at)
            VALUES ($1, $2, $3, $4, $5, NOW())
            ON CONFLICT (user_id) DO UPDATE SET
                username = COALESCE(EXCLUDED.username, users.username),
                first_name = COALESCE(EXCLUDED.first_name, users.first_name),
                last_name = COALESCE(EXCLUDED.last_name, users.last_name),
                language_code = COALESCE(EXCLUDED.language_code, users.language_code),
                last_seen_at = NOW(),
                updated_at = NOW()
            RETURNING *
        """, user_id, username, first_name, last_name, language_code)
    
    # Subscription management
    async def get_active_subscription(self, user_id: int) -> Optional[dict]:
        """Get active or grace period subscription"""
        return await self.fetchrow("""
            SELECT * FROM subscriptions
            WHERE user_id = $1 
                AND status IN ('active', 'grace')
            ORDER BY expires_at DESC
            LIMIT 1
        """, user_id)
    
    async def has_active_access(self, user_id: int) -> bool:
        """Check if user has active access (including grace period)"""
        result = await self.fetchval("""
            SELECT EXISTS(
                SELECT 1 FROM subscriptions
                WHERE user_id = $1 
                    AND status IN ('active', 'grace')
                    AND (expires_at > NOW() OR grace_until > NOW())
            )
        """, user_id)
        return result
    
    # Payment management with idempotency
    async def insert_payment_idempotent(self, user_id: int, charge_id: str = None,
                                       star_tx_id: str = None, amount: int = 0,
                                       payment_type: str = 'one_time',
                                       is_recurring: bool = False,
                                       invoice_payload: str = None) -> Optional[dict]:
        """Insert payment with idempotency check"""
        try:
            return await self.fetchrow("""
                INSERT INTO payments (user_id, charge_id, star_tx_id, amount, 
                                    payment_type, is_recurring, invoice_payload)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING *
            """, user_id, charge_id, star_tx_id, amount, payment_type, is_recurring, invoice_payload)
        except UniqueViolationError:
            logger.info(f"Duplicate payment detected: charge_id={charge_id}, star_tx_id={star_tx_id}")
            return None
    
    async def process_subscription_payment(self, user_id: int, payment: dict,
                                          subscription_expiration: datetime = None,
                                          is_recurring: bool = False):
        """Process subscription payment and extend access"""
        async with self.acquire() as conn:
            async with conn.transaction(isolation='repeatable_read'):
                # Get or create subscription - First, check for existing active/grace subscription
                existing_sub = await conn.fetchrow("""
                    SELECT * FROM subscriptions 
                    WHERE user_id = $1 AND status IN ('active', 'grace')
                    ORDER BY expires_at DESC LIMIT 1
                """, user_id)
                
                if existing_sub:
                    # Update existing subscription
                    sub = await conn.fetchrow("""
                        UPDATE subscriptions 
                        SET status = 'active',
                            is_recurring = $2,
                            expires_at = GREATEST(
                                COALESCE(expires_at, NOW()),
                                $3
                            ),
                            grace_until = NULL,
                            grace_started_at = NULL,
                            updated_at = NOW()
                        WHERE subscription_id = $1
                        RETURNING *
                    """, existing_sub['subscription_id'], is_recurring,
                        subscription_expiration or datetime.now(timezone.utc) + timedelta(days=settings.plan_days))
                else:
                    # Create new subscription
                    sub = await conn.fetchrow("""
                        INSERT INTO subscriptions (user_id, status, is_recurring, expires_at)
                        VALUES ($1, 'active', $2, $3)
                        RETURNING *
                    """, user_id, is_recurring,
                        subscription_expiration or datetime.now(timezone.utc) + timedelta(days=settings.plan_days))
                
                # Update payment with subscription_id
                await conn.execute("""
                    UPDATE payments 
                    SET subscription_id = $1
                    WHERE payment_id = $2
                """, sub['subscription_id'], payment['payment_id'])
                
                # Store recurring charge_id if first recurring payment
                if is_recurring and payment.get('charge_id'):
                    await conn.execute("""
                        INSERT INTO recurring_subs (user_id, charge_id)
                        VALUES ($1, $2)
                        ON CONFLICT (user_id) DO UPDATE SET
                            charge_id = EXCLUDED.charge_id,
                            updated_at = NOW()
                    """, user_id, payment['charge_id'])
    
    # Whitelist management
    async def is_whitelisted(self, user_id: int) -> bool:
        """Check if user is whitelisted"""
        return await self.fetchval("""
            SELECT EXISTS(
                SELECT 1 FROM whitelist
                WHERE telegram_id = $1 
                    AND revoked_at IS NULL
            )
        """, user_id)
    
    async def burn_whitelist(self, user_id: int) -> bool:
        """Burn whitelist entry on join request (mark as used)"""
        result = await self.execute("""
            UPDATE whitelist 
            SET revoked_at = NOW(), note = COALESCE(note, '') || ' - Used for join'
            WHERE telegram_id = $1 AND revoked_at IS NULL
        """, user_id)
        return result != "UPDATE 0"
    
    async def revoke_whitelist(self, user_id: int):
        """Revoke whitelist on user leaving"""
        await self.execute("""
            UPDATE whitelist
            SET revoked_at = NOW(), note = COALESCE(note, '') || ' - User left group'
            WHERE telegram_id = $1 AND revoked_at IS NULL
        """, user_id)
    
    # Funnel events
    async def log_event(self, user_id: Optional[int], event_type: str, 
                       metadata: Dict[str, Any] = None):
        """Log funnel event"""
        import json
        metadata_json = json.dumps(metadata or {})
        await self.execute("""
            INSERT INTO funnel_events (user_id, event_type, metadata)
            VALUES ($1, $2, $3::jsonb)
        """, user_id, event_type, metadata_json)
    
    # Grace period transitions
    async def find_to_grace(self, now: datetime) -> List[dict]:
        """Find subscriptions to transition to grace"""
        return await self.fetch("""
            SELECT * FROM subscriptions
            WHERE status = 'active'
                AND expires_at < $1
                AND expires_at > $1 - INTERVAL '1 hour'
        """, now)
    
    async def set_grace(self, user_id: int, grace_until: datetime):
        """Set subscription to grace period"""
        await self.execute("""
            UPDATE subscriptions
            SET status = 'grace',
                grace_until = $2,
                grace_started_at = NOW()
            WHERE user_id = $1 AND status = 'active'
        """, user_id, grace_until)
    
    async def find_to_expire(self, now: datetime) -> List[dict]:
        """Find subscriptions to expire"""
        return await self.fetch("""
            SELECT * FROM subscriptions
            WHERE status = 'grace'
                AND grace_until < $1
        """, now)
    
    async def set_expired(self, user_id: int):
        """Set subscription as expired"""
        await self.execute("""
            UPDATE subscriptions
            SET status = 'expired'
            WHERE user_id = $1 AND status = 'grace'
        """, user_id)
    
    # Reconciliation
    async def get_reconcile_cursor(self) -> Optional[datetime]:
        """Get last reconciliation timestamp, initialize if missing"""
        cursor_time = await self.fetchval("""
            SELECT last_tx_at FROM star_tx_cursor WHERE id = 1
        """)
        
        if cursor_time is None:
            # Initialize cursor if missing
            from datetime import timedelta
            initial_time = datetime.now(timezone.utc) - timedelta(days=7)
            await self.execute("""
                INSERT INTO star_tx_cursor (id, last_tx_at, updated_at)
                VALUES (1, $1, NOW())
                ON CONFLICT (id) DO NOTHING
            """, initial_time)
            
            # Return the initialized value
            cursor_time = await self.fetchval("""
                SELECT last_tx_at FROM star_tx_cursor WHERE id = 1
            """)
        
        return cursor_time
    
    async def update_reconcile_cursor(self, last_tx_at: datetime, last_tx_id: str = None):
        """Update reconciliation cursor, create if missing"""
        await self.execute("""
            INSERT INTO star_tx_cursor (id, last_tx_at, last_tx_id, updated_at)
            VALUES (1, $1, $2, NOW())
            ON CONFLICT (id) DO UPDATE
            SET last_tx_at = EXCLUDED.last_tx_at,
                last_tx_id = EXCLUDED.last_tx_id,
                updated_at = NOW()
        """, last_tx_at, last_tx_id)
    
    # Stats for dashboard
    async def get_stats(self) -> dict:
        """Get statistics for dashboard"""
        stats = await self.fetchrow("""
            SELECT 
                (SELECT COUNT(*) FROM users) as total_users,
                (SELECT COUNT(*) FROM users WHERE status = 'active') as active_users,
                (SELECT COUNT(*) FROM subscriptions WHERE status = 'active') as active_subs,
                (SELECT COUNT(*) FROM subscriptions WHERE status = 'grace') as grace_subs,
                (SELECT COUNT(*) FROM subscriptions WHERE is_recurring = true AND status IN ('active', 'grace')) as recurring_subs,
                (SELECT COALESCE(SUM(amount), 0) FROM payments WHERE created_at >= NOW() - INTERVAL '30 days') as revenue_30d,
                (SELECT COALESCE(SUM(amount), 0) FROM payments WHERE created_at >= NOW() - INTERVAL '24 hours') as revenue_24h,
                (SELECT COUNT(*) FROM payments WHERE created_at >= NOW() - INTERVAL '24 hours') as payments_24h
        """)
        return dict(stats)
    
    # Notifications
    async def queue_notification(self, user_id: int, notification_type: str, metadata: dict = None):
        """Queue notification for sending"""
        await self.execute("""
            INSERT INTO notifications_queue (user_id, type, metadata)
            VALUES ($1, $2, $3)
        """, user_id, notification_type, metadata or {})
    
    async def get_pending_notifications(self, limit: int = 100) -> List[dict]:
        """Get pending notifications"""
        return await self.fetch("""
            SELECT * FROM notifications_queue
            WHERE sent = false
            ORDER BY created_at
            LIMIT $1
        """, limit)
    
    async def mark_notification_sent(self, notification_id: str):
        """Mark notification as sent"""
        await self.execute("""
            UPDATE notifications_queue
            SET sent = true, sent_at = NOW()
            WHERE notification_id = $1
        """, notification_id)

    
    # ============= Feature Flags =============
    async def get_feature_flag(self, key: str) -> Optional[bool]:
        """Get feature flag value"""
        result = await self.fetchrow("""
            SELECT bool_value FROM feature_flags WHERE key = $1
        """, key)
        return result['bool_value'] if result else None
    
    async def set_feature_flag(self, key: str, value: bool) -> bool:
        """Set feature flag value"""
        await self.execute("""
            INSERT INTO feature_flags (key, bool_value)
            VALUES ($1, $2)
            ON CONFLICT (key) DO UPDATE 
            SET bool_value = $2, updated_at = NOW()
        """, key, value)
        return True
    
    async def is_kicks_enabled(self) -> bool:
        """Check if kicks are enabled"""
        result = await self.get_feature_flag('kick_enabled')
        if result is not None:
            return result
        # Fallback to environment variable
        import os
        return os.getenv('KICK_ENABLED', 'false').lower() == 'true'
    
    # ============= Whitelist Functions =============
    async def grant_whitelist(self, user_id: int, source: str = 'manual', note: str = None) -> bool:
        """Grant whitelist to user (idempotent)"""
        try:
            await self.execute("""
                INSERT INTO whitelist (telegram_id, source, note, revoked_at)
                VALUES ($1, $2, $3, NULL)
                ON CONFLICT (telegram_id) DO UPDATE
                SET revoked_at = NULL,
                    source = COALESCE(whitelist.source, $2),
                    note = COALESCE($3, whitelist.note)
            """, user_id, source, note)
            logger.info(f"Granted whitelist to user {user_id} (source: {source})")
            return True
        except Exception as e:
            logger.error(f"Failed to grant whitelist to {user_id}: {e}")
            return False
    
    async def revoke_whitelist(self, user_id: int, reason: str = 'manual') -> bool:
        """Revoke whitelist from user"""
        try:
            result = await self.execute("""
                UPDATE whitelist 
                SET revoked_at = NOW(), note = COALESCE(note, '') || ' [Revoked: ' || $2 || ']'
                WHERE telegram_id = $1 AND revoked_at IS NULL
            """, user_id, reason)
            
            if result and 'UPDATE' in result:
                logger.info(f"Revoked whitelist from user {user_id} (reason: {reason})")
                # Track event
                await self.track_event('whitelist_burned', user_id, {'reason': reason})
            return True
        except Exception as e:
            logger.error(f"Failed to revoke whitelist from {user_id}: {e}")
            return False
    
    async def is_whitelisted(self, user_id: int) -> bool:
        """Check if user is whitelisted (active, not revoked)"""
        result = await self.fetchrow("""
            SELECT 1 FROM whitelist 
            WHERE telegram_id = $1 AND revoked_at IS NULL
        """, user_id)
        return result is not None
    
    async def get_whitelist_status(self, user_id: int) -> Optional[dict]:
        """Get detailed whitelist status for user"""
        return await self.fetchrow("""
            SELECT 
                telegram_id,
                granted_at,
                revoked_at,
                source,
                note,
                CASE WHEN revoked_at IS NULL THEN true ELSE false END as is_active
            FROM whitelist
            WHERE telegram_id = $1
        """, user_id)
    
    async def get_whitelist_stats(self) -> dict:
        """Get whitelist statistics"""
        result = await self.fetchrow("""
            SELECT * FROM v_whitelist_summary
        """)
        return dict(result) if result else {
            'total_whitelisted': 0,
            'revoked_count': 0,
            'subs_active_whitelisted': 0,
            'subs_expired_whitelisted': 0
        }
    
    async def bulk_grant_whitelist(self, user_ids: List[int], source: str = 'seed', note: str = None) -> int:
        """Bulk grant whitelist to multiple users"""
        count = 0
        for user_id in user_ids:
            if await self.grant_whitelist(user_id, source, note):
                count += 1
        return count
    
    async def get_expired_non_whitelisted(self, limit: int = 100) -> List[dict]:
        """Get expired users who are NOT whitelisted (for dry-run)"""
        return await self.fetch("""
            SELECT 
                s.user_id,
                u.username,
                u.first_name,
                u.last_name,
                s.expires_at,
                s.status,
                CASE 
                    WHEN s.status = 'expired' THEN 'subscription_expired'
                    WHEN s.status = 'grace' AND s.grace_ends_at < NOW() THEN 'grace_period_ended'
                    ELSE 'other'
                END as kick_reason
            FROM subscriptions s
            JOIN users u ON s.user_id = u.user_id
            WHERE s.status IN ('expired', 'grace')
            AND (s.status = 'expired' OR s.grace_ends_at < NOW())
            AND NOT EXISTS (
                SELECT 1 FROM whitelist w 
                WHERE w.telegram_id = s.user_id 
                AND w.revoked_at IS NULL
            )
            ORDER BY s.expires_at
            LIMIT $1
        """, limit)


# Global database instance
db = Database()

import asyncio