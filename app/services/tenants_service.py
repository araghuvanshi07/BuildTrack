from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas import SubscriptionCreateRequest, TenantContext, TenantCreateRequest
from app.db.sql import tenant_schema_statements
from app.repositories import tenants as repo
from app.utils.tenancy import validate_schema_name


async def create_tenant(db: AsyncSession, payload: TenantCreateRequest) -> dict:
    schema_name = validate_schema_name(payload.schema_name)
    plan_id = await repo.fetch_active_core_plan_id(db)
    if not plan_id:
        raise HTTPException(status_code=500, detail='Default plan missing. Run bootstrap first.')

    tenant_row = await repo.insert_tenant(db, payload.name, schema_name)
    for stmt in tenant_schema_statements(schema_name):
        await db.execute(text(stmt))

    await repo.insert_default_active_subscription(db, tenant_row['id'], plan_id, payload.billing_cycle)
    return {'tenant_id': tenant_row['id'], 'name': tenant_row['name'], 'schema_name': tenant_row['schema_name']}


async def create_subscription(db: AsyncSession, payload: SubscriptionCreateRequest) -> UUID:
    plan_id = await repo.fetch_active_core_plan_id(db)
    if not plan_id:
        raise HTTPException(status_code=500, detail='Default plan missing. Run bootstrap first.')
    try:
        return await repo.insert_subscription(
            db,
            payload.tenant_id,
            plan_id,
            payload.billing_cycle,
            payload.status,
            payload.period_start,
            payload.period_end,
            payload.trial_end,
        )
    except IntegrityError as exc:
        if 'uq_tenant_single_live_subscription' in str(exc):
            raise HTTPException(status_code=409, detail='Tenant already has an active subscription') from exc
        raise


async def get_tenant_context(db: AsyncSession, tenant_id: UUID) -> TenantContext:
    row = await repo.fetch_tenant_context(db, tenant_id)
    if not row:
        raise HTTPException(status_code=404, detail='Tenant not found or inactive')
    return TenantContext(tenant_id=row['id'], schema_name=row['schema_name'])


async def require_active_subscription(db: AsyncSession, tenant: TenantContext) -> TenantContext:
    if not await repo.is_subscription_valid(db, tenant.tenant_id):
        raise HTTPException(status_code=402, detail='Subscription inactive or expired')
    return tenant
