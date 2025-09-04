"""Optimized stats query using CTE for better performance"""

async def get_stats_optimized(self) -> dict:
    """Get statistics for dashboard using optimized CTE query"""
    result = await self.fetchrow("""
        WITH stats AS (
            SELECT 
                COUNT(DISTINCT u.user_id) as total_users,
                COUNT(DISTINCT u.user_id) FILTER (WHERE u.status = 'active') as active_users,
                COUNT(DISTINCT s.user_id) FILTER (WHERE s.status = 'active') as active_subs,
                COUNT(DISTINCT s.user_id) FILTER (WHERE s.status = 'grace') as grace_subs,
                COUNT(DISTINCT s.user_id) FILTER (WHERE s.is_recurring = true AND s.status IN ('active', 'grace')) as recurring_subs
            FROM users u
            LEFT JOIN subscriptions s ON u.user_id = s.user_id
        ), 
        payments_stats AS (
            SELECT 
                COALESCE(SUM(amount) FILTER (WHERE created_at >= NOW() - INTERVAL '30 days'), 0) as revenue_30d,
                COALESCE(SUM(amount) FILTER (WHERE created_at >= NOW() - INTERVAL '24 hours'), 0) as revenue_24h,
                COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '24 hours') as payments_24h
            FROM payments
        )
        SELECT 
            s.total_users,
            s.active_users,
            s.active_subs,
            s.grace_subs,
            s.recurring_subs,
            p.revenue_30d,
            p.revenue_24h,
            p.payments_24h
        FROM stats s 
        CROSS JOIN payments_stats p
    """)
    return dict(result)

# To replace the existing method in db.py, use:
# db.get_stats = get_stats_optimized.__get__(db, Database)