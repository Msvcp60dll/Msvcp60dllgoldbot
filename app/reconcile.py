from datetime import datetime, timedelta, timezone
import logging
from typing import Optional
from app.config import settings
from app.db import db

logger = logging.getLogger(__name__)

async def reconcile_star_transactions():
    """Reconcile Star transactions with sliding window"""
    from app.bot import bot
    
    try:
        # Get last reconciliation cursor
        last_tx_at = await db.get_reconcile_cursor()
        
        # Calculate time window with overlap
        now = datetime.now(timezone.utc)
        if last_tx_at:
            # Look back from last cursor with window overlap
            from_date = last_tx_at - timedelta(days=settings.reconcile_window_days)
        else:
            # First run: look back full window
            from_date = now - timedelta(days=settings.reconcile_window_days)
        
        to_date = now
        
        logger.info(f"Reconciling transactions from {from_date} to {to_date}")
        
        # Get existing payments in window for deduplication
        existing_payments = await db.fetch("""
            SELECT charge_id, star_tx_id 
            FROM payments 
            WHERE created_at >= $1
        """, from_date - timedelta(days=1))  # Extra day for safety
        
        existing_charge_ids = {p['charge_id'] for p in existing_payments if p['charge_id']}
        existing_star_tx_ids = {p['star_tx_id'] for p in existing_payments if p['star_tx_id']}
        
        # Get Star transactions from Telegram
        offset = 0
        max_tx_date = last_tx_at
        processed = 0
        new_payments = 0
        
        while True:
            try:
                transactions = await bot.get_star_transactions(
                    offset=offset,
                    limit=100
                )
                
                if not transactions.transactions:
                    break
                
                for tx in transactions.transactions:
                    # Convert transaction date
                    tx_date = datetime.fromtimestamp(tx.date, tz=timezone.utc)
                    
                    # Skip if outside window
                    if tx_date < from_date or tx_date > to_date:
                        continue
                    
                    # Track max date for cursor
                    if not max_tx_date or tx_date > max_tx_date:
                        max_tx_date = tx_date
                    
                    # Skip if already processed (by transaction ID)
                    if tx.id in existing_star_tx_ids:
                        continue
                    
                    # Process incoming payment
                    if tx.source and hasattr(tx.source, 'user'):
                        user_id = tx.source.user.id
                        
                        # Insert payment (idempotent)
                        payment = await db.insert_payment_idempotent(
                            user_id=user_id,
                            star_tx_id=tx.id,
                            amount=tx.amount,
                            payment_type='recurring_renewal',  # Assume renewal for reconciliation
                            is_recurring=True
                        )
                        
                        if payment:
                            new_payments += 1
                            
                            # Get user's subscription
                            subscription = await db.get_active_subscription(user_id)
                            
                            if subscription:
                                # Extend subscription
                                new_expires = max(
                                    subscription['expires_at'],
                                    tx_date + timedelta(days=30)
                                )
                                
                                await db.execute("""
                                    UPDATE subscriptions
                                    SET expires_at = $2,
                                        status = 'active',
                                        grace_until = NULL,
                                        grace_started_at = NULL
                                    WHERE user_id = $1 
                                        AND status IN ('active', 'grace', 'expired')
                                """, user_id, new_expires)
                            else:
                                # Create new subscription
                                await db.execute("""
                                    INSERT INTO subscriptions (user_id, status, is_recurring, expires_at)
                                    VALUES ($1, 'active', true, $2)
                                """, user_id, tx_date + timedelta(days=30))
                            
                            await db.log_event(user_id, "reconcile_applied", {
                                "tx_id": tx.id,
                                "amount": tx.amount,
                                "tx_date": tx_date.isoformat()
                            })
                    
                    processed += 1
                
                offset += len(transactions.transactions)
                
                # Check if we've gone through all transactions
                if len(transactions.transactions) < 100:
                    break
                    
            except Exception as e:
                logger.error(f"Error fetching Star transactions at offset {offset}: {e}")
                break
        
        # Update cursor
        if max_tx_date:
            await db.update_reconcile_cursor(max_tx_date)
        
        logger.info(f"Reconciliation complete: processed {processed} transactions, {new_payments} new payments")
        
        # Log stats
        await db.log_event(None, "reconcile_complete", {
            "processed": processed,
            "new_payments": new_payments,
            "from_date": from_date.isoformat(),
            "to_date": to_date.isoformat()
        })
        
    except Exception as e:
        logger.error(f"Reconciliation failed: {e}", exc_info=True)
        await db.log_event(None, "reconcile_error", {"error": str(e)})