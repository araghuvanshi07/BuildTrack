PUBLIC_STATEMENTS = [
    "create extension if not exists pgcrypto",
    """
    create table if not exists public.tenants (
      id uuid primary key default gen_random_uuid(),
      name varchar(140) not null,
      schema_name varchar(63) not null unique,
      is_active boolean not null default true,
      created_at timestamptz not null default now(),
      updated_at timestamptz not null default now()
    )
    """,
    """
    create table if not exists public.plans (
      id uuid primary key default gen_random_uuid(),
      code varchar(50) not null unique,
      name varchar(120) not null,
      monthly_price_inr numeric(12,2) not null check (monthly_price_inr >= 0),
      yearly_price_inr numeric(12,2) not null check (yearly_price_inr >= 0),
      is_active boolean not null default true,
      created_at timestamptz not null default now(),
      updated_at timestamptz not null default now()
    )
    """,
    """
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
    )
    """,
    """
    create unique index if not exists uq_tenant_single_live_subscription
    on public.tenant_subscriptions (tenant_id)
    where status in ('TRIALING','ACTIVE','PAST_DUE')
    """,
    """
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
    )
    """,
    """
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
    $$
    """,
    """
    insert into public.plans (code, name, monthly_price_inr, yearly_price_inr)
    values ('buildtrack_core', 'BuildTrack Core', 1999.00, 19999.00)
    on conflict (code) do nothing
    """,
]


def tenant_schema_statements(schema_name: str) -> list[str]:
    return [
        f"create schema if not exists {schema_name}",
        f"""
        create table if not exists {schema_name}.users (
          id uuid primary key default gen_random_uuid(),
          name varchar(120) not null,
          email varchar(255) unique,
          phone varchar(20) unique not null,
          role varchar(20) not null check (role in ('ADMIN','CONTRACTOR','SUPERVISOR')),
          password_hash text,
          password_updated_at timestamptz,
          is_active boolean not null default true,
          created_at timestamptz not null default now(),
          updated_at timestamptz not null default now()
        )
        """,
        f"""
        create table if not exists {schema_name}.supervisor_permissions (
          supervisor_id uuid not null references {schema_name}.users(id) on delete cascade,
          permission_code varchar(40) not null check (
            permission_code in (
              'add_worker',
              'mark_attendance',
              'create_site',
              'create_task',
              'add_expense',
              'approve_expense',
              'view_reports'
            )
          ),
          is_enabled boolean not null default true,
          created_at timestamptz not null default now(),
          updated_at timestamptz not null default now(),
          primary key (supervisor_id, permission_code)
        )
        """,
        f"""
        create table if not exists {schema_name}.projects (
          id uuid primary key default gen_random_uuid(),
          name varchar(150) not null,
          location text,
          start_date date,
          estimated_budget numeric(14,2),
          contractor_id uuid,
          created_at timestamptz not null default now(),
          updated_at timestamptz not null default now(),
          version bigint not null default 1,
          is_deleted boolean not null default false
        )
        """,
        f"""
        create table if not exists {schema_name}.sites (
          id uuid primary key default gen_random_uuid(),
          project_id uuid not null references {schema_name}.projects(id),
          supervisor_id uuid,
          status varchar(20) not null check (status in ('active','completed','paused')),
          created_at timestamptz not null default now(),
          updated_at timestamptz not null default now(),
          version bigint not null default 1,
          is_deleted boolean not null default false
        )
        """,
        f"""
        create table if not exists {schema_name}.materials (
          id uuid primary key default gen_random_uuid(),
          name varchar(120) not null,
          unit varchar(30) not null,
          default_unit_cost numeric(12,2),
          created_at timestamptz not null default now(),
          updated_at timestamptz not null default now(),
          version bigint not null default 1,
          is_deleted boolean not null default false
        )
        """,
        f"""
        create table if not exists {schema_name}.material_transactions (
          id uuid primary key default gen_random_uuid(),
          site_id uuid not null references {schema_name}.sites(id),
          material_id uuid not null references {schema_name}.materials(id),
          quantity_received numeric(12,3) not null default 0,
          quantity_used numeric(12,3) not null default 0,
          unit_cost numeric(12,2),
          photo_url text,
          notes text,
          created_at timestamptz not null default now(),
          updated_at timestamptz not null default now(),
          version bigint not null default 1,
          is_deleted boolean not null default false,
          check (quantity_received >= 0 and quantity_used >= 0),
          check (quantity_received > 0 or quantity_used > 0)
        )
        """,
        f"""
        create table if not exists {schema_name}.tasks (
          id uuid primary key default gen_random_uuid(),
          site_id uuid not null references {schema_name}.sites(id),
          title varchar(200) not null,
          status varchar(20) not null check (status in ('pending','in_progress','completed')),
          progress_percent int not null default 0 check (progress_percent between 0 and 100),
          media_url text,
          created_at timestamptz not null default now(),
          updated_at timestamptz not null default now(),
          version bigint not null default 1,
          is_deleted boolean not null default false
        )
        """,
        f"""
        create table if not exists {schema_name}.expenses (
          id uuid primary key default gen_random_uuid(),
          site_id uuid not null references {schema_name}.sites(id),
          category varchar(80) not null,
          amount numeric(14,2) not null check (amount >= 0),
          description text,
          receipt_url text,
          created_at timestamptz not null default now(),
          updated_at timestamptz not null default now(),
          version bigint not null default 1,
          is_deleted boolean not null default false
        )
        """,
        f"""
        create table if not exists {schema_name}.supervisor_site_assignments (
          supervisor_id uuid not null references {schema_name}.users(id) on delete cascade,
          site_id uuid not null references {schema_name}.sites(id) on delete cascade,
          created_at timestamptz not null default now(),
          primary key (supervisor_id, site_id)
        )
        """,
        f"""
        create table if not exists {schema_name}.workers (
          id uuid primary key default gen_random_uuid(),
          site_id uuid not null references {schema_name}.sites(id),
          name varchar(120) not null,
          phone varchar(20),
          created_by uuid,
          created_at timestamptz not null default now(),
          updated_at timestamptz not null default now(),
          version bigint not null default 1,
          is_deleted boolean not null default false
        )
        """,
        f"create index if not exists idx_sites_project on {schema_name}.sites(project_id)",
        f"create index if not exists idx_tasks_site_created on {schema_name}.tasks(site_id, created_at desc)",
        f"create index if not exists idx_expenses_site_created on {schema_name}.expenses(site_id, created_at desc)",
        f"create index if not exists idx_mt_site_created on {schema_name}.material_transactions(site_id, created_at desc)",
        f"create index if not exists idx_supervisor_permissions_supervisor on {schema_name}.supervisor_permissions(supervisor_id)",
        f"create index if not exists idx_supervisor_site_assignments_supervisor on {schema_name}.supervisor_site_assignments(supervisor_id)",
        f"create index if not exists idx_workers_site on {schema_name}.workers(site_id)",
    ]
