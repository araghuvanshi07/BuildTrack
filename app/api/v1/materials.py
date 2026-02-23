from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas import MaterialCreateRequest, MaterialTransactionCreateRequest, TenantContext
from app.core.dependencies import get_current_paid_tenant
from app.db.session import get_db
from app.services.materials_service import create_material, create_material_transaction, materials_summary

router = APIRouter(tags=['materials'])


@router.post('/materials')
async def create_material_endpoint(
    payload: MaterialCreateRequest,
    tenant: TenantContext = Depends(get_current_paid_tenant),
    db: AsyncSession = Depends(get_db),
) -> dict:
    material_id = await create_material(db, tenant.schema_name, payload)
    return {'id': str(material_id)}


@router.post('/material-transactions')
async def create_material_transaction_endpoint(
    payload: MaterialTransactionCreateRequest,
    tenant: TenantContext = Depends(get_current_paid_tenant),
    db: AsyncSession = Depends(get_db),
) -> dict:
    tx_id = await create_material_transaction(db, tenant.schema_name, payload)
    return {'id': str(tx_id)}


@router.get('/site/{site_id}/materials-summary')
async def material_summary_endpoint(
    site_id: UUID,
    tenant: TenantContext = Depends(get_current_paid_tenant),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    return await materials_summary(db, tenant.schema_name, site_id)
