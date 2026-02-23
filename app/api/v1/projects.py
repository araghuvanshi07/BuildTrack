from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas import ProjectCreateRequest, ProjectUpdateRequest, TenantContext
from app.core.dependencies import get_current_paid_tenant
from app.db.session import get_db
from app.services.projects_service import create_project, delete_project, get_project, list_projects, update_project

router = APIRouter(prefix='/projects', tags=['projects'])


@router.post('')
async def create_project_endpoint(
    payload: ProjectCreateRequest,
    tenant: TenantContext = Depends(get_current_paid_tenant),
    db: AsyncSession = Depends(get_db),
) -> dict:
    project_id = await create_project(db, tenant.schema_name, payload)
    return {'id': str(project_id)}


@router.get('')
async def list_projects_endpoint(
    tenant: TenantContext = Depends(get_current_paid_tenant),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    return await list_projects(db, tenant.schema_name)


@router.get('/{project_id}')
async def get_project_endpoint(
    project_id: UUID,
    tenant: TenantContext = Depends(get_current_paid_tenant),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await get_project(db, tenant.schema_name, project_id)


@router.put('/{project_id}')
async def update_project_endpoint(
    project_id: UUID,
    payload: ProjectUpdateRequest,
    tenant: TenantContext = Depends(get_current_paid_tenant),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await update_project(db, tenant.schema_name, project_id, payload)
    return {'message': 'Updated'}


@router.delete('/{project_id}')
async def delete_project_endpoint(
    project_id: UUID,
    tenant: TenantContext = Depends(get_current_paid_tenant),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await delete_project(db, tenant.schema_name, project_id)
    return {'message': 'Deleted'}
