from datetime import date
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def insert_tenant(db: AsyncSession, name: str, schema_name: str) -> dict:
    result = await db.execute(
        text(
            """
            insert into public.tenants (name, schema_name)
            values (:name, :schema_name)
            returning id, name, schema_name
            """
        ),
        {'name': name, 'schema_name': schema_name},
    )
    return dict(result.mappings().one())


async def create_trial_subscription(db: AsyncSession, tenant_id: UUID, trial_days: int) -> UUID:
    result = await db.execute(
        text(
            """
            insert into public.tenant_subscriptions (
              tenant_id,
              plan_name,
              start_date,
              end_date,
              is_active,
              extra_sites_count,
              trial_start_date,
              trial_end_date,
              is_trial_active
            )
            values (
              :tenant_id,
              null,
              null,
              null,
              false,
              0,
              current_date,
              current_date + make_interval(days => :trial_days),
              true
            )
            returning id
            """
        ),
        {'tenant_id': str(tenant_id), 'trial_days': trial_days},
    )
    return result.scalar_one()


async def upsert_subscription(
    db: AsyncSession,
    tenant_id: UUID,
    plan_name: str,
    start_date: date,
    end_date: date,
    is_active: bool,
    extra_sites_count: int,
) -> UUID:
    result = await db.execute(
        text(
            """
            insert into public.tenant_subscriptions (
              tenant_id,
              plan_name,
              start_date,
              end_date,
              is_active,
              extra_sites_count,
              trial_start_date,
              trial_end_date,
              is_trial_active
            )
            values (
              :tenant_id,
              :plan_name,
              :start_date,
              :end_date,
              :is_active,
              :extra_sites_count,
              current_date,
              current_date,
              false
            )
            on conflict (tenant_id)
            do update set
              plan_name=excluded.plan_name,
              start_date=excluded.start_date,
              end_date=excluded.end_date,
              is_active=excluded.is_active,
              extra_sites_count=excluded.extra_sites_count,
              is_trial_active=false,
              updated_at=now()
            returning id
            """
        ),
        {
            'tenant_id': str(tenant_id),
            'plan_name': plan_name,
            'start_date': start_date,
            'end_date': end_date,
            'is_active': is_active,
            'extra_sites_count': extra_sites_count,
        },
    )
    return result.scalar_one()


async def add_extra_sites(db: AsyncSession, tenant_id: UUID, additional_sites: int) -> UUID:
    result = await db.execute(
        text(
            """
            update public.tenant_subscriptions
            set extra_sites_count=extra_sites_count + :additional_sites,
                updated_at=now()
            where tenant_id=:tenant_id
            returning id
            """
        ),
        {'tenant_id': str(tenant_id), 'additional_sites': additional_sites},
    )
    updated = result.scalar_one_or_none()
    if updated is not None:
        return updated

    created = await db.execute(
        text(
            """
            insert into public.tenant_subscriptions (
              tenant_id,
              plan_name,
              start_date,
              end_date,
              is_active,
              extra_sites_count,
              trial_start_date,
              trial_end_date,
              is_trial_active
            )
            values (
              :tenant_id,
              null,
              null,
              null,
              false,
              :additional_sites,
              current_date,
              current_date,
              false
            )
            returning id
            """
        ),
        {'tenant_id': str(tenant_id), 'additional_sites': additional_sites},
    )
    return created.scalar_one()


async def fetch_subscription_context(db: AsyncSession, tenant_id: UUID) -> dict | None:
    result = await db.execute(
        text(
            """
            select
              ts.id,
              ts.tenant_id,
              ts.plan_name,
              ts.start_date,
              ts.end_date,
              ts.is_active,
              ts.extra_sites_count,
              ts.trial_start_date,
              ts.trial_end_date,
              ts.is_trial_active,
              p.max_sites,
              p.price_usd_monthly
            from public.tenant_subscriptions ts
            left join public.plans p on p.name = ts.plan_name and p.is_active=true
            where ts.tenant_id=:tenant_id
            """
        ),
        {'tenant_id': str(tenant_id)},
    )
    row = result.mappings().one_or_none()
    return dict(row) if row else None


async def plan_exists(db: AsyncSession, plan_name: str) -> bool:
    result = await db.execute(
        text("select exists(select 1 from public.plans where name=:name and is_active=true)"),
        {'name': plan_name},
    )
    return bool(result.scalar_one())


async def list_plans(db: AsyncSession) -> list[dict]:
    result = await db.execute(
        text(
            """
            select name, price_usd_monthly, max_sites
            from public.plans
            where is_active=true
            order by price_usd_monthly
            """
        )
    )
    return [dict(row) for row in result.mappings().all()]


async def fetch_tenant_context(db: AsyncSession, tenant_id: UUID) -> dict | None:
    result = await db.execute(
        text('select id, schema_name from public.tenants where id=:tenant_id and is_active=true'),
        {'tenant_id': str(tenant_id)},
    )
    row = result.mappings().one_or_none()
    return dict(row) if row else None
