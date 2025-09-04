from aiogram import Router, F
from aiogram.types import ChatMemberUpdated
import logging
from app.config import settings
from app.db import db

logger = logging.getLogger(__name__)
router = Router()

@router.chat_member(F.chat.id == settings.group_chat_id)
async def handle_member_update(update: ChatMemberUpdated):
    """Handle chat member status changes"""
    user_id = update.from_user.id
    old_status = update.old_chat_member.status
    new_status = update.new_chat_member.status
    
    try:
        # Log status change
        await db.log_event(user_id, "member_status_change", {
            "old_status": old_status,
            "new_status": new_status
        })
        
        # Handle user leaving or being kicked
        if new_status in ['left', 'kicked']:
            # Revoke whitelist
            await db.revoke_whitelist(user_id)
            logger.info(f"User {user_id} left/kicked, whitelist revoked")
            
            # Log event
            await db.log_event(user_id, "whitelist_revoked", {
                "reason": new_status
            })
        
        # Handle user joining (member status)
        elif old_status in ['left', 'kicked'] and new_status == 'member':
            # Update user as active
            await db.execute("""
                UPDATE users 
                SET status = 'active', last_seen_at = NOW()
                WHERE user_id = $1
            """, user_id)
            
            await db.log_event(user_id, "member_joined", {})
            logger.info(f"User {user_id} joined as member")
        
        # Handle ban
        elif new_status == 'kicked':
            # Update user status
            await db.execute("""
                UPDATE users 
                SET status = 'banned'
                WHERE user_id = $1
            """, user_id)
            
            await db.log_event(user_id, "member_banned", {})
            logger.info(f"User {user_id} was banned")
            
    except Exception as e:
        logger.error(f"Error handling member update for user {user_id}: {e}", exc_info=True)