# BuildTrack Backend Implementation Guide (Current Code)

This document describes how the backend works today, based on the current FastAPI codebase.

## 1. Stack and Layers
- Framework: FastAPI
- Language: Python
- DB: PostgreSQL (schema-per-tenant)
- Data access: SQLAlchemy async sessions + SQL repositories
- Auth: JWT

Layering used in code:
1. API routers (`app/api/v1/*`)
2. Services (`app/services/*`)
3. Repositories (`app/repositories/*`)
4. Models/schemas (`app/models/*`, `app/api/v1/schemas.py`)

## 2. Request Flow
1. Client sends `X-Tenant-ID` header.
2. `get_current_tenant()` resolves tenant and schema from public tables.
3. `get_current_paid_tenant()` applies subscription access policy (trial/subscribed/read-only on expiry).
4. `get_current_user()` resolves actor from JWT (`Authorization: Bearer ...`) or `X-User-ID` fallback.
5. Services call `set_tenant_search_path()` to run queries in tenant schema.

## 3. Multi-Tenant Model
- Public schema stores tenant and subscription metadata.
- Each tenant has separate schema for operational data (`users`, `projects`, `sites`, `workers`, etc.).
- Tenant schema is created at tenant onboarding.

## 4. Subscription System (Current)

### 4.1 Plans
Plans are in `public.plans`:
- `STARTER`: `$10/month`, `max_sites=3`
- `GROWTH`: `$20/month`, `max_sites=5`
- `PRO`: `$40/month`, `max_sites=10`
- Extra site price is fixed constant: `$5/month`.

### 4.2 Trial
At tenant creation (`POST /api/v1/tenants`):
- Trial row is auto-created in `public.tenant_subscriptions`
- `trial_start_date = today`
- `trial_end_date = today + 45 days`
- `is_trial_active = true`
- Trial site limit = 2

### 4.3 Razorpay-driven subscription updates
Subscription mutation endpoints are protected by webhook secret header:
- `POST /api/v1/tenants/subscription`
- `POST /api/v1/tenants/subscription/extra-sites`

Required header:
- `X-Razorpay-Webhook-Secret: <secret>`

Configured via:
- `razorpay_webhook_secret` in app settings (`app/core/config.py`)

### 4.4 Read-only behavior after expiry
Global dependency logic (`check_subscription_access`):
- If trial active: allow all
- Else if subscription active: allow all
- Else:
  - allow `GET/HEAD/OPTIONS`
  - block write methods (`POST/PUT/PATCH/DELETE`) with HTTP 402

## 5. Site Limit Enforcement
Before site creation (`create_site` service):
- If trial active: limit = 2
- Else if subscribed: `limit = plan_max_sites + extra_sites_count`
- Else: limit = 0
- If current non-deleted sites >= limit => HTTP 409

## 6. Auth and Roles
Roles:
- `CONTRACTOR`
- `SUPERVISOR`

Auth endpoints:
- OTP flow (`/auth/send-otp`, `/auth/verify-otp`)
- Password login (`/auth/login`)
- Invite/set-password flow

Role/permission model:
- Contractor has full access in tenant scope.
- Supervisor access is permission-based (`supervisor_permissions`) and site-assignment based.
- Default supervisor permissions include:
  - `add_worker`
  - `mark_attendance`

## 7. Workforce and Salary Modules

### 7.1 Workers
Endpoints:
- `POST /api/v1/workers`
- `GET /api/v1/workers`

Worker salary config:
- `salary_type`: `daily` or `monthly`
- `daily_wage` (daily)
- `monthly_salary` + `is_attendance_based` (monthly)

### 7.2 Attendance
Endpoints:
- `POST /api/v1/attendance`
- `GET /api/v1/attendance`

Rules:
- Unique attendance per worker/date
- Statuses: `present`, `absent`, `paid_leave`, `half_day`

### 7.3 Bonus
Endpoints:
- `POST /api/v1/bonus`
- `GET /api/v1/bonus`

### 7.4 Salary summary
Endpoint:
- `GET /api/v1/salary-summary?worker_id=<id>&from=<date>&to=<date>`

Computation:
- Daily worker: attendance units (`present=1`, `paid_leave=1`, `half_day=0.5`) × daily wage
- Monthly worker (attendance-based): prorated per day by month length × attendance units
- Monthly worker (non-attendance-based): full prorated days in selected range
- Bonus is included

Important MVP behavior:
- Payment amount tracking is not used.
- `total_paid` is `0` in salary summary.
- Settlement status controls `PAID/UNPAID`.

### 7.5 Salary settlement
Endpoint:
- `POST /api/v1/salary-settlements`

Stores period-level flag:
- `is_paid`
- `paid_on`
- `marked_by`

## 8. Other Core Modules
- Projects: CRUD
- Sites: CRUD (with subscription/site-limit enforcement)
- Materials and material transactions
- Tasks
- Expenses
- Dashboard summary
- Contractor/supervisor management and permission assignment

## 9. Key Headers
- Tenant context: `X-Tenant-ID`
- User context fallback: `X-User-ID`
- JWT: `Authorization: Bearer <token>`
- Razorpay webhook guard: `X-Razorpay-Webhook-Secret`

## 10. Main API Router Groups
- `/api/v1/auth`
- `/api/v1/tenants`
- `/api/v1/projects`
- `/api/v1/sites`
- `/api/v1/materials`, `/api/v1/material-transactions`
- `/api/v1/tasks`
- `/api/v1/expenses`
- `/api/v1/dashboard`
- `/api/v1/contractor`
- `/api/v1/supervisor`
- workforce endpoints at root of `/api/v1` (`/workers`, `/attendance`, `/bonus`, `/salary-summary`, `/salary-settlements`)

## 11. Operational Notes
- The system is validated by tests in `tests/`.
- Current behavior is implementation-first; if business policy changes, update service layer first, then tests.
