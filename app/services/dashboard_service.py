from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas import UserContext
from app.models.enums import UserRole
from app.repositories import dashboard as repo
from app.services.access_control_service import require_permission
from app.utils.tenancy import set_tenant_search_path


def _as_actor(actor: UserContext | str) -> UserContext:
    from uuid import UUID

    if isinstance(actor, UserContext):
        return actor
    return UserContext(tenant_id=UUID(int=0), schema_name=actor, user_id=None, role=UserRole.CONTRACTOR)


async def get_summary(db: AsyncSession, actor: UserContext | str) -> dict:
    actor = _as_actor(actor)
    await require_permission(db, actor, 'view_reports')
    await set_tenant_search_path(db, actor.schema_name)
    return await repo.get_summary(db)
