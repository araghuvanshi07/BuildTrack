from datetime import date
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas import AddExtraSitesRequest, SubscriptionCreateRequest, TenantContext, TenantCreateRequest
from app.db.sql import tenant_schema_statements
from app.repositories import tenants as repo
from app.repositories import sites as sites_repo
from app.utils.tenancy import validate_schema_name

TRIAL_DAYS = 45
TRIAL_SITE_LIMIT = 2
EXTRA_SITE_PRICE_USD_MONTHLY = 5
WRITE_METHODS = {'POST', 'PUT', 'PATCH', 'DELETE'}
SAFE_METHODS = {'GET', 'HEAD', 'OPTIONS'}


async def create_tenant(db: AsyncSession, payload: TenantCreateRequest) -> dict:
    schema_name = validate_schema_name(payload.schema_name)

    tenant_row = await repo.insert_tenant(db, payload.name, schema_name)
    for stmt in tenant_schema_statements(schema_name):
        await db.execute(text(stmt))

    await repo.create_trial_subscription(db, tenant_row['id'], TRIAL_DAYS)
    return {'tenant_id': tenant_row['id'], 'name': tenant_row['name'], 'schema_name': tenant_row['schema_name']}


async def create_subscription(db: AsyncSession, payload: SubscriptionCreateRequest) -> UUID:
    if payload.end_date < payload.start_date:
        raise HTTPException(status_code=400, detail='end_date must be on or after start_date')
    if not await repo.plan_exists(db, payload.plan_name.value):
        raise HTTPException(status_code=400, detail='Invalid plan_name')

    return await repo.upsert_subscription(
        db,
        payload.tenant_id,
        payload.plan_name.value,
        payload.start_date,
        payload.end_date,
        payload.is_active,
        payload.extra_sites_count,
    )


async def add_extra_sites(db: AsyncSession, payload: AddExtraSitesRequest) -> UUID:
    return await repo.add_extra_sites(db, payload.tenant_id, payload.additional_sites)


async def list_plans(db: AsyncSession) -> list[dict]:
    rows = await repo.list_plans(db)
    return [
        {
            'name': row['name'],
            'price_usd_monthly': float(row['price_usd_monthly']),
            'max_sites': row['max_sites'],
            'extra_site_price_usd_monthly': EXTRA_SITE_PRICE_USD_MONTHLY,
        }
        for row in rows
    ]


async def get_tenant_context(db: AsyncSession, tenant_id: UUID) -> TenantContext:
    row = await repo.fetch_tenant_context(db, tenant_id)
    if not row:
        raise HTTPException(status_code=404, detail='Tenant not found or inactive')
    return TenantContext(tenant_id=row['id'], schema_name=row['schema_name'])


def _is_trial_active(ctx: dict, today: date) -> bool:
    return bool(ctx['is_trial_active']) and ctx['trial_start_date'] <= today <= ctx['trial_end_date']


def _is_subscription_active(ctx: dict, today: date) -> bool:
    return bool(ctx['is_active']) and bool(ctx['plan_name']) and bool(ctx['start_date']) and bool(ctx['end_date']) and ctx['start_date'] <= today <= ctx['end_date']


async def get_subscription_state(db: AsyncSession, tenant_id: UUID) -> dict:
    ctx = await repo.fetch_subscription_context(db, tenant_id)
    if not ctx:
        raise HTTPException(status_code=404, detail='Subscription context not found for tenant')

    today = date.today()
    trial_active = _is_trial_active(ctx, today)
    subscription_active = _is_subscription_active(ctx, today)

    return {
        **ctx,
        'trial_active': trial_active,
        'subscription_active': subscription_active,
    }


async def check_subscription_access(db: AsyncSession, tenant: TenantContext, method: str) -> TenantContext:
    state = await get_subscription_state(db, tenant.tenant_id)
    if state['trial_active'] or state['subscription_active']:
        return tenant

    normalized = method.upper()
    if normalized in SAFE_METHODS:
        return tenant
    if normalized in WRITE_METHODS:
        raise HTTPException(status_code=402, detail='Subscription expired. Read-only access allowed')
    return tenant


async def require_active_subscription(db: AsyncSession, tenant: TenantContext) -> TenantContext:
    state = await get_subscription_state(db, tenant.tenant_id)
    if not (state['trial_active'] or state['subscription_active']):
        raise HTTPException(status_code=402, detail='Subscription inactive or expired')
    return tenant


async def ensure_site_creation_allowed(db: AsyncSession, tenant_id: UUID) -> None:
    state = await get_subscription_state(db, tenant_id)
    current_sites = await sites_repo.count_sites(db)

    if state['trial_active']:
        limit = TRIAL_SITE_LIMIT
    elif state['subscription_active']:
        plan_limit = int(state['max_sites'] or 0)
        limit = plan_limit + int(state['extra_sites_count'] or 0)
    else:
        limit = 0

    if current_sites >= limit:
        raise HTTPException(status_code=409, detail=f'Site limit reached ({limit}). Upgrade plan or add extra sites.')
