from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas import MaterialCreateRequest, MaterialTransactionCreateRequest
from app.repositories import materials as repo
from app.utils.payloads import to_db_payload
from app.utils.tenancy import set_tenant_search_path


async def create_material(db: AsyncSession, schema_name: str, payload: MaterialCreateRequest) -> UUID:
    await set_tenant_search_path(db, schema_name)
    return await repo.create_material(db, to_db_payload(payload))


async def create_material_transaction(db: AsyncSession, schema_name: str, payload: MaterialTransactionCreateRequest) -> UUID:
    await set_tenant_search_path(db, schema_name)
    body = to_db_payload(payload, uuid_fields={'site_id', 'material_id'})
    return await repo.create_material_transaction(db, body)


async def materials_summary(db: AsyncSession, schema_name: str, site_id: UUID) -> list[dict]:
    await set_tenant_search_path(db, schema_name)
    return await repo.materials_summary(db, str(site_id))
