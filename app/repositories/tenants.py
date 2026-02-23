from datetime import datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import BillingCycle, SubscriptionStatus


async def fetch_active_core_plan_id(db: AsyncSession) -> UUID | None:
    result = await db.execute(text("select id from public.plans where code='buildtrack_core' and is_active=true limit 1"))
    return result.scalar_one_or_none()


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


async def insert_default_active_subscription(
    db: AsyncSession,
    tenant_id: UUID,
    plan_id: UUID,
    billing_cycle: BillingCycle,
) -> None:
    months = '1 month' if billing_cycle == BillingCycle.MONTHLY else '1 year'
    await db.execute(
        text(
            f"""
            insert into public.tenant_subscriptions (
                tenant_id, plan_id, billing_cycle, status, period_start, period_end
            ) values (
                :tenant_id, :plan_id, :billing_cycle, 'ACTIVE', now(), now() + interval '{months}'
            )
            """
        ),
        {
            'tenant_id': str(tenant_id),
            'plan_id': str(plan_id),
            'billing_cycle': billing_cycle.value,
        },
    )


async def insert_subscription(
    db: AsyncSession,
    tenant_id: UUID,
    plan_id: UUID,
    billing_cycle: BillingCycle,
    status: SubscriptionStatus,
    period_start: datetime,
    period_end: datetime,
    trial_end: datetime | None,
) -> UUID:
    result = await db.execute(
        text(
            """
            insert into public.tenant_subscriptions (
              tenant_id, plan_id, billing_cycle, status, period_start, period_end, trial_end
            ) values (
              :tenant_id, :plan_id, :billing_cycle, :status, :period_start, :period_end, :trial_end
            )
            returning id
            """
        ),
        {
            'tenant_id': str(tenant_id),
            'plan_id': str(plan_id),
            'billing_cycle': billing_cycle.value,
            'status': status.value,
            'period_start': period_start,
            'period_end': period_end,
            'trial_end': trial_end,
        },
    )
    return result.scalar_one()


async def fetch_tenant_context(db: AsyncSession, tenant_id: UUID) -> dict | None:
    result = await db.execute(
        text("select id, schema_name from public.tenants where id=:tenant_id and is_active=true"),
        {'tenant_id': str(tenant_id)},
    )
    row = result.mappings().one_or_none()
    return dict(row) if row else None


async def is_subscription_valid(db: AsyncSession, tenant_id: UUID) -> bool:
    result = await db.execute(
        text('select public.is_tenant_subscription_valid(:tenant_id)'),
        {'tenant_id': str(tenant_id)},
    )
    return bool(result.scalar_one())
