-- BuildTrack SaaS subscription model (v2)
-- New model: fixed plans + extra site addon + trial-first onboarding.

create extension if not exists pgcrypto;

create table if not exists public.tenants (
  id uuid primary key default gen_random_uuid(),
  name varchar(140) not null,
  schema_name varchar(63) not null unique,
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- Reset old billing model objects when migrating from v1
 drop function if exists public.is_tenant_subscription_valid(uuid);
 drop table if exists public.tenant_add_ons cascade;
 drop table if exists public.tenant_subscriptions cascade;
 drop table if exists public.plans cascade;

create table if not exists public.plans (
  id uuid primary key default gen_random_uuid(),
  name varchar(20) not null unique check (name in ('STARTER', 'GROWTH', 'PRO')),
  price_usd_monthly numeric(10,2) not null check (price_usd_monthly >= 0),
  max_sites int not null check (max_sites >= 1),
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.tenant_subscriptions (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null unique references public.tenants(id) on delete cascade,
  plan_name varchar(20) references public.plans(name),
  start_date date,
  end_date date,
  is_active boolean not null default false,
  extra_sites_count int not null default 0 check (extra_sites_count >= 0),
  trial_start_date date not null,
  trial_end_date date not null,
  is_trial_active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (trial_end_date >= trial_start_date)
);

create index if not exists idx_tenant_subscriptions_tenant
on public.tenant_subscriptions (tenant_id);

insert into public.plans (name, price_usd_monthly, max_sites)
values
  ('STARTER', 10.00, 3),
  ('GROWTH', 20.00, 5),
  ('PRO', 40.00, 10)
on conflict (name) do update
set
  price_usd_monthly = excluded.price_usd_monthly,
  max_sites = excluded.max_sites,
  updated_at = now();
