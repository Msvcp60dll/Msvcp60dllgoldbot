"""
Single source of truth for webhook configuration.
ALL webhook setups MUST use this configuration.
"""

# CRITICAL: These are the ONLY allowed_updates that should EVER be used
REQUIRED_WEBHOOK_UPDATES = [
    "message",              # Regular messages
    "callback_query",       # Inline button callbacks
    "chat_join_request",    # CRITICAL: Group join requests
    "chat_member",          # Member status changes
    "pre_checkout_query",   # Payment pre-checkout
    "successful_payment"    # CRITICAL: Payment confirmations
]

# Webhook configuration constants
WEBHOOK_DROP_PENDING = False  # Don't lose pending updates
WEBHOOK_MAX_CONNECTIONS = 40

def get_webhook_config():
    """Get the standard webhook configuration"""
    return {
        "allowed_updates": REQUIRED_WEBHOOK_UPDATES,
        "drop_pending_updates": WEBHOOK_DROP_PENDING,
        "max_connections": WEBHOOK_MAX_CONNECTIONS
    }

def validate_webhook_updates(current_updates):
    """Check if current webhook has all required updates"""
    if not current_updates:
        return False, REQUIRED_WEBHOOK_UPDATES
    
    missing = [u for u in REQUIRED_WEBHOOK_UPDATES if u not in current_updates]
    return len(missing) == 0, missing

def get_critical_updates():
    """Get updates that are critical for revenue"""
    return ["chat_join_request", "successful_payment"]