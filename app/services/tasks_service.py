from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas import TaskCreateRequest, TaskUpdateRequest, UserContext
from app.repositories import tasks as repo
from app.services.access_control_service import require_permission
from app.utils.payloads import to_db_payload
from app.utils.tenancy import set_tenant_search_path


def _as_actor(actor: UserContext | str) -> UserContext:
    from app.models.enums import UserRole

    if isinstance(actor, UserContext):
        return actor
    return UserContext(tenant_id=UUID(int=0), schema_name=actor, user_id=None, role=UserRole.CONTRACTOR)


async def create_task(db: AsyncSession, actor: UserContext | str, payload: TaskCreateRequest) -> UUID:
    actor = _as_actor(actor)
    await require_permission(db, actor, 'create_task', payload.site_id)
    await set_tenant_search_path(db, actor.schema_name)
    body = to_db_payload(payload, uuid_fields={'site_id'}, enum_fields={'status'})
    return await repo.create_task(db, body)


async def update_task(db: AsyncSession, actor: UserContext | str, task_id: UUID, payload: TaskUpdateRequest) -> None:
    actor = _as_actor(actor)
    await set_tenant_search_path(db, actor.schema_name)
    row = await repo.get_task(db, task_id)
    if not row:
        raise HTTPException(status_code=404, detail='Task not found')
    site_scope = UUID(str(row['site_id'])) if 'site_id' in row and row['site_id'] is not None else None
    await require_permission(db, actor, 'create_task', site_scope)
    data = to_db_payload(payload, exclude_none=True, enum_fields={'status'})
    if not data:
        return
    await repo.update_task(db, task_id, data)


async def list_tasks(db: AsyncSession, actor: UserContext | str, site_id: UUID) -> list[dict]:
    actor = _as_actor(actor)
    await require_permission(db, actor, 'mark_attendance', site_id)
    await set_tenant_search_path(db, actor.schema_name)
    return await repo.list_tasks(db, site_id)


async def get_task(db: AsyncSession, actor: UserContext | str, task_id: UUID) -> dict:
    actor = _as_actor(actor)
    await set_tenant_search_path(db, actor.schema_name)
    row = await repo.get_task(db, task_id)
    if not row:
        raise HTTPException(status_code=404, detail='Task not found')
    site_scope = UUID(str(row['site_id'])) if 'site_id' in row and row['site_id'] is not None else None
    await require_permission(db, actor, 'mark_attendance', site_scope)
    return row


async def delete_task(db: AsyncSession, actor: UserContext | str, task_id: UUID) -> None:
    actor = _as_actor(actor)
    await set_tenant_search_path(db, actor.schema_name)
    row = await repo.get_task(db, task_id)
    if not row:
        raise HTTPException(status_code=404, detail='Task not found')
    site_scope = UUID(str(row['site_id'])) if 'site_id' in row and row['site_id'] is not None else None
    await require_permission(db, actor, 'create_task', site_scope)
    await repo.delete_task(db, task_id)
