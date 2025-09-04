from fastapi import HTTPException, Header, Request, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from typing import Optional
import logging
from datetime import datetime, timedelta, timezone
from app.config import settings
from app.db import db

logger = logging.getLogger(__name__)

async def verify_dashboard_auth(authorization: Optional[str] = Header(None)):
    """Verify dashboard authentication"""
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization required")
    
    # Check Bearer token
    if authorization.startswith("Bearer "):
        token = authorization[7:]
        if token in settings.dashboard_tokens:
            return True
    
    raise HTTPException(status_code=401, detail="Invalid authorization")

async def get_dashboard_stats():
    """Get comprehensive dashboard statistics"""
    stats = await db.get_stats()
    
    # Get funnel metrics
    funnel_24h = await db.fetch("""
        SELECT event_type, COUNT(*) as count
        FROM funnel_events
        WHERE created_at >= NOW() - INTERVAL '24 hours'
        GROUP BY event_type
    """)
    
    funnel_dict = {row['event_type']: row['count'] for row in funnel_24h}
    
    # Get recent payments
    recent_payments = await db.fetch("""
        SELECT p.*, u.username, u.first_name
        FROM payments p
        JOIN users u ON p.user_id = u.user_id
        ORDER BY p.created_at DESC
        LIMIT 10
    """)
    
    # Get expiring soon
    expiring_soon = await db.fetch("""
        SELECT s.*, u.username, u.first_name
        FROM subscriptions s
        JOIN users u ON s.user_id = u.user_id
        WHERE s.status = 'active'
            AND s.expires_at < NOW() + INTERVAL '3 days'
        ORDER BY s.expires_at
        LIMIT 10
    """)
    
    # Calculate conversion rate
    join_requests = funnel_dict.get('offer_shown', 0)
    payments = stats.get('payments_24h', 0)
    conversion_rate = (payments / join_requests * 100) if join_requests > 0 else 0
    
    # Calculate MRR
    mrr = stats.get('recurring_subs', 0) * settings.sub_stars
    
    return {
        "overview": {
            "total_users": stats.get('total_users', 0),
            "active_users": stats.get('active_users', 0),
            "active_subscriptions": stats.get('active_subs', 0),
            "grace_subscriptions": stats.get('grace_subs', 0),
            "recurring_subscriptions": stats.get('recurring_subs', 0),
            "mrr_stars": mrr,
            "revenue_24h": stats.get('revenue_24h', 0),
            "revenue_30d": stats.get('revenue_30d', 0),
            "conversion_rate_24h": round(conversion_rate, 2)
        },
        "funnel_24h": {
            "join_requests": funnel_dict.get('offer_shown', 0),
            "invoices_sent": funnel_dict.get('invoice_sent', 0),
            "payments_completed": payments,
            "approvals": funnel_dict.get('auto_approved', 0) + funnel_dict.get('approve_ok', 0),
            "grace_transitions": funnel_dict.get('grace_notification_sent', 0),
            "cancellations": funnel_dict.get('subscription_cancelled', 0)
        },
        "recent_payments": [
            {
                "user_id": p['user_id'],
                "username": p['username'],
                "first_name": p['first_name'],
                "amount": p['amount'],
                "type": p['payment_type'],
                "created_at": p['created_at'].isoformat()
            }
            for p in recent_payments
        ],
        "expiring_soon": [
            {
                "user_id": s['user_id'],
                "username": s['username'],
                "first_name": s['first_name'],
                "expires_at": s['expires_at'].isoformat(),
                "is_recurring": s['is_recurring']
            }
            for s in expiring_soon
        ],
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

async def dashboard_json(authorization: str = Depends(verify_dashboard_auth)):
    """JSON API endpoint for dashboard"""
    stats = await get_dashboard_stats()
    return JSONResponse(content=stats)

async def dashboard_html(request: Request, authorization: str = Depends(verify_dashboard_auth)):
    """HTML dashboard view"""
    html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bot Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f5f5f5;
            padding: 20px;
        }
        .container { max-width: 1200px; margin: 0 auto; }
        h1 { margin-bottom: 20px; color: #333; }
        .grid { 
            display: grid; 
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .card {
            background: white;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .metric { font-size: 2em; font-weight: bold; color: #2563eb; }
        .label { color: #666; margin-bottom: 5px; }
        .chart-container { 
            background: white;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }
        table {
            width: 100%;
            background: white;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        th, td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #eee;
        }
        th { background: #f8f9fa; font-weight: 600; }
        .status-active { color: #10b981; }
        .status-grace { color: #f59e0b; }
        .refresh-btn {
            background: #2563eb;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 6px;
            cursor: pointer;
            margin-bottom: 20px;
        }
        .refresh-btn:hover { background: #1d4ed8; }
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 Bot Dashboard</h1>
        <button class="refresh-btn" onclick="loadDashboard()">🔄 Refresh</button>
        
        <div class="grid" id="metrics">
            <div class="card">
                <div class="label">Total Users</div>
                <div class="metric" id="total-users">-</div>
            </div>
            <div class="card">
                <div class="label">Active Subscriptions</div>
                <div class="metric" id="active-subs">-</div>
            </div>
            <div class="card">
                <div class="label">MRR (Stars)</div>
                <div class="metric" id="mrr">-</div>
            </div>
            <div class="card">
                <div class="label">Revenue 24h</div>
                <div class="metric" id="revenue-24h">-</div>
            </div>
        </div>
        
        <div class="chart-container">
            <h2>Funnel (Last 24h)</h2>
            <canvas id="funnelChart"></canvas>
        </div>
        
        <h2>Recent Payments</h2>
        <table>
            <thead>
                <tr>
                    <th>User</th>
                    <th>Amount</th>
                    <th>Type</th>
                    <th>Time</th>
                </tr>
            </thead>
            <tbody id="recent-payments">
                <tr><td colspan="4">Loading...</td></tr>
            </tbody>
        </table>
        
        <h2 style="margin-top: 20px;">Expiring Soon</h2>
        <table>
            <thead>
                <tr>
                    <th>User</th>
                    <th>Expires</th>
                    <th>Type</th>
                </tr>
            </thead>
            <tbody id="expiring-soon">
                <tr><td colspan="3">Loading...</td></tr>
            </tbody>
        </table>
    </div>
    
    <script>
        let funnelChart = null;
        
        async function loadDashboard() {
            try {
                const response = await fetch('/admin/api/summary', {
                    headers: {
                        'Authorization': 'Bearer ' + getAuthToken()
                    }
                });
                
                if (!response.ok) throw new Error('Failed to load dashboard');
                
                const data = await response.json();
                updateMetrics(data.overview);
                updateFunnel(data.funnel_24h);
                updateRecentPayments(data.recent_payments);
                updateExpiringSoon(data.expiring_soon);
            } catch (error) {
                console.error('Dashboard error:', error);
                alert('Failed to load dashboard');
            }
        }
        
        function getAuthToken() {
            // Get token from URL or localStorage
            const urlParams = new URLSearchParams(window.location.search);
            return urlParams.get('token') || localStorage.getItem('dashboardToken') || '';
        }
        
        function updateMetrics(overview) {
            document.getElementById('total-users').textContent = overview.total_users;
            document.getElementById('active-subs').textContent = overview.active_subscriptions;
            document.getElementById('mrr').textContent = overview.mrr_stars + ' ⭐';
            document.getElementById('revenue-24h').textContent = overview.revenue_24h + ' ⭐';
        }
        
        function updateFunnel(funnel) {
            const ctx = document.getElementById('funnelChart').getContext('2d');
            
            if (funnelChart) {
                funnelChart.destroy();
            }
            
            funnelChart = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: ['Join Requests', 'Invoices', 'Payments', 'Approved'],
                    datasets: [{
                        label: 'Count',
                        data: [
                            funnel.join_requests,
                            funnel.invoices_sent,
                            funnel.payments_completed,
                            funnel.approvals
                        ],
                        backgroundColor: '#2563eb',
                        borderColor: '#1d4ed8',
                        borderWidth: 1
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: {
                            beginAtZero: true
                        }
                    }
                }
            });
        }
        
        function updateRecentPayments(payments) {
            const tbody = document.getElementById('recent-payments');
            if (payments.length === 0) {
                tbody.innerHTML = '<tr><td colspan="4">No recent payments</td></tr>';
                return;
            }
            
            tbody.innerHTML = payments.map(p => `
                <tr>
                    <td>${p.first_name || p.username || p.user_id}</td>
                    <td>${p.amount} ⭐</td>
                    <td>${p.type}</td>
                    <td>${new Date(p.created_at).toLocaleString()}</td>
                </tr>
            `).join('');
        }
        
        function updateExpiringSoon(subscriptions) {
            const tbody = document.getElementById('expiring-soon');
            if (subscriptions.length === 0) {
                tbody.innerHTML = '<tr><td colspan="3">No subscriptions expiring soon</td></tr>';
                return;
            }
            
            tbody.innerHTML = subscriptions.map(s => `
                <tr>
                    <td>${s.first_name || s.username || s.user_id}</td>
                    <td>${new Date(s.expires_at).toLocaleString()}</td>
                    <td>${s.is_recurring ? '🔄 Recurring' : '💎 One-time'}</td>
                </tr>
            `).join('');
        }
        
        // Load dashboard on page load
        loadDashboard();
        
        // Auto-refresh every 30 seconds
        setInterval(loadDashboard, 30000);
    </script>
</body>
</html>"""
    
    return HTMLResponse(content=html_content)