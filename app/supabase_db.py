"""
Supabase database layer using REST API instead of direct PostgreSQL connection.
This avoids the need for database password and uses the service key instead.
"""

import httpx
import json
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta, timezone
import logging
from app.config import settings

logger = logging.getLogger(__name__)

class SupabaseDB:
    def __init__(self):
        self.base_url = f"{settings.supabase_url}/rest/v1"
        self.headers = {
            "apikey": settings.supabase_service_key,
            "Authorization": f"Bearer {settings.supabase_service_key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation"
        }
        self.client = httpx.AsyncClient(headers=self.headers, timeout=30.0)
    
    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()
    
    async def _request(self, method: str, endpoint: str, **kwargs) -> Any:
        """Make HTTP request to Supabase"""
        url = f"{self.base_url}/{endpoint}"
        response = await self.client.request(method, url, **kwargs)
        
        if response.status_code >= 400:
            logger.error(f"Supabase error: {response.status_code} - {response.text}")
            raise Exception(f"Supabase error: {response.text}")
        
        if response.text:
            return response.json()
        return None
    
    # User management
    async def upsert_user(self, user_id: int, username: str = None, 
                         first_name: str = None, last_name: str = None,
                         language_code: str = 'en') -> dict:
        """Insert or update user"""
        data = {
            "user_id": user_id,
            "username": username,
            "first_name": first_name,
            "last_name": last_name,
            "language_code": language_code,
            "last_seen_at": datetime.now(timezone.utc).isoformat()
        }
        
        result = await self._request(
            "POST", 
            "users",
            json=data,
            headers={**self.headers, "Prefer": "resolution=merge-duplicates,return=representation"}
        )
        
        return result[0] if result else {}
    
    # Subscription management
    async def get_active_subscription(self, user_id: int) -> Optional[dict]:
        """Get active or grace period subscription"""
        result = await self._request(
            "GET",
            f"subscriptions?user_id=eq.{user_id}&status=in.(active,grace)&order=expires_at.desc&limit=1"
        )
        return result[0] if result else None
    
    async def has_active_access(self, user_id: int) -> bool:
        """Check if user has active access"""
        sub = await self.get_active_subscription(user_id)
        if not sub:
            return False
        
        now = datetime.now(timezone.utc)
        expires_at = datetime.fromisoformat(sub['expires_at'].replace('Z', '+00:00')) if sub.get('expires_at') else None
        grace_until = datetime.fromisoformat(sub['grace_until'].replace('Z', '+00:00')) if sub.get('grace_until') else None
        
        return (expires_at and expires_at > now) or (grace_until and grace_until > now)
    
    # Payment management
    async def insert_payment_idempotent(self, user_id: int, charge_id: str = None,
                                       star_tx_id: str = None, amount: int = 0,
                                       payment_type: str = 'one_time',
                                       is_recurring: bool = False,
                                       invoice_payload: str = None) -> Optional[dict]:
        """Insert payment with idempotency check"""
        data = {
            "user_id": user_id,
            "charge_id": charge_id,
            "star_tx_id": star_tx_id,
            "amount": amount,
            "payment_type": payment_type,
            "is_recurring": is_recurring,
            "invoice_payload": invoice_payload
        }
        
        # First check if payment exists
        if charge_id:
            existing = await self._request(
                "GET",
                f"payments?charge_id=eq.{charge_id}"
            )
            if existing:
                logger.info(f"Duplicate payment detected: charge_id={charge_id}")
                return None
        
        if star_tx_id:
            existing = await self._request(
                "GET",
                f"payments?star_tx_id=eq.{star_tx_id}"
            )
            if existing:
                logger.info(f"Duplicate payment detected: star_tx_id={star_tx_id}")
                return None
        
        # Insert new payment
        result = await self._request(
            "POST",
            "payments",
            json=data
        )
        
        return result[0] if result else None
    
    async def process_subscription_payment(self, user_id: int, payment: dict,
                                          subscription_expiration: datetime = None,
                                          is_recurring: bool = False):
        """Process subscription payment and extend access"""
        
        # Get existing subscription
        existing_sub = await self.get_active_subscription(user_id)
        
        if existing_sub:
            # Update existing subscription
            new_expires = subscription_expiration or datetime.now(timezone.utc) + timedelta(days=settings.plan_days)
            
            if existing_sub.get('expires_at'):
                current_expires = datetime.fromisoformat(existing_sub['expires_at'].replace('Z', '+00:00'))
                new_expires = max(current_expires, new_expires)
            
            await self._request(
                "PATCH",
                f"subscriptions?subscription_id=eq.{existing_sub['subscription_id']}",
                json={
                    "status": "active",
                    "is_recurring": is_recurring,
                    "expires_at": new_expires.isoformat(),
                    "grace_until": None,
                    "grace_started_at": None
                }
            )
        else:
            # Create new subscription
            await self._request(
                "POST",
                "subscriptions",
                json={
                    "user_id": user_id,
                    "status": "active",
                    "is_recurring": is_recurring,
                    "expires_at": (subscription_expiration or datetime.now(timezone.utc) + timedelta(days=settings.plan_days)).isoformat()
                }
            )
        
        # Store recurring charge_id if first recurring payment
        if is_recurring and payment.get('charge_id'):
            # Check if exists
            existing_recurring = await self._request(
                "GET",
                f"recurring_subs?user_id=eq.{user_id}"
            )
            
            if existing_recurring:
                await self._request(
                    "PATCH",
                    f"recurring_subs?user_id=eq.{user_id}",
                    json={"charge_id": payment['charge_id']}
                )
            else:
                await self._request(
                    "POST",
                    "recurring_subs",
                    json={"user_id": user_id, "charge_id": payment['charge_id']}
                )
    
    # Whitelist management
    async def is_whitelisted(self, user_id: int) -> bool:
        """Check if user is whitelisted"""
        result = await self._request(
            "GET",
            f"whitelist?user_id=eq.{user_id}&burned_at=is.null"
        )
        return bool(result)
    
    async def burn_whitelist(self, user_id: int) -> bool:
        """Burn whitelist entry on join request"""
        result = await self._request(
            "PATCH",
            f"whitelist?user_id=eq.{user_id}&burned_at=is.null",
            json={"burned_at": datetime.now(timezone.utc).isoformat()}
        )
        return bool(result)
    
    async def revoke_whitelist(self, user_id: int):
        """Revoke whitelist on user leaving"""
        await self._request(
            "DELETE",
            f"whitelist?user_id=eq.{user_id}&burned_at=is.null"
        )
    
    # Funnel events
    async def log_event(self, user_id: Optional[int], event_type: str, 
                       metadata: Dict[str, Any] = None):
        """Log funnel event"""
        await self._request(
            "POST",
            "funnel_events",
            json={
                "user_id": user_id,
                "event_type": event_type,
                "metadata": metadata or {}
            }
        )
    
    # Simple query methods for other operations
    async def execute(self, query: str, *args):
        """Not implemented for REST API - use specific methods instead"""
        logger.warning("Direct SQL execution not available with REST API")
        return None
    
    async def fetch(self, endpoint: str, filters: dict = None):
        """Generic fetch method"""
        query_params = []
        if filters:
            for key, value in filters.items():
                query_params.append(f"{key}={value}")
        
        url_suffix = "?" + "&".join(query_params) if query_params else ""
        return await self._request("GET", f"{endpoint}{url_suffix}")
    
    async def fetchrow(self, endpoint: str, filters: dict = None):
        """Fetch single row"""
        result = await self.fetch(endpoint, filters)
        return result[0] if result else None
    
    async def fetchval(self, endpoint: str, column: str, filters: dict = None):
        """Fetch single value"""
        row = await self.fetchrow(endpoint, filters)
        return row.get(column) if row else None
    
    # Stats for dashboard
    async def get_stats(self) -> dict:
        """Get statistics for dashboard"""
        # Get counts from different tables
        users = await self._request("GET", "users?select=user_id")
        active_users = await self._request("GET", "users?status=eq.active&select=user_id")
        active_subs = await self._request("GET", "subscriptions?status=eq.active&select=subscription_id")
        grace_subs = await self._request("GET", "subscriptions?status=eq.grace&select=subscription_id")
        recurring_subs = await self._request("GET", "subscriptions?is_recurring=eq.true&status=in.(active,grace)&select=subscription_id")
        
        # Get payment stats
        now = datetime.now(timezone.utc)
        day_ago = now - timedelta(days=1)
        month_ago = now - timedelta(days=30)
        
        payments_24h = await self._request(
            "GET",
            f"payments?created_at=gte.{day_ago.isoformat()}&select=amount"
        )
        
        payments_30d = await self._request(
            "GET",
            f"payments?created_at=gte.{month_ago.isoformat()}&select=amount"
        )
        
        revenue_24h = sum(p.get('amount', 0) for p in payments_24h)
        revenue_30d = sum(p.get('amount', 0) for p in payments_30d)
        
        return {
            "total_users": len(users),
            "active_users": len(active_users),
            "active_subs": len(active_subs),
            "grace_subs": len(grace_subs),
            "recurring_subs": len(recurring_subs),
            "revenue_24h": revenue_24h,
            "revenue_30d": revenue_30d,
            "payments_24h": len(payments_24h)
        }
    
    # Initialize database schema
    async def init_schema(self):
        """Initialize database schema using Supabase SQL editor"""
        logger.info("Database schema should be initialized via Supabase Dashboard SQL editor")
        logger.info("Copy the contents of app/models.sql and run in Supabase SQL editor")
        return True


# Global database instance - use Supabase REST API
db = SupabaseDB()