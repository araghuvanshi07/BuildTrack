# BuildTrack Frontend Requirements (v1)

## Purpose
This document defines what the frontend app must implement against the current BuildTrack backend.

## Product Scope
- Multi-tenant support
- Authentication (OTP + email/password)
- Projects
- Sites
- Materials + material transactions
- Tasks
- Expenses
- Dashboard summary
- Contractor-managed supervisor permissions

## Roles and Access
- Roles: `CONTRACTOR`, `SUPERVISOR`, `ADMIN` (enum exists; current flows mainly contractor/supervisor)
- Contractor: full operational access
- Supervisor: permission-based + site-assignment based access

Default supervisor permissions (always enabled):
- `add_worker`
- `mark_attendance`

Optional supervisor permissions:
- `create_site`
- `create_task`
- `add_expense`
- `approve_expense` (modeled but no active endpoint logic)
- `view_reports`

## API Integration
- Base prefix: `/api/v1`
- Required headers for protected routes:
  - `X-Tenant-ID: <tenant_uuid>`
  - `Authorization: Bearer <access_token>`

Important:
- Frontend must always send bearer token after login.
- `X-User-ID` is present as fallback behavior; do not rely on it in production UX.

## Global Error Handling
Handle these statuses globally:
- `400` bad request / missing or invalid tenant header
- `401` auth failures
- `402` inactive/expired subscription
- `403` forbidden / missing permission
- `404` not found
- `409` conflicts
- `422` validation
- `500` server error

Common error response shape currently used:
- `{"detail": "..."}`

## Core User Journeys
1. Tenant onboarding
1. Contractor invites user -> set password -> login
1. Contractor creates supervisors and configures permissions
1. Contractor assigns supervisors to sites
1. Contractor/supervisor perform project/site/task/material/expense operations
1. Dashboard summary view

## Required Screens
- Auth:
  - Send OTP
  - Verify OTP
  - Email/password login
  - Set password (token from URL)
  - Invite contractor
  - Resend set-password link
- Projects:
  - List, create, detail, update
- Sites:
  - List, create, detail, update
- Materials:
  - Material create
  - Material transaction create
  - Site material summary
- Tasks:
  - Site tasks list
  - Task create/detail/update/delete
- Expenses:
  - Site expenses list
  - Expense create
- Dashboard:
  - Summary metrics cards
- Contractor supervisor management:
  - Supervisor list/create/detail
  - Permission update
  - Site assignment
- Supervisor:
  - Worker create

## Endpoint Map
### Auth
- `POST /auth/send-otp` -> `{ message, otp_for_dev }`
- `POST /auth/verify-otp` -> `{ access_token, refresh_token, token_type }`
- `POST /auth/refresh-token` -> `{ access_token, token_type }`
- `POST /auth/invite-contractor` -> `{ id, message }`
- `POST /auth/resend-set-password-link` -> `{ message }`
- `POST /auth/set-password` -> `{ message }`
- `POST /auth/login` -> `{ access_token, refresh_token, token_type }`

### Tenant
- `POST /tenants` -> `{ tenant_id, name, schema_name }`
- `POST /tenants/subscription` -> `{ subscription_id }`

### Projects
- `POST /projects` -> `{ id }`
- `GET /projects` -> `Project[]`
- `GET /projects/{project_id}` -> `Project`
- `PUT /projects/{project_id}` -> `{ message: "Updated" }`
- `DELETE /projects/{project_id}` -> `{ message: "Deleted" }`

### Sites
- `POST /sites` -> `{ id }`
- `GET /sites` -> `Site[]` (supervisor list is assignment-filtered)
- `GET /sites/{site_id}` -> `Site`
- `PUT /sites/{site_id}` -> `{ message: "Updated" }`
- `DELETE /sites/{site_id}` -> `{ message: "Deleted" }`

### Materials
- `POST /materials` -> `{ id }`
- `POST /material-transactions` -> `{ id }`
- `GET /site/{site_id}/materials-summary` -> `[{ material_id, name, unit, total_received, total_used, remaining_stock }]`

### Tasks
- `POST /tasks` -> `{ id }`
- `PUT /tasks/{task_id}` -> `{ message: "Updated" }`
- `GET /tasks/{task_id}` -> `Task`
- `GET /site/{site_id}/tasks` -> `Task[]`
- `DELETE /tasks/{task_id}` -> `{ message: "Deleted" }`

### Expenses
- `POST /expenses` -> `{ id }`
- `GET /site/{site_id}/expenses` -> `Expense[]`

### Dashboard
- `GET /dashboard/summary` -> `{ total_sites, active_sites, total_expense, total_material_cost, overall_progress_percentage }`

### Contractor / Supervisor Management
- `POST /contractor/supervisors` -> `{ id }`
- `GET /contractor/supervisors` -> `Supervisor[]`
- `GET /contractor/supervisors/{supervisor_id}` -> `SupervisorDetail`
- `GET /contractor/supervisors/{supervisor_id}/permissions` -> `[{ permission_code, is_enabled }]`
- `PUT /contractor/supervisors/{supervisor_id}/permissions` -> `{ message: "Updated" }`
- `POST /contractor/supervisors/{supervisor_id}/sites/{site_id}` -> `{ message: "Assigned" }`
- `POST /workers` -> `{ id }`

## Client Validation Rules
- Password: 8-128 chars
- Tenant name: 2-140
- Tenant schema name: 3-63 (lowercase/underscore format)
- Name fields: 2-120
- Phone min length: 8
- Task progress: 0-100
- Expense amount: >= 0
- Material transaction:
  - `quantity_received >= 0`
  - `quantity_used >= 0`
  - not both zero

## UX/State Requirements
- Central API client with tenant header injection
- Auth token storage and attach bearer token on protected calls
- Role/permission-based route and component guards
- Loading + empty + error states on all list/detail screens
- Confirmation for deletes
- Consistent success/error toasts
- On `402`, show subscription-blocking state and prevent protected actions

## Backend Constraints to Note
- Many list/detail endpoints return raw DB rows; strict versioned API contract not yet formalized.
- Numeric values may be returned as decimals/JSON numbers; parse safely for currency display.
- `/auth/refresh-token` currently issues a new token from optional subject and does not validate a refresh token payload.

## Frontend v1 Acceptance Criteria
- Full auth flow works (set password + login)
- Tenant header is applied to all protected routes
- Contractor can complete core CRUD and management flows
- Supervisor sees only allowed actions and assigned-site data
- Dashboard summary renders accurate aggregates
- App handles all major HTTP error states cleanly
