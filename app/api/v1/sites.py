from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas import SiteCreateRequest, SiteUpdateRequest, UserContext
from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.services.sites_service import create_site, delete_site, get_site, list_sites, update_site

router = APIRouter(prefix='/sites', tags=['sites'])


@router.post('')
async def create_site_endpoint(
    payload: SiteCreateRequest,
    actor: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    site_id = await create_site(db, actor, payload)
    return {'id': str(site_id)}


@router.get('')
async def list_sites_endpoint(
    actor: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    return await list_sites(db, actor)


@router.get('/{site_id}')
async def get_site_endpoint(
    site_id: UUID,
    actor: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await get_site(db, actor, site_id)


@router.put('/{site_id}')
async def update_site_endpoint(
    site_id: UUID,
    payload: SiteUpdateRequest,
    actor: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await update_site(db, actor, site_id, payload)
    return {'message': 'Updated'}


@router.delete('/{site_id}')
async def delete_site_endpoint(
    site_id: UUID,
    actor: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await delete_site(db, actor, site_id)
    return {'message': 'Deleted'}
