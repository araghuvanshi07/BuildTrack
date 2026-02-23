from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas import SupervisorCreateRequest, SupervisorPermissionUpdateRequest, UserContext
from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.services.access_control_service import (
    assign_supervisor_site,
    create_supervisor,
    get_supervisor_detail,
    list_permissions,
    list_supervisors,
    set_supervisor_permission,
)

router = APIRouter(prefix='/contractor', tags=['contractor'])


@router.post('/supervisors')
async def create_supervisor_endpoint(
    payload: SupervisorCreateRequest,
    actor: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    user_id = await create_supervisor(db, actor, payload)
    return {'id': str(user_id)}


@router.get('/supervisors')
async def list_supervisors_endpoint(
    actor: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    return await list_supervisors(db, actor)


@router.get('/supervisors/{supervisor_id}')
async def get_supervisor_detail_endpoint(
    supervisor_id: UUID,
    actor: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await get_supervisor_detail(db, actor, supervisor_id)


@router.get('/supervisors/{supervisor_id}/permissions')
async def list_supervisor_permissions_endpoint(
    supervisor_id: UUID,
    actor: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    return await list_permissions(db, actor, supervisor_id)


@router.put('/supervisors/{supervisor_id}/permissions')
async def update_supervisor_permissions_endpoint(
    supervisor_id: UUID,
    payload: SupervisorPermissionUpdateRequest,
    actor: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await set_supervisor_permission(db, actor, supervisor_id, payload.permission_code, payload.is_enabled)
    return {'message': 'Updated'}


@router.post('/supervisors/{supervisor_id}/sites/{site_id}')
async def assign_supervisor_site_endpoint(
    supervisor_id: UUID,
    site_id: UUID,
    actor: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await assign_supervisor_site(db, actor, supervisor_id, site_id)
    return {'message': 'Assigned'}
