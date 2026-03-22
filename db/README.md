# Subscription Schema (v2)

This folder contains SQL for the multi-tenant subscription model used by BuildTrack.

## Features
- Fixed plans: `STARTER`, `GROWTH`, `PRO`
- Trial on tenant creation: 45 days with trial flags
- Extra site tracking via `extra_sites_count`
- Single subscription record per tenant

## Run
```bash
psql -d <your_db_name> -f db/001_subscription_flat_model.sql
```

## Tables
- `public.plans`
- `public.tenant_subscriptions`

## Notes
- v1 billing objects are dropped during migration (`tenant_add_ons`, old `tenant_subscriptions`, old function).
- Access and site-limit logic is enforced in application services/dependencies.
