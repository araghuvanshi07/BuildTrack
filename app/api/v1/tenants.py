from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from uuid import UUID

from app.api.v1.schemas import AddExtraSitesRequest, SubscriptionCreateRequest, TenantCreateRequest
from app.core.dependencies import verify_razorpay_webhook
from app.db.session import get_db
from app.services.tenants_service import EXTRA_SITE_PRICE_USD_MONTHLY, add_extra_sites, create_subscription, create_tenant, get_subscription_state, list_plans

router = APIRouter(prefix='/tenants', tags=['tenants'])


@router.post('')
async def create_tenant_endpoint(payload: TenantCreateRequest, db: AsyncSession = Depends(get_db)) -> dict:
    return await create_tenant(db, payload)


@router.post('/subscription')
async def create_subscription_endpoint(
    payload: SubscriptionCreateRequest,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_razorpay_webhook),
) -> dict:
    subscription_id = await create_subscription(db, payload)
    return {'subscription_id': str(subscription_id)}


@router.post('/subscription/extra-sites')
async def add_extra_sites_endpoint(
    payload: AddExtraSitesRequest,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_razorpay_webhook),
) -> dict:
    subscription_id = await add_extra_sites(db, payload)
    return {'subscription_id': str(subscription_id)}


@router.get('/plans')
async def list_plans_endpoint(db: AsyncSession = Depends(get_db)) -> list[dict]:
    return await list_plans(db)


@router.get('/{tenant_id}/subscription')
async def tenant_subscription_endpoint(tenant_id: UUID, db: AsyncSession = Depends(get_db)) -> dict:
    state = await get_subscription_state(db, tenant_id)
    return {
        'tenant_id': str(state['tenant_id']),
        'plan_name': state['plan_name'],
        'start_date': state['start_date'],
        'end_date': state['end_date'],
        'is_active': state['is_active'],
        'extra_sites_count': state['extra_sites_count'],
        'trial_start_date': state['trial_start_date'],
        'trial_end_date': state['trial_end_date'],
        'is_trial_active': state['is_trial_active'],
        'trial_active': state['trial_active'],
        'subscription_active': state['subscription_active'],
        'plan_max_sites': state['max_sites'],
        'extra_site_price_usd_monthly': EXTRA_SITE_PRICE_USD_MONTHLY,
    }
