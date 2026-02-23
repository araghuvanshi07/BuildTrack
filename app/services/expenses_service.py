from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas import ExpenseCreateRequest, UserContext
from app.models.enums import UserRole
from app.repositories import expenses as repo
from app.services.access_control_service import require_permission
from app.utils.payloads import to_db_payload
from app.utils.tenancy import set_tenant_search_path


def _as_actor(actor: UserContext | str) -> UserContext:
    if isinstance(actor, UserContext):
        return actor
    return UserContext(tenant_id=UUID(int=0), schema_name=actor, user_id=None, role=UserRole.CONTRACTOR)


async def create_expense(db: AsyncSession, actor: UserContext | str, payload: ExpenseCreateRequest) -> UUID:
    actor = _as_actor(actor)
    await require_permission(db, actor, 'add_expense', payload.site_id)
    await set_tenant_search_path(db, actor.schema_name)
    body = to_db_payload(payload, uuid_fields={'site_id'})
    return await repo.create_expense(db, body)


async def list_expenses(db: AsyncSession, actor: UserContext | str, site_id: UUID) -> list[dict]:
    actor = _as_actor(actor)
    await require_permission(db, actor, 'mark_attendance', site_id)
    await set_tenant_search_path(db, actor.schema_name)
    return await repo.list_expenses(db, site_id)
