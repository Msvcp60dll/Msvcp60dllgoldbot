# Проект: Платная группа Telegram на Stars (aiogram v3 + FastAPI + Supabase + Railway)
**Версия:** 1.3 (идемпотентность + redirect hardening + grace + reconcile window + безопасный дашборд)  
**Дата:** 2025-09-04  
**Автор требований:** Anton + Ia (co-design)  
**Язык реализации:** Python 3.11+

---

## 0) Что нового vs v1.2
1) **Идемпотентность платежей**: защита от дублей на уровне БД — уникальные индексы по `charge_id` и `star_tx_id` (+ обработка `UniqueViolation`).  
2) **Redirect-трекер** `/r/sub`: мгновенный `307` + `Cache-Control: no-store` + бэкграунд-лог + таймстамп-параметр `_t` для анти-кэша.  
3) **Grace period**: статус `grace` с `grace_until`, дефолт `GRACE_HOURS=48`. Планировщик переводит `active → grace → expired`.  
4) **Reconcile с «скользящим окном»**: читаем Star-транзакции за последние `RECONCILE_WINDOW_DAYS` (напр., 3 дня) от курсора времени; дедуп по индексам.  
5) **Dashboard auth**: токены формата Bearer — `DASHBOARD_TOKENS=tok1,tok2`; без owner-id по HTTP.  
6) **Надёжный approve**: ретраи с бэкоффом + self‑service `/enter` как гарант доставки доступа.  

No‑Refund политика остаётся неизменной: возвратов не делаем, доступ доставляем.

---

## 1) Краткое резюме
Бот продаёт доступ в группу через **Telegram Stars (XTR)**. Вход — **только Join-by-Request**. В ЛС две кнопки: **разовый** пропуск и **подписка/мес** (автосписание). Оплата → авто‑approve.  
Стабильность обеспечивают: идемпотентность, reconcile звёздных транзакций, self‑service вход `/enter`, whitelist, планировщик, и лёгкий дашборд.

---

## 2) Архитектура (сжатая)
- **aiogram v3**: `chat_join_request`, `pre_checkout_query`, `successful_payment`, `chat_member`, команды `/status`, `/enter`, `/cancel_sub`, `/stats` (для OWNER_IDS).  
- **FastAPI**: `/webhook/{WEBHOOK_SECRET}`, `/r/sub` редирект‑трекер, `/healthz`, `/admin/api/summary`, `/admin/dashboard`.  
- **Supabase/Postgres**: users, subscriptions, payments, whitelist, funnel_events, recurring_subs, star_tx_cursor.  
- **Scheduler**: напоминания, переходы `active→grace→expired`, баны (учитывая whitelist).  
- **Reconcile**: подбор входящих Star‑транзакций по времени со скользящим окном.  
- **Дашборд**: JSON API + HTML (Chart.js), Bearer‑токены.

---

## 3) Модель данных (SQL фрагменты и миграции)
### 3.1 Основные таблицы (как в v1.2) + добавки
```sql
-- payments: идемпотентные ключи
alter table payments add column if not exists star_tx_id text;
create unique index if not exists uniq_payments_charge_id
  on payments(charge_id) where charge_id is not null;
create unique index if not exists uniq_payments_star_tx
  on payments(star_tx_id) where star_tx_id is not null;

-- subscriptions: grace
do $$ begin
  alter type sub_status add value 'grace';
exception when duplicate_object then null; end $$;
alter table subscriptions add column if not exists grace_until timestamptz;

-- курсор reconcile
create table if not exists star_tx_cursor(
  id int primary key default 1,
  last_tx_at timestamptz,
  last_tx_id text
);
```

### 3.2 Funnel события (без изменений от v1.2, но добавим пару типов)
- `offer_shown`, `approve_retry`, `approve_fail`, `reconcile_applied` — добавлены в список.

---

## 4) Потоки и правила
### 4.1 Join → Offer → Pay → Access
- Любой новый join request **сжигает** whitelist.  
- Если у пользователя активен доступ — сразу `approve`. Иначе ЛС с кнопками:  
  - **Разовый** → `sendInvoice("XTR", prices=[LabeledPrice(amount=PLAN_STARS)])`.  
  - **Подписка** → redirect `/r/sub?u={id}&v={ab}&p={SUB_STARS}` → 307 на `createInvoiceLink(..., subscription_period=2592000)`.  
- `pre_checkout_query` → `ok=True`.  
- `successful_payment` (идемпотентно):
  - Вставка `payments` с `charge_id` (и/или `star_tx_id` если есть) — **под частичным уникальным индексом**.  
  - Разовый: `expires_at = max(now, expires_at) + PLAN_DAYS`, `is_recurring=false`.  
  - Подписка: `expires_at = subscription_expiration_date`, `is_recurring=true`, `recurring_subs.charge_id` при первом платеже.  
  - **Finalize access**: ретраи `approve_chat_join_request` (экспоненциально, до 24ч) → если не взлетело, `/enter` всё равно доставит.

### 4.2 Redirect‑трекер `/r/sub`
- Возвращает **307** + `Cache-Control: no-store` и `Vary: User-Agent`.  
- Логирует событие **в фоне** (BackgroundTasks).  
- К URL инвойса добавляет `_t={unix_ts}` для разрушения кэша.

### 4.3 Self‑service `/enter`
- Если `expires_at >= now()` → попытаться `approve_chat_join_request`.  
- Если не висит join request → сгенерировать одноразовую ссылку:  
  `createChatInviteLink(creates_join_request=true, member_limit=1, expire_date=now+INVITE_TTL_MIN)`.

### 4.4 Планировщик: grace
- При `expires_at < now()` и `status='active'` → `status='grace'`, `grace_until = expires_at + GRACE_HOURS`.  
- При `grace_until < now()` и `status='grace'` → `status='expired'` + бан (кроме whitelist).  
- Напоминания шлём только `is_recurring=false` (разовые) за `DAYS_BEFORE_EXPIRE` (опционально — за 1 день подписчикам предупредить пополнить ⭐).

### 4.5 Reconcile: «окно назад»
- Храним `last_tx_at` в `star_tx_cursor`.  
- Каждый запуск: `from = coalesce(last_tx_at, now() - interval '{RECONCILE_WINDOW_DAYS} days') - interval '{RECONCILE_WINDOW_DAYS} days'` (двухкратный запас), `to = now()`.  
- Пробегаем транзакции **входящих платежей**; вставляем `payments` с `star_tx_id` → уникальные индексы **гарантируют без дублей**.  
- Для подписок: `expires_at = max(expires_at, tx_date + interval '30 days')`. Для разовых: `+ PLAN_DAYS`.  
- В конце: `last_tx_at = max(tx.date)`.

---

## 5) Аутентификация дашборда
- Переменная `DASHBOARD_TOKENS="tok1,tok2"`; HTTP‑доступ только с заголовком `Authorization: Bearer <token>`.  
- Никаких Telegram‑ID в HTTP. Всегда HTTPS (Railway).  
- Дополнительно можно включить BasicAuth (`DASHBOARD_USER/PASS`) — опционально.

---

## 6) Переменные окружения (дельта)
```
GRACE_HOURS=48
RECONCILE_WINDOW_DAYS=3
DASHBOARD_TOKENS=tok1,tok2
```
(Остальные — как в v1.2 no‑agents: PLAN_*, SUB_*, …)

---

## 7) Скетчи кода

### 7.1 Идемпотентная вставка платежа
```python
from asyncpg import UniqueViolationError

async def insert_payment_idempotent(**kw):
    try:
        await db.insert_payment(**kw)    # внутри обычный INSERT
        return True
    except UniqueViolationError:
        return False
```

### 7.2 Надёжный approve
```python
async def finalize_access(tid: int):
    delay = 0.5
    for attempt in range(8):  # ~0.5 + 1 + 2 + 4 + ... секунд
        try:
            await bot.approve_chat_join_request(settings.group_chat_id, tid)
            await db.log_event(tid, "approve_ok", {"attempt": attempt})
            return True
        except RetryableTelegramError:
            await db.log_event(tid, "approve_retry", {"attempt": attempt})
            await asyncio.sleep(delay); delay *= 2
        except FatalTelegramError:
            break
    await db.log_event(tid, "approve_fail", {})
    return False  # пользователь добьёт /enter
```

### 7.3 Redirect‑трекер
```python
@app.get("/r/sub")
async def rsub(u: int, v: str = "A", p: int = 0, bt: BackgroundTasks = None):
    link = await create_subscription_invoice_link(u, p)  # createInvoiceLink(..., subscription_period=2592000)
    if bt: bt.add_task(db.log_funnel_event, u, "sub_link_click", {"ab": v, "price": p})
    return RedirectResponse(link + f"&_t={int(time.time())}", status_code=307, headers={"Cache-Control": "no-store", "Vary": "User-Agent"})
```

### 7.4 Планировщик: grace → expired
```python
async def sweep():
    now = datetime.now(timezone.utc)
    # active → grace
    for s in await db.find_to_grace(now):
        await db.set_grace(s.user_id, s.expires_at + timedelta(hours=settings.grace_hours))
        await safe_dm(s.user_id, "Доступ истёк, у вас ещё идёт льготный период.")

    # grace → expired
    for s in await db.find_to_expire(now):
        if not await db.is_whitelisted(s.user_id):
            await bot.banChatMember(settings.group_chat_id, s.user_id)
        await db.set_expired(s.user_id)
```

---

## 8) MASTER PROMPT для Codex (GPT‑5‑high) — v1.3
Скопируй блок целиком. Он дополняет v1.2, включая правки выше.

```text
Goal: Build a production-ready Telegram bot that sells access to a discussion supergroup via Telegram Stars (XTR), offering ONE-TIME and MONTHLY RECURRING payments. No refunds. No LLMs. Stack: Python 3.11+, aiogram v3, FastAPI webhook, Postgres (Supabase), Railway. Must include: Join-by-Request funnel, DM offer, one-time invoice (sendInvoice currency="XTR"), subscription via invoice link (subscription_period=2592000), auto-approve on payment with retries + self-service /enter, reminders & grace & expiry with soft ban, whitelist, reconciliation of Star transactions with sliding time window, redirect tracker hardened, dashboard with Bearer-token auth, idempotent payments.

**Deliverables (files):**
- pyproject.toml, README.md, .env.example, Dockerfile
- main.py (FastAPI: /webhook/{WEBHOOK_SECRET}, /healthz, /r/sub, /admin/api/summary, /admin/dashboard)
- app/config.py (envs incl. GRACE_HOURS, RECONCILE_WINDOW_DAYS, DASHBOARD_TOKENS)
- app/bot.py (startup: delete_webhook; set_webhook with allowed_updates=["chat_join_request","chat_member","message","callback_query","pre_checkout_query"])
- app/db.py (asyncpg; helpers; queries for grace transitions; idempotent inserts; funnel logging)
- app/reconcile.py (read incoming Star transactions from Bot API using a **sliding window** back from star_tx_cursor.last_tx_at; insert payments with star_tx_id; update subscriptions; save new last_tx_at)
- app/scheduler.py (hourly: active→grace→expired; soft bans; reminders for non-recurring; use whitelist)
- app/dashboard.py (+ templates/dashboard.html) — JSON API + HTML with Bearer token auth via DASHBOARD_TOKENS
- app/models.sql (schema v1.3: payments.star_tx_id; unique partial indexes on charge_id, star_tx_id; subscriptions.grace_until; sub_status includes 'grace'; star_tx_cursor; funnel_events)
- app/routers/{join.py,payments.py,commands.py,members.py} with:
  - join: on chat_join_request → upsert user; revoke whitelist; if active → approve; else DM two buttons (one-time callback pay:one; subscription URL /r/sub?u=...)
  - payments: pre_checkout_query(ok=True); on successful_payment → **idempotent insert** (charge_id), set/extend expires_at; if recurring → use subscription_expiration_date and mark is_recurring=true; store recurring_subs.charge_id on first; then **finalize access** via approve with exponential backoff; if fail, user completes via /enter
  - commands: /status (show expiry, recurring flag, buttons Enter/Extend/Subscribe), /enter (approve or single-use invite with TTL), /cancel_sub (disable autorenew by stored charge_id; access kept until expires_at), /stats (OWNER_IDS) with key numbers
  - members: on left/kicked → revoke whitelist

**Hardening requirements:**
- Payments **idempotency**: DB unique indexes:
  - uniq_payments_charge_id on payments(charge_id) where charge_id is not null
  - uniq_payments_star_tx on payments(star_tx_id) where star_tx_id is not null
  Handle UniqueViolationError gracefully.
- Redirect tracker /r/sub: return 307, add Cache-Control: no-store; log in background; append timestamp query param to invoice link to avoid client caches.
- Reconcile: use RECONCILE_WINDOW_DAYS to re-read window back from last_tx_at; deduplicate via unique indexes; update last_tx_at to max(tx.date).
- Grace: GRACE_HOURS; transitions active→grace when expires_at < now, then grace→expired when grace_until < now; ban on expired unless whitelisted.
- Dashboard auth: only Bearer tokens from DASHBOARD_TOKENS env; reject otherwise.

**Output:** full runnable repo with code and concise README, no TODOs, static copy (no LLMs). Keep code clean and typed, with retries/backoff and structured logging.
```

---

## 9) Что проверить после генерации
- Разовая/подписка: оплата → без дублей в `payments`, сроки корректно обновляются.  
- `/r/sub`: клики логируются, редирект быстрый, без кэша.  
- Планировщик: переходы `active→grace→expired` и баны (whitelist не трогать).  
- Reconcile: выключить вебхук на час, оплатить → после старта reconcile подберёт транзакцию без дублей.  
- Дашборд: открывается только с Bearer‑токеном; `/stats` в чате — правильные цифры.

---

С этим v1.3 у нас скелет **строгий и скромный**: минимум магии, много идемпотентности и предсказуемости. Дальше можно строить рефералку и когортки — без переделок базы.
