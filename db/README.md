# BuildTrack DB - Flat Subscription Model

## What this migration includes
- Flat contractor subscription (monthly/yearly)
- Unlimited sites (no site-based billing limit table/logic)
- Optional add-ons (WhatsApp alerts, PDF exports, advanced reports)
- Billing support tables (subscriptions, invoices, payments)
- Helper function for backend gate checks:
  - `public.is_tenant_subscription_valid(tenant_id uuid)`

## Apply on local Postgres
```bash
psql -d <your_db_name> -f db/001_subscription_flat_model.sql
```

## Basic backend check query
```sql
select public.is_tenant_subscription_valid('<tenant_uuid>'::uuid);
```

## API gating logic
- If helper function returns `true`: allow protected write/read APIs.
- If `false`: return payment/subscription error response.
