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
    "drop function if exists public.is_tenant_subscription_valid(uuid)",
    "drop table if exists public.tenant_add_ons cascade",
    "drop table if exists public.tenant_subscriptions cascade",
    "drop table if exists public.plans cascade",
    """
    create table if not exists public.plans (
      id uuid primary key default gen_random_uuid(),
      name varchar(20) not null unique check (name in ('STARTER', 'GROWTH', 'PRO')),
      price_usd_monthly numeric(10,2) not null check (price_usd_monthly >= 0),
      max_sites int not null check (max_sites >= 1),
      is_active boolean not null default true,
      created_at timestamptz not null default now(),
      updated_at timestamptz not null default now()
    )
    """,
    """
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
    )
    """,
    "create index if not exists idx_tenant_subscriptions_tenant on public.tenant_subscriptions(tenant_id)",
    """
    insert into public.plans (name, price_usd_monthly, max_sites)
    values ('STARTER', 10.00, 3), ('GROWTH', 20.00, 5), ('PRO', 40.00, 10)
    on conflict (name) do update
    set price_usd_monthly=excluded.price_usd_monthly,
        max_sites=excluded.max_sites,
        updated_at=now()
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
          salary_type varchar(20) not null check (salary_type in ('daily','monthly')),
          daily_wage numeric(12,2),
          monthly_salary numeric(12,2),
          is_attendance_based boolean not null default true,
          phone varchar(20),
          created_by uuid,
          created_at timestamptz not null default now(),
          updated_at timestamptz not null default now(),
          version bigint not null default 1,
          is_deleted boolean not null default false,
          check (
            (salary_type='daily' and daily_wage is not null and monthly_salary is null)
            or (salary_type='monthly' and monthly_salary is not null and daily_wage is null)
          )
        )
        """,
        f"""
        create table if not exists {schema_name}.attendance (
          id uuid primary key default gen_random_uuid(),
          worker_id uuid not null references {schema_name}.workers(id) on delete cascade,
          site_id uuid not null references {schema_name}.sites(id) on delete cascade,
          date date not null,
          status varchar(20) not null check (status in ('present','absent','paid_leave','half_day')),
          marked_by uuid,
          created_at timestamptz not null default now(),
          unique (worker_id, date)
        )
        """,
        f"""
        create table if not exists {schema_name}.bonuses (
          id uuid primary key default gen_random_uuid(),
          worker_id uuid not null references {schema_name}.workers(id) on delete cascade,
          amount numeric(12,2) not null check (amount >= 0),
          date date not null,
          note text,
          created_at timestamptz not null default now()
        )
        """,
        f"drop table if exists {schema_name}.payments cascade",
        f"""
        create table if not exists {schema_name}.salary_settlements (
          id uuid primary key default gen_random_uuid(),
          worker_id uuid not null references {schema_name}.workers(id) on delete cascade,
          from_date date not null,
          to_date date not null,
          is_paid boolean not null default false,
          paid_on date,
          marked_by uuid,
          created_at timestamptz not null default now(),
          updated_at timestamptz not null default now(),
          unique (worker_id, from_date, to_date),
          check (to_date >= from_date)
        )
        """,
        f"create index if not exists idx_sites_project on {schema_name}.sites(project_id)",
        f"create index if not exists idx_tasks_site_created on {schema_name}.tasks(site_id, created_at desc)",
        f"create index if not exists idx_expenses_site_created on {schema_name}.expenses(site_id, created_at desc)",
        f"create index if not exists idx_mt_site_created on {schema_name}.material_transactions(site_id, created_at desc)",
        f"create index if not exists idx_supervisor_permissions_supervisor on {schema_name}.supervisor_permissions(supervisor_id)",
        f"create index if not exists idx_supervisor_site_assignments_supervisor on {schema_name}.supervisor_site_assignments(supervisor_id)",
        f"create index if not exists idx_workers_site on {schema_name}.workers(site_id)",
        f"create index if not exists idx_attendance_worker_date on {schema_name}.attendance(worker_id, date)",
        f"create index if not exists idx_attendance_site_date on {schema_name}.attendance(site_id, date)",
        f"create index if not exists idx_bonus_worker_date on {schema_name}.bonuses(worker_id, date)",
        f"create index if not exists idx_settlement_worker_period on {schema_name}.salary_settlements(worker_id, from_date, to_date)",
    ]
