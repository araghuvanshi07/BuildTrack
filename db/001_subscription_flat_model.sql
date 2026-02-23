-- BuildTrack: Minimal Flat Subscription Model (Public Schema Only)
-- Goal: Keep tenant schemas clean, keep billing/subscription management simple.

begin;

create extension if not exists pgcrypto;

-- 1) Tenants
create table if not exists public.tenants (
  id uuid primary key default gen_random_uuid(),
  name varchar(140) not null,
  schema_name varchar(63) not null unique,
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- 2) Plans (flat monthly/yearly)
create table if not exists public.plans (
  id uuid primary key default gen_random_uuid(),
  code varchar(50) not null unique,
  name varchar(120) not null,
  monthly_price_inr numeric(12,2) not null check (monthly_price_inr >= 0),
  yearly_price_inr numeric(12,2) not null check (yearly_price_inr >= 0),
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- 3) Tenant subscriptions (single live subscription per tenant)
create table if not exists public.tenant_subscriptions (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.tenants(id) on delete cascade,
  plan_id uuid not null references public.plans(id),
  billing_cycle varchar(10) not null check (billing_cycle in ('MONTHLY','YEARLY')),
  status varchar(20) not null check (status in ('TRIALING','ACTIVE','PAST_DUE','CANCELED','EXPIRED')),
  period_start timestamptz not null,
  period_end timestamptz not null,
  trial_end timestamptz,
  cancel_at_period_end boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (period_end > period_start)
);

create unique index if not exists uq_tenant_single_live_subscription
on public.tenant_subscriptions (tenant_id)
where status in ('TRIALING','ACTIVE','PAST_DUE');

create index if not exists idx_tenant_subscriptions_lookup
on public.tenant_subscriptions (tenant_id, status, period_end);

-- 4) Optional add-ons per subscription
create table if not exists public.tenant_add_ons (
  id uuid primary key default gen_random_uuid(),
  tenant_subscription_id uuid not null references public.tenant_subscriptions(id) on delete cascade,
  add_on_code varchar(60) not null,
  add_on_name varchar(120) not null,
  price_inr numeric(12,2) not null check (price_inr >= 0),
  billing_cycle varchar(10) not null check (billing_cycle in ('MONTHLY','YEARLY')),
  status varchar(20) not null check (status in ('ACTIVE','CANCELED')),
  period_start timestamptz not null,
  period_end timestamptz not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (period_end > period_start)
);

create index if not exists idx_tenant_addons_lookup
on public.tenant_add_ons (tenant_subscription_id, status);

-- Helper function for API gate checks
create or replace function public.is_tenant_subscription_valid(p_tenant_id uuid)
returns boolean
language sql
stable
as $$
  select exists (
    select 1
    from public.tenant_subscriptions ts
    where ts.tenant_id = p_tenant_id
      and ts.period_end >= now()
      and (
        ts.status = 'ACTIVE'
        or (ts.status = 'TRIALING' and (ts.trial_end is null or ts.trial_end >= now()))
      )
  );
$$;

-- Seed: one core plan
insert into public.plans (code, name, monthly_price_inr, yearly_price_inr)
values ('buildtrack_core', 'BuildTrack Core', 1999.00, 19999.00)
on conflict (code) do nothing;

commit;
