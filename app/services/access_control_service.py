from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas import SupervisorCreateRequest, TenantContext, UserContext, UserRole, WorkerCreateRequest
from app.services.auth_service import send_set_password_for_user
from app.repositories import access_control as repo
from app.utils.payloads import to_db_payload
from app.utils.permissions import ALL_SUPERVISOR_PERMISSIONS, DEFAULT_SUPERVISOR_PERMISSIONS
from app.utils.tenancy import set_tenant_search_path


async def get_user_context(db: AsyncSession, tenant: UserContext, user_id: UUID) -> UserContext:
    await set_tenant_search_path(db, tenant.schema_name)
    user = await repo.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail='User not found in tenant')
    return UserContext(
        tenant_id=tenant.tenant_id,
        schema_name=tenant.schema_name,
        user_id=user['id'],
        role=UserRole(user['role']),
    )


def _require_contractor(actor: UserContext) -> None:
    if actor.role != UserRole.CONTRACTOR:
        raise HTTPException(status_code=403, detail='Only contractor can perform this action')


async def create_supervisor(db: AsyncSession, actor: UserContext, payload: SupervisorCreateRequest) -> UUID:
    _require_contractor(actor)
    await set_tenant_search_path(db, actor.schema_name)
    supervisor_id = await repo.create_supervisor(db, to_db_payload(payload))
    supervisor = await repo.get_user_by_id(db, supervisor_id)
    if not supervisor:
        raise HTTPException(status_code=500, detail='Failed to create supervisor')
    for code in DEFAULT_SUPERVISOR_PERMISSIONS:
        await repo.upsert_supervisor_permission(db, supervisor_id, code, True)
    await send_set_password_for_user(db, tenant=TenantContext(tenant_id=actor.tenant_id, schema_name=actor.schema_name), user=supervisor)
    return supervisor_id


async def set_supervisor_permission(
    db: AsyncSession,
    actor: UserContext,
    supervisor_id: UUID,
    permission_code: str,
    is_enabled: bool,
) -> None:
    _require_contractor(actor)
    if permission_code not in ALL_SUPERVISOR_PERMISSIONS:
        raise HTTPException(status_code=400, detail='Invalid permission code')
    if permission_code in DEFAULT_SUPERVISOR_PERMISSIONS and not is_enabled:
        raise HTTPException(status_code=400, detail='Default supervisor permissions cannot be disabled')
    await set_tenant_search_path(db, actor.schema_name)
    user = await repo.get_user_by_id(db, supervisor_id)
    if not user or user['role'] != UserRole.SUPERVISOR.value:
        raise HTTPException(status_code=404, detail='Supervisor not found')
    await repo.upsert_supervisor_permission(db, supervisor_id, permission_code, is_enabled)


async def list_permissions(db: AsyncSession, actor: UserContext, supervisor_id: UUID) -> list[dict]:
    _require_contractor(actor)
    await set_tenant_search_path(db, actor.schema_name)
    user = await repo.get_user_by_id(db, supervisor_id)
    if not user or user['role'] != UserRole.SUPERVISOR.value:
        raise HTTPException(status_code=404, detail='Supervisor not found')
    perms = {row['permission_code']: bool(row['is_enabled']) for row in await repo.list_supervisor_permissions(db, supervisor_id)}
    for default_code in DEFAULT_SUPERVISOR_PERMISSIONS:
        perms[default_code] = True
    return [{'permission_code': code, 'is_enabled': enabled} for code, enabled in sorted(perms.items())]


async def assign_supervisor_site(db: AsyncSession, actor: UserContext, supervisor_id: UUID, site_id: UUID) -> None:
    _require_contractor(actor)
    await set_tenant_search_path(db, actor.schema_name)
    user = await repo.get_user_by_id(db, supervisor_id)
    if not user or user['role'] != UserRole.SUPERVISOR.value:
        raise HTTPException(status_code=404, detail='Supervisor not found')
    await repo.assign_supervisor_to_site(db, supervisor_id, site_id)


async def require_permission(
    db: AsyncSession,
    actor: UserContext,
    permission_code: str,
    site_id: UUID | None = None,
) -> None:
    if actor.role == UserRole.CONTRACTOR:
        return
    if actor.role != UserRole.SUPERVISOR:
        raise HTTPException(status_code=403, detail='Role not allowed')

    await set_tenant_search_path(db, actor.schema_name)
    is_allowed = await repo.has_permission(db, actor.user_id, permission_code) if actor.user_id else False
    if not is_allowed:
        raise HTTPException(status_code=403, detail=f'Missing permission: {permission_code}')

    if site_id and actor.user_id:
        is_assigned = await repo.is_supervisor_assigned_to_site(db, actor.user_id, site_id)
        if not is_assigned:
            raise HTTPException(status_code=403, detail='Supervisor is not assigned to this site')


async def create_worker(db: AsyncSession, actor: UserContext, payload: WorkerCreateRequest) -> UUID:
    await require_permission(db, actor, 'add_worker', payload.site_id)
    await set_tenant_search_path(db, actor.schema_name)
    body = to_db_payload(payload, uuid_fields={'site_id'})
    body['created_by'] = str(actor.user_id) if actor.user_id else None
    return await repo.create_worker(db, body)


async def list_supervisors(db: AsyncSession, actor: UserContext) -> list[dict]:
    _require_contractor(actor)
    await set_tenant_search_path(db, actor.schema_name)
    rows = await repo.list_supervisors(db)
    return [{**row, 'id': str(row['id'])} for row in rows]


async def get_supervisor_detail(db: AsyncSession, actor: UserContext, supervisor_id: UUID) -> dict:
    _require_contractor(actor)
    await set_tenant_search_path(db, actor.schema_name)
    row = await repo.get_supervisor_detail(db, supervisor_id)
    if not row:
        raise HTTPException(status_code=404, detail='Supervisor not found')
    site_ids = await repo.list_assigned_site_ids(db, supervisor_id)
    return {**row, 'id': str(row['id']), 'assigned_site_ids': site_ids}
