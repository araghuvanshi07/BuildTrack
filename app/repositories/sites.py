from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def create_site(db: AsyncSession, payload: dict) -> UUID:
    result = await db.execute(
        text(
            """
            insert into sites (project_id, supervisor_id, status)
            values (:project_id, :supervisor_id, :status)
            returning id
            """
        ),
        payload,
    )
    return result.scalar_one()


async def list_sites(db: AsyncSession) -> list[dict]:
    result = await db.execute(text('select * from sites where is_deleted=false order by created_at desc'))
    return [dict(row) for row in result.mappings().all()]


async def get_site(db: AsyncSession, site_id: UUID) -> dict | None:
    result = await db.execute(text('select * from sites where id=:id and is_deleted=false'), {'id': str(site_id)})
    row = result.mappings().one_or_none()
    return dict(row) if row else None


async def update_site(db: AsyncSession, site_id: UUID, data: dict) -> None:
    sets = ', '.join([f"{k}=:{k}" for k in data.keys()]) + ', updated_at=now(), version=version+1'
    data['site_id'] = str(site_id)
    await db.execute(text(f'update sites set {sets} where id=:site_id and is_deleted=false'), data)


async def delete_site(db: AsyncSession, site_id: UUID) -> None:
    await db.execute(
        text(
            """
            update sites
            set is_deleted=true, updated_at=now(), version=version+1
            where id=:site_id and is_deleted=false
            """
        ),
        {'site_id': str(site_id)},
    )
