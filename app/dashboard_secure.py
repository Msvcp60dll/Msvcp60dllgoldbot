"""
Secure dashboard implementation with input validation and SQL injection prevention.
"""

from fastapi import HTTPException, Header, Request, Depends, Query
from fastapi.responses import HTMLResponse, JSONResponse
from typing import Optional
from datetime import datetime, timedelta, timezone

from app.config import settings
from app.db import db
from app.logging_config import get_logger
from app.validators import DashboardParams, sanitize_log_message
from app.security import build_safe_query, sanitize_order_by

logger = get_logger(__name__)


async def verify_dashboard_auth(authorization: Optional[str] = Header(None)):
    """Verify dashboard authentication"""
    if not authorization:
        logger.warning("dashboard.auth_missing")
        raise HTTPException(status_code=401, detail="Authorization required")
    
    # Check Bearer token
    if not authorization.startswith("Bearer "):
        logger.warning("dashboard.auth_invalid_format")
        raise HTTPException(status_code=401, detail="Invalid authorization format")
    
    token = authorization[7:]
    
    # Validate token exists and is in allowed list
    if not token or token not in settings.dashboard_tokens:
        logger.warning(
            "dashboard.auth_failed",
            token_prefix=token[:10] if token else "empty"
        )
        raise HTTPException(status_code=401, detail="Invalid authorization")
    
    logger.info(
        "dashboard.access_granted",
        token_prefix=token[:10]
    )
    return token


async def get_dashboard_stats_secure(params: DashboardParams):
    """Get dashboard statistics with secure parameterized queries"""
    
    # Build date filters safely
    date_conditions = []
    date_params = []
    param_index = 1
    
    if params.start_date:
        date_conditions.append(f"created_at >= ${param_index}")
        date_params.append(params.start_date)
        param_index += 1
    
    if params.end_date:
        date_conditions.append(f"created_at <= ${param_index}")
        date_params.append(params.end_date)
        param_index += 1
    
    date_filter = " AND ".join(date_conditions) if date_conditions else "1=1"
    
    # Get basic stats with parameterized queries
    stats = await db.get_stats()
    
    # Get funnel metrics with safe parameterized query
    default_filter = "created_at >= NOW() - INTERVAL '24 hours'"
    funnel_query = f"""
        SELECT event_type, COUNT(*) as count
        FROM funnel_events
        WHERE {date_filter or default_filter}
        GROUP BY event_type
    """
    
    if date_params:
        funnel_24h = await db.fetch(funnel_query, *date_params)
    else:
        funnel_24h = await db.fetch(funnel_query)
    
    funnel_dict = {row['event_type']: row['count'] for row in funnel_24h}
    
    # Get recent payments with parameterized limit
    payments_query = """
        SELECT p.payment_id, p.user_id, p.amount, p.payment_type, p.created_at,
               u.username, u.first_name
        FROM payments p
        JOIN users u ON p.user_id = u.user_id
        ORDER BY p.created_at DESC
        LIMIT $1
    """
    recent_payments = await db.fetch(payments_query, min(params.limit, 100))
    
    # Get expiring subscriptions with safe query
    expiring_query = """
        SELECT s.subscription_id, s.user_id, s.expires_at, s.is_recurring,
               u.username, u.first_name
        FROM subscriptions s
        JOIN users u ON s.user_id = u.user_id
        WHERE s.status = 'active'
            AND s.expires_at < NOW() + INTERVAL '3 days'
        ORDER BY s.expires_at
        LIMIT $1
    """
    expiring_soon = await db.fetch(expiring_query, min(params.limit, 100))
    
    # Calculate conversion rate safely
    join_requests = funnel_dict.get('offer_shown', 0)
    payments = stats.get('payments_24h', 0)
    
    # Prevent division by zero
    try:
        conversion_rate = (payments / join_requests * 100) if join_requests > 0 else 0
    except (ZeroDivisionError, TypeError):
        conversion_rate = 0
    
    # Calculate MRR safely
    recurring_subs = stats.get('recurring_subs', 0) or 0
    mrr = recurring_subs * settings.sub_stars
    
    # Sanitize usernames and first names for output
    safe_payments = []
    for p in recent_payments:
        safe_payments.append({
            "user_id": p['user_id'],
            "username": sanitize_log_message(p.get('username', ''), 32) if p.get('username') else None,
            "first_name": sanitize_log_message(p.get('first_name', ''), 32) if p.get('first_name') else None,
            "amount": p['amount'],
            "type": p['payment_type'],
            "created_at": p['created_at'].isoformat()
        })
    
    safe_expiring = []
    for s in expiring_soon:
        safe_expiring.append({
            "user_id": s['user_id'],
            "username": sanitize_log_message(s.get('username', ''), 32) if s.get('username') else None,
            "first_name": sanitize_log_message(s.get('first_name', ''), 32) if s.get('first_name') else None,
            "expires_at": s['expires_at'].isoformat(),
            "is_recurring": s['is_recurring']
        })
    
    return {
        "overview": {
            "total_users": int(stats.get('total_users', 0)),
            "active_users": int(stats.get('active_users', 0)),
            "active_subscriptions": int(stats.get('active_subs', 0)),
            "grace_subscriptions": int(stats.get('grace_subs', 0)),
            "recurring_subscriptions": int(stats.get('recurring_subs', 0)),
            "mrr_stars": int(mrr),
            "revenue_24h": int(stats.get('revenue_24h', 0)),
            "revenue_30d": int(stats.get('revenue_30d', 0)),
            "conversion_rate_24h": round(float(conversion_rate), 2)
        },
        "funnel_24h": {
            "join_requests": int(funnel_dict.get('offer_shown', 0)),
            "invoices_sent": int(funnel_dict.get('invoice_sent', 0)),
            "payments_completed": int(payments),
            "approvals": int(funnel_dict.get('auto_approved', 0) + funnel_dict.get('approve_ok', 0)),
            "grace_transitions": int(funnel_dict.get('grace_notification_sent', 0)),
            "cancellations": int(funnel_dict.get('subscription_cancelled', 0))
        },
        "recent_payments": safe_payments,
        "expiring_soon": safe_expiring,
        "query_params": {
            "start_date": params.start_date.isoformat() if params.start_date else None,
            "end_date": params.end_date.isoformat() if params.end_date else None,
            "limit": params.limit
        },
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


async def dashboard_json_secure(
    request: Request,
    params: DashboardParams = Depends(),
    auth_token: str = Depends(verify_dashboard_auth)
):
    """Secure JSON API endpoint for dashboard with input validation"""
    try:
        # Log dashboard access
        logger.info(
            "dashboard.api_access",
            token_prefix=auth_token[:10],
            params=params.dict()
        )
        
        # Get stats with validated parameters
        stats = await get_dashboard_stats_secure(params)
        
        return JSONResponse(content=stats)
        
    except ValueError as e:
        logger.warning(
            "dashboard.validation_error",
            error=str(e),
            token_prefix=auth_token[:10]
        )
        raise HTTPException(status_code=400, detail=str(e))
        
    except Exception as e:
        logger.error(
            "dashboard.error",
            exception=e,
            token_prefix=auth_token[:10]
        )
        raise HTTPException(status_code=500, detail="Internal server error")


async def dashboard_html_secure(
    request: Request,
    auth_token: str = Depends(verify_dashboard_auth)
):
    """Secure HTML dashboard view"""
    # Use the same HTML template but with added security headers
    html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline';">
    <title>Bot Dashboard - Secure</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js" integrity="sha384-uKQOXLVqRmYjpuNBJBRKGLzLo8jq6YqKmVqNBmyZvJzKAwYGpGlQgABHRjpJ+X5B" crossorigin="anonymous"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f5f5f5;
            padding: 20px;
        }
        .container { max-width: 1200px; margin: 0 auto; }
        h1 { margin-bottom: 20px; color: #333; }
        
        .filters {
            background: white;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        
        .filters label {
            margin-right: 10px;
            font-weight: 600;
        }
        
        .filters input {
            margin-right: 20px;
            padding: 5px 10px;
            border: 1px solid #ddd;
            border-radius: 4px;
        }
        
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
            height: 400px;
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
        
        .refresh-btn, .filter-btn {
            background: #2563eb;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 6px;
            cursor: pointer;
            margin-right: 10px;
        }
        
        .refresh-btn:hover, .filter-btn:hover { background: #1d4ed8; }
        
        .error {
            background: #fee;
            color: #c00;
            padding: 10px;
            border-radius: 4px;
            margin: 10px 0;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 Bot Dashboard (Secure)</h1>
        
        <div class="filters">
            <label>Start Date:</label>
            <input type="datetime-local" id="start-date" max="">
            
            <label>End Date:</label>
            <input type="datetime-local" id="end-date" max="">
            
            <label>Limit:</label>
            <input type="number" id="limit" value="10" min="1" max="100">
            
            <button class="filter-btn" onclick="applyFilters()">Apply Filters</button>
            <button class="refresh-btn" onclick="loadDashboard()">🔄 Refresh</button>
        </div>
        
        <div id="error-message" class="error" style="display:none;"></div>
        
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
        let currentFilters = {};
        
        // Set max date to today
        document.getElementById('start-date').max = new Date().toISOString().slice(0, 16);
        document.getElementById('end-date').max = new Date().toISOString().slice(0, 16);
        
        function escapeHtml(text) {
            const map = {
                '&': '&amp;',
                '<': '&lt;',
                '>': '&gt;',
                '"': '&quot;',
                "'": '&#039;'
            };
            return text ? text.replace(/[&<>"']/g, m => map[m]) : '';
        }
        
        function applyFilters() {
            const startDate = document.getElementById('start-date').value;
            const endDate = document.getElementById('end-date').value;
            const limit = document.getElementById('limit').value;
            
            currentFilters = {};
            
            if (startDate) currentFilters.start_date = startDate;
            if (endDate) currentFilters.end_date = endDate;
            if (limit) currentFilters.limit = parseInt(limit);
            
            // Validate date range
            if (startDate && endDate) {
                const start = new Date(startDate);
                const end = new Date(endDate);
                
                if (end < start) {
                    showError('End date must be after start date');
                    return;
                }
                
                const daysDiff = (end - start) / (1000 * 60 * 60 * 24);
                if (daysDiff > 90) {
                    showError('Date range cannot exceed 90 days');
                    return;
                }
            }
            
            loadDashboard();
        }
        
        function showError(message) {
            const errorEl = document.getElementById('error-message');
            errorEl.textContent = message;
            errorEl.style.display = 'block';
            setTimeout(() => {
                errorEl.style.display = 'none';
            }, 5000);
        }
        
        async function loadDashboard() {
            try {
                const params = new URLSearchParams(currentFilters);
                const url = '/admin/api/summary' + (params.toString() ? '?' + params.toString() : '');
                
                const response = await fetch(url, {
                    headers: {
                        'Authorization': 'Bearer ' + getAuthToken()
                    }
                });
                
                if (!response.ok) {
                    const error = await response.json();
                    throw new Error(error.detail || 'Failed to load dashboard');
                }
                
                const data = await response.json();
                updateMetrics(data.overview);
                updateFunnel(data.funnel_24h);
                updateRecentPayments(data.recent_payments);
                updateExpiringSoon(data.expiring_soon);
                
            } catch (error) {
                console.error('Dashboard error:', error);
                showError(error.message || 'Failed to load dashboard');
            }
        }
        
        function getAuthToken() {
            const urlParams = new URLSearchParams(window.location.search);
            return urlParams.get('token') || sessionStorage.getItem('dashboardToken') || '';
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
                    <td>${escapeHtml(p.first_name || p.username || String(p.user_id))}</td>
                    <td>${p.amount} ⭐</td>
                    <td>${escapeHtml(p.type)}</td>
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
                    <td>${escapeHtml(s.first_name || s.username || String(s.user_id))}</td>
                    <td>${new Date(s.expires_at).toLocaleString()}</td>
                    <td>${s.is_recurring ? '🔄 Recurring' : '💎 One-time'}</td>
                </tr>
            `).join('');
        }
        
        // Load dashboard on page load
        loadDashboard();
        
        // Auto-refresh every 60 seconds (increased from 30)
        setInterval(loadDashboard, 60000);
    </script>
</body>
</html>"""
    
    return HTMLResponse(content=html_content)