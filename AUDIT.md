# Audit (Spec v1.3 + v1.3.1)

This audit highlights issues and improvements based on the repo’s current codebase. Severity levels: High, Medium, Low.

- main.py:66 — High — Webhook lacks X-Telegram-Bot-Api-Secret-Token verification. Adds path secrecy but no header check for Telegram-origin requests.
- app/config.py:79–90 — High — Computed database URL omits `sslmode=require` and cannot be overridden by env `DATABASE_URL`.
- app/db.py:48 — Medium — Pool connects using `settings.database_url`; if URL lacks SSL params, connection may be downgraded. Fixed by enforcing sslmode in config.
- app/routers/commands.py: start of file — Medium — No `/paysupport` handler to guide users and notify admins about payment issues.
- app/models.sql:56 / supabase_schema_fixed.sql — Medium — No unique partial index enforcing single active/grace subscription per user. Code relies on `ON CONFLICT (user_id) WHERE status IN ('active','grace')` (app/db.py:98) which requires such an index.
- supabase_indexes.sql: performance/idempotency — Info — Idempotent payments depend on unique indexes on charge_id/star_tx_id. Present, but ensure applied in production.
- app/dashboard.py:1–20 — Info — Dashboard is protected via Bearer token. Ensure `DASHBOARD_TOKENS` are set in env; empty means all requests fail with 401 (expected).
- app/reconcile.py:18–66 — Info — Reconciliation correctly pages via `get_star_transactions(offset, limit)` and uses a sliding window; ensure scheduler is running (app/scheduler.py).

Notes
- No hardcoded secrets found; configuration is read from environment (.env supported by pydantic).
- Health endpoints exist and are lightweight.
- UniqueViolation handling for payments present; relies on DB indexes being applied.
