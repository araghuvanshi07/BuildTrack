from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas import SubscriptionCreateRequest, TenantCreateRequest
from app.db.session import get_db
from app.services.tenants_service import create_subscription, create_tenant

router = APIRouter(prefix='/tenants', tags=['tenants'])


@router.post('')
async def create_tenant_endpoint(payload: TenantCreateRequest, db: AsyncSession = Depends(get_db)) -> dict:
    return await create_tenant(db, payload)


@router.post('/subscription')
async def create_subscription_endpoint(payload: SubscriptionCreateRequest, db: AsyncSession = Depends(get_db)) -> dict:
    subscription_id = await create_subscription(db, payload)
    return {'subscription_id': str(subscription_id)}
