from fastapi import HTTPException, Header, Request, Depends, Response
from fastapi.responses import HTMLResponse, JSONResponse
from typing import Optional
import logging
import csv
import io
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

async def get_overdue_members():
    """Get members who are overdue but not yet kicked"""
    # Get overdue subscriptions
    overdue = await db.fetch("""
        SELECT 
            s.user_id,
            s.expires_at,
            s.status,
            s.is_recurring,
            u.username,
            u.first_name,
            u.last_name,
            EXTRACT(EPOCH FROM (NOW() - s.expires_at))/86400 as days_overdue,
            w.telegram_id as whitelisted
        FROM subscriptions s
        JOIN users u ON s.user_id = u.user_id
        LEFT JOIN whitelist w ON s.user_id = w.telegram_id AND w.revoked_at IS NULL
        WHERE s.expires_at < NOW() 
            AND s.status != 'banned'
        ORDER BY s.expires_at ASC
    """)
    
    # Separate whitelisted from non-whitelisted
    overdue_members = []
    for row in overdue:
        member = {
            "user_id": row['user_id'],
            "username": row['username'],
            "first_name": row['first_name'],
            "last_name": row['last_name'],
            "expires_at": row['expires_at'].isoformat(),
            "days_overdue": round(row['days_overdue'], 1),
            "status": row['status'],
            "is_recurring": row['is_recurring'],
            "whitelisted": bool(row['whitelisted']),
            "severity": "critical" if row['days_overdue'] > 3 else "warning"
        }
        overdue_members.append(member)
    
    return overdue_members

async def get_enhanced_dashboard_stats():
    """Get comprehensive dashboard statistics with revenue metrics"""
    stats = await db.get_stats()
    
    # Get revenue metrics
    revenue_today = await db.fetchval("""
        SELECT COALESCE(SUM(amount), 0) 
        FROM payments 
        WHERE created_at >= CURRENT_DATE
    """)
    
    revenue_week = await db.fetchval("""
        SELECT COALESCE(SUM(amount), 0) 
        FROM payments 
        WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'
    """)
    
    revenue_month = await db.fetchval("""
        SELECT COALESCE(SUM(amount), 0) 
        FROM payments 
        WHERE created_at >= CURRENT_DATE - INTERVAL '30 days'
    """)
    
    # Get active paid subscriptions (excluding whitelist)
    active_paid = await db.fetchval("""
        SELECT COUNT(DISTINCT s.user_id)
        FROM subscriptions s
        LEFT JOIN whitelist w ON s.user_id = w.telegram_id AND w.revoked_at IS NULL
        WHERE s.status = 'active' 
            AND s.expires_at > NOW()
            AND w.telegram_id IS NULL
    """)
    
    # Get members in grace period
    grace_members = await db.fetchval("""
        SELECT COUNT(*)
        FROM subscriptions
        WHERE status = 'grace'
            AND expires_at < NOW()
            AND expires_at > NOW() - INTERVAL '48 hours'
    """)
    
    # Get funnel metrics for conversion rate
    funnel_24h = await db.fetch("""
        SELECT event_type, COUNT(*) as count
        FROM funnel_events
        WHERE created_at >= NOW() - INTERVAL '24 hours'
        GROUP BY event_type
    """)
    
    funnel_dict = {row['event_type']: row['count'] for row in funnel_24h}
    
    # Calculate conversion rate
    join_requests = funnel_dict.get('offer_shown', 0)
    payments = stats.get('payments_24h', 0)
    conversion_rate = (payments / join_requests * 100) if join_requests > 0 else 0
    
    # Get overdue members
    overdue_members = await get_overdue_members()
    overdue_not_whitelisted = [m for m in overdue_members if not m['whitelisted']]
    
    # Get recent payments with more details
    recent_payments = await db.fetch("""
        SELECT 
            p.*,
            u.username,
            u.first_name,
            u.last_name,
            s.expires_at,
            s.status as sub_status
        FROM payments p
        JOIN users u ON p.user_id = u.user_id
        LEFT JOIN subscriptions s ON p.user_id = s.user_id
        ORDER BY p.created_at DESC
        LIMIT 20
    """)
    
    # Get expiring soon with more details
    expiring_soon = await db.fetch("""
        SELECT 
            s.*,
            u.username,
            u.first_name,
            u.last_name,
            EXTRACT(EPOCH FROM (s.expires_at - NOW()))/3600 as hours_until_expiry
        FROM subscriptions s
        JOIN users u ON s.user_id = u.user_id
        WHERE s.status = 'active'
            AND s.expires_at > NOW()
            AND s.expires_at < NOW() + INTERVAL '3 days'
        ORDER BY s.expires_at
        LIMIT 20
    """)
    
    # Calculate MRR
    mrr = stats.get('recurring_subs', 0) * settings.sub_stars
    
    return {
        "overview": {
            "total_users": stats.get('total_users', 0),
            "active_users": stats.get('active_users', 0),
            "active_paid_subscriptions": active_paid,
            "total_active_subscriptions": stats.get('active_subs', 0),
            "grace_members": grace_members,
            "overdue_not_kicked": len(overdue_not_whitelisted),
            "overdue_whitelisted": len(overdue_members) - len(overdue_not_whitelisted),
            "recurring_subscriptions": stats.get('recurring_subs', 0),
            "mrr_stars": mrr,
            "revenue_today": revenue_today,
            "revenue_week": revenue_week,
            "revenue_month": revenue_month,
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
        "overdue_members": overdue_members,
        "recent_payments": [
            {
                "user_id": p['user_id'],
                "username": p['username'],
                "first_name": p['first_name'],
                "last_name": p['last_name'],
                "amount": p['amount'],
                "type": p['payment_type'],
                "created_at": p['created_at'].isoformat(),
                "sub_status": p['sub_status'],
                "expires_at": p['expires_at'].isoformat() if p['expires_at'] else None
            }
            for p in recent_payments
        ],
        "expiring_soon": [
            {
                "user_id": s['user_id'],
                "username": s['username'],
                "first_name": s['first_name'],
                "last_name": s['last_name'],
                "expires_at": s['expires_at'].isoformat(),
                "hours_until_expiry": round(s['hours_until_expiry'], 1),
                "is_recurring": s['is_recurring']
            }
            for s in expiring_soon
        ],
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

async def dashboard_api_summary(authorization: str = Depends(verify_dashboard_auth)):
    """Enhanced JSON API endpoint for dashboard"""
    stats = await get_enhanced_dashboard_stats()
    return JSONResponse(content=stats)

async def export_overdue_csv(authorization: str = Depends(verify_dashboard_auth)):
    """Export overdue members as CSV"""
    overdue_members = await get_overdue_members()
    
    # Create CSV in memory
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=[
        'user_id', 'username', 'first_name', 'last_name',
        'expires_at', 'days_overdue', 'status', 'is_recurring',
        'whitelisted', 'severity'
    ])
    
    writer.writeheader()
    writer.writerows(overdue_members)
    
    # Return as downloadable CSV
    csv_content = output.getvalue()
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=overdue_members_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        }
    )

async def dashboard_html_enhanced(request: Request, authorization: str = Depends(verify_dashboard_auth)):
    """Enhanced HTML dashboard view with overdue members"""
    html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bot Dashboard - Enhanced</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f5f5f5;
            padding: 20px;
        }
        .container { max-width: 1400px; margin: 0 auto; }
        h1 { margin-bottom: 20px; color: #333; }
        h2 { margin: 20px 0 10px; color: #555; }
        .grid { 
            display: grid; 
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 30px;
        }
        .card {
            background: white;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .card.warning { border-left: 4px solid #f59e0b; }
        .card.critical { border-left: 4px solid #ef4444; }
        .metric { font-size: 2em; font-weight: bold; color: #2563eb; }
        .metric.warning { color: #f59e0b; }
        .metric.critical { color: #ef4444; }
        .label { color: #666; margin-bottom: 5px; font-size: 0.9em; }
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
            margin-bottom: 20px;
        }
        th, td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #eee;
        }
        th { background: #f8f9fa; font-weight: 600; }
        tr:hover { background: #f8f9fa; }
        .status-active { color: #10b981; }
        .status-grace { color: #f59e0b; }
        .status-expired { color: #ef4444; }
        .severity-warning { background: #fef3c7; }
        .severity-critical { background: #fee2e2; }
        .whitelisted { opacity: 0.6; }
        .button-group {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
            align-items: center;
        }
        .btn {
            background: #2563eb;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 6px;
            cursor: pointer;
            text-decoration: none;
            display: inline-block;
        }
        .btn:hover { background: #1d4ed8; }
        .btn-secondary { background: #6b7280; }
        .btn-secondary:hover { background: #4b5563; }
        .btn-export { background: #10b981; }
        .btn-export:hover { background: #059669; }
        .auto-refresh {
            display: flex;
            align-items: center;
            gap: 10px;
            color: #666;
        }
        .auto-refresh input { margin-right: 5px; }
        .overdue-section {
            background: white;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-bottom: 20px;
            border-top: 4px solid #ef4444;
        }
        .revenue-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 10px;
            margin: 10px 0;
        }
        .revenue-item {
            text-align: center;
            padding: 10px;
            background: #f3f4f6;
            border-radius: 6px;
        }
        .revenue-label { font-size: 0.8em; color: #666; }
        .revenue-value { font-size: 1.5em; font-weight: bold; color: #10b981; }
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 Enhanced Bot Dashboard</h1>
        
        <div class="button-group">
            <button class="btn" onclick="loadDashboard()">🔄 Refresh Now</button>
            <a href="/admin/api/overdue/csv" class="btn btn-export" id="export-btn">📥 Export Overdue Members</a>
            <div class="auto-refresh">
                <label>
                    <input type="checkbox" id="auto-refresh" checked> Auto-refresh every 60s
                </label>
                <span id="last-update">Never</span>
            </div>
        </div>
        
        <!-- Key Metrics -->
        <div class="grid" id="metrics">
            <div class="card">
                <div class="label">Active Paid Subs</div>
                <div class="metric" id="active-paid">-</div>
            </div>
            <div class="card">
                <div class="label">MRR (Stars)</div>
                <div class="metric" id="mrr">-</div>
            </div>
            <div class="card">
                <div class="label">Conversion Rate 24h</div>
                <div class="metric" id="conversion">-</div>
            </div>
            <div class="card warning">
                <div class="label">Grace Period</div>
                <div class="metric warning" id="grace">-</div>
            </div>
            <div class="card critical">
                <div class="label">Overdue Not Kicked</div>
                <div class="metric critical" id="overdue">-</div>
            </div>
        </div>
        
        <!-- Revenue Metrics -->
        <div class="card">
            <h3>💰 Revenue (Stars)</h3>
            <div class="revenue-grid">
                <div class="revenue-item">
                    <div class="revenue-label">Today</div>
                    <div class="revenue-value" id="revenue-today">-</div>
                </div>
                <div class="revenue-item">
                    <div class="revenue-label">This Week</div>
                    <div class="revenue-value" id="revenue-week">-</div>
                </div>
                <div class="revenue-item">
                    <div class="revenue-label">This Month</div>
                    <div class="revenue-value" id="revenue-month">-</div>
                </div>
            </div>
        </div>
        
        <!-- Overdue Members Section -->
        <div class="overdue-section">
            <h2>⚠️ OVERDUE MEMBERS STILL IN CHAT</h2>
            <p style="color: #666; margin-bottom: 10px;">Members whose subscriptions expired but haven't been kicked (excluding whitelisted)</p>
            <table>
                <thead>
                    <tr>
                        <th>User ID</th>
                        <th>Username</th>
                        <th>Name</th>
                        <th>Days Overdue</th>
                        <th>Status</th>
                        <th>Type</th>
                        <th>Whitelisted</th>
                    </tr>
                </thead>
                <tbody id="overdue-members">
                    <tr><td colspan="7">Loading...</td></tr>
                </tbody>
            </table>
        </div>
        
        <!-- Funnel Chart -->
        <div class="chart-container">
            <h2>📈 Conversion Funnel (Last 24h)</h2>
            <canvas id="funnelChart" height="100"></canvas>
        </div>
        
        <!-- Recent Payments -->
        <h2>💎 Recent Payments</h2>
        <table>
            <thead>
                <tr>
                    <th>User</th>
                    <th>Amount</th>
                    <th>Type</th>
                    <th>Status</th>
                    <th>Time</th>
                </tr>
            </thead>
            <tbody id="recent-payments">
                <tr><td colspan="5">Loading...</td></tr>
            </tbody>
        </table>
        
        <!-- Expiring Soon -->
        <h2>⏰ Expiring Soon</h2>
        <table>
            <thead>
                <tr>
                    <th>User</th>
                    <th>Hours Until Expiry</th>
                    <th>Expires At</th>
                    <th>Type</th>
                </tr>
            </thead>
            <tbody id="expiring-soon">
                <tr><td colspan="4">Loading...</td></tr>
            </tbody>
        </table>
    </div>
    
    <script>
        let funnelChart = null;
        let autoRefreshInterval = null;
        
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
                updateOverdueMembers(data.overdue_members);
                updateRecentPayments(data.recent_payments);
                updateExpiringSoon(data.expiring_soon);
                
                // Update last refresh time
                document.getElementById('last-update').textContent = 
                    'Last update: ' + new Date().toLocaleTimeString();
                
            } catch (error) {
                console.error('Dashboard error:', error);
                alert('Failed to load dashboard: ' + error.message);
            }
        }
        
        function getAuthToken() {
            const urlParams = new URLSearchParams(window.location.search);
            const token = urlParams.get('token') || localStorage.getItem('dashboardToken') || '';
            if (token) {
                localStorage.setItem('dashboardToken', token);
                // Update export button with auth
                document.getElementById('export-btn').href = 
                    `/admin/api/overdue/csv?token=${token}`;
            }
            return token;
        }
        
        function updateMetrics(overview) {
            document.getElementById('active-paid').textContent = overview.active_paid_subscriptions;
            document.getElementById('mrr').textContent = overview.mrr_stars + ' ⭐';
            document.getElementById('conversion').textContent = overview.conversion_rate_24h + '%';
            document.getElementById('grace').textContent = overview.grace_members;
            document.getElementById('overdue').textContent = overview.overdue_not_kicked;
            
            // Revenue metrics
            document.getElementById('revenue-today').textContent = overview.revenue_today + ' ⭐';
            document.getElementById('revenue-week').textContent = overview.revenue_week + ' ⭐';
            document.getElementById('revenue-month').textContent = overview.revenue_month + ' ⭐';
        }
        
        function updateFunnel(funnel) {
            const ctx = document.getElementById('funnelChart').getContext('2d');
            
            if (funnelChart) {
                funnelChart.destroy();
            }
            
            funnelChart = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: ['Join Requests', 'Invoices', 'Payments', 'Approved', 'Cancellations'],
                    datasets: [{
                        label: 'Count',
                        data: [
                            funnel.join_requests,
                            funnel.invoices_sent,
                            funnel.payments_completed,
                            funnel.approvals,
                            funnel.cancellations
                        ],
                        backgroundColor: ['#3b82f6', '#10b981', '#f59e0b', '#8b5cf6', '#ef4444'],
                        borderWidth: 0
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
        
        function updateOverdueMembers(members) {
            const tbody = document.getElementById('overdue-members');
            if (members.length === 0) {
                tbody.innerHTML = '<tr><td colspan="7">No overdue members</td></tr>';
                return;
            }
            
            tbody.innerHTML = members.map(m => {
                const rowClass = m.severity === 'critical' ? 'severity-critical' : 
                                m.severity === 'warning' ? 'severity-warning' : '';
                const whitelistClass = m.whitelisted ? 'whitelisted' : '';
                
                return `
                    <tr class="${rowClass} ${whitelistClass}">
                        <td>${m.user_id}</td>
                        <td>${m.username || '-'}</td>
                        <td>${m.first_name || ''} ${m.last_name || ''}</td>
                        <td><strong>${m.days_overdue}</strong> days</td>
                        <td class="status-${m.status}">${m.status}</td>
                        <td>${m.is_recurring ? '🔄 Recurring' : '💎 One-time'}</td>
                        <td>${m.whitelisted ? '✅ Yes' : '❌ No'}</td>
                    </tr>
                `;
            }).join('');
        }
        
        function updateRecentPayments(payments) {
            const tbody = document.getElementById('recent-payments');
            if (payments.length === 0) {
                tbody.innerHTML = '<tr><td colspan="5">No recent payments</td></tr>';
                return;
            }
            
            tbody.innerHTML = payments.map(p => `
                <tr>
                    <td>${p.first_name || p.username || p.user_id}</td>
                    <td>${p.amount} ⭐</td>
                    <td>${p.type}</td>
                    <td class="status-${p.sub_status || 'active'}">${p.sub_status || 'N/A'}</td>
                    <td>${new Date(p.created_at).toLocaleString()}</td>
                </tr>
            `).join('');
        }
        
        function updateExpiringSoon(subscriptions) {
            const tbody = document.getElementById('expiring-soon');
            if (subscriptions.length === 0) {
                tbody.innerHTML = '<tr><td colspan="4">No subscriptions expiring soon</td></tr>';
                return;
            }
            
            tbody.innerHTML = subscriptions.map(s => {
                const urgentClass = s.hours_until_expiry < 24 ? 'severity-warning' : '';
                return `
                    <tr class="${urgentClass}">
                        <td>${s.first_name || s.username || s.user_id}</td>
                        <td><strong>${s.hours_until_expiry}</strong> hours</td>
                        <td>${new Date(s.expires_at).toLocaleString()}</td>
                        <td>${s.is_recurring ? '🔄 Recurring' : '💎 One-time'}</td>
                    </tr>
                `;
            }).join('');
        }
        
        // Auto-refresh management
        function setupAutoRefresh() {
            const checkbox = document.getElementById('auto-refresh');
            
            function updateAutoRefresh() {
                if (checkbox.checked) {
                    autoRefreshInterval = setInterval(loadDashboard, 60000); // 60 seconds
                } else {
                    if (autoRefreshInterval) {
                        clearInterval(autoRefreshInterval);
                        autoRefreshInterval = null;
                    }
                }
            }
            
            checkbox.addEventListener('change', updateAutoRefresh);
            updateAutoRefresh();
        }
        
        // Initialize dashboard
        loadDashboard();
        setupAutoRefresh();
    </script>
</body>
</html>"""
    
    return HTMLResponse(content=html_content)