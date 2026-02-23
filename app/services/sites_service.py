from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas import SiteCreateRequest, SiteUpdateRequest, UserContext, UserRole
from app.repositories import access_control as access_repo
from app.repositories import sites as repo
from app.services.access_control_service import require_permission
from app.utils.payloads import to_db_payload
from app.utils.tenancy import set_tenant_search_path


def _as_actor(actor: UserContext | str) -> UserContext:
    if isinstance(actor, UserContext):
        return actor
    return UserContext(tenant_id=UUID(int=0), schema_name=actor, user_id=None, role=UserRole.CONTRACTOR)


async def create_site(db: AsyncSession, actor: UserContext | str, payload: SiteCreateRequest) -> UUID:
    actor = _as_actor(actor)
    await require_permission(db, actor, 'create_site')
    await set_tenant_search_path(db, actor.schema_name)
    body = to_db_payload(payload, uuid_fields={'project_id', 'supervisor_id'}, enum_fields={'status'})
    return await repo.create_site(db, body)


async def list_sites(db: AsyncSession, actor: UserContext | str) -> list[dict]:
    actor = _as_actor(actor)
    await set_tenant_search_path(db, actor.schema_name)
    rows = await repo.list_sites(db)
    if actor.role != UserRole.SUPERVISOR or not actor.user_id:
        return rows
    filtered: list[dict] = []
    for row in rows:
        if await access_repo.is_supervisor_assigned_to_site(db, actor.user_id, UUID(str(row['id']))):
            filtered.append(row)
    return filtered


async def get_site(db: AsyncSession, actor: UserContext | str, site_id: UUID) -> dict:
    actor = _as_actor(actor)
    await set_tenant_search_path(db, actor.schema_name)
    row = await repo.get_site(db, site_id)
    if not row:
        raise HTTPException(status_code=404, detail='Site not found')
    if actor.role == UserRole.SUPERVISOR and actor.user_id:
        await require_permission(db, actor, 'mark_attendance', site_id)
    return row


async def update_site(db: AsyncSession, actor: UserContext | str, site_id: UUID, payload: SiteUpdateRequest) -> None:
    actor = _as_actor(actor)
    await require_permission(db, actor, 'create_site', site_id)
    await set_tenant_search_path(db, actor.schema_name)
    row = await repo.get_site(db, site_id)
    if not row:
        raise HTTPException(status_code=404, detail='Site not found')
    data = to_db_payload(payload, exclude_none=True, uuid_fields={'supervisor_id'}, enum_fields={'status'})
    if not data:
        return
    await repo.update_site(db, site_id, data)


async def delete_site(db: AsyncSession, actor: UserContext | str, site_id: UUID) -> None:
    actor = _as_actor(actor)
    await require_permission(db, actor, 'create_site', site_id)
    await set_tenant_search_path(db, actor.schema_name)
    row = await repo.get_site(db, site_id)
    if not row:
        raise HTTPException(status_code=404, detail='Site not found')
    await repo.delete_site(db, site_id)
