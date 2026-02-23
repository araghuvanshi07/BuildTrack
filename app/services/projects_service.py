from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas import ProjectCreateRequest, ProjectUpdateRequest
from app.repositories import projects as repo
from app.utils.payloads import to_db_payload
from app.utils.tenancy import set_tenant_search_path


async def create_project(db: AsyncSession, schema_name: str, payload: ProjectCreateRequest) -> UUID:
    await set_tenant_search_path(db, schema_name)
    body = to_db_payload(payload, uuid_fields={'contractor_id'})
    return await repo.create_project(db, body)


async def list_projects(db: AsyncSession, schema_name: str) -> list[dict]:
    await set_tenant_search_path(db, schema_name)
    return await repo.list_projects(db)


async def get_project(db: AsyncSession, schema_name: str, project_id: UUID) -> dict:
    await set_tenant_search_path(db, schema_name)
    row = await repo.get_project(db, project_id)
    if not row:
        raise HTTPException(status_code=404, detail='Project not found')
    return row


async def update_project(db: AsyncSession, schema_name: str, project_id: UUID, payload: ProjectUpdateRequest) -> None:
    await set_tenant_search_path(db, schema_name)
    row = await repo.get_project(db, project_id)
    if not row:
        raise HTTPException(status_code=404, detail='Project not found')
    data = to_db_payload(payload, exclude_none=True, uuid_fields={'contractor_id'})
    if not data:
        return
    await repo.update_project(db, project_id, data)


async def delete_project(db: AsyncSession, schema_name: str, project_id: UUID) -> None:
    await set_tenant_search_path(db, schema_name)
    row = await repo.get_project(db, project_id)
    if not row:
        raise HTTPException(status_code=404, detail='Project not found')
    await repo.delete_project(db, project_id)
