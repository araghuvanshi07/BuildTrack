from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def create_project(db: AsyncSession, payload: dict) -> UUID:
    result = await db.execute(
        text(
            """
            insert into projects (name, location, start_date, estimated_budget, contractor_id)
            values (:name, :location, :start_date, :estimated_budget, :contractor_id)
            returning id
            """
        ),
        payload,
    )
    return result.scalar_one()


async def list_projects(db: AsyncSession) -> list[dict]:
    result = await db.execute(text('select * from projects where is_deleted=false order by created_at desc'))
    return [dict(row) for row in result.mappings().all()]


async def get_project(db: AsyncSession, project_id: UUID) -> dict | None:
    result = await db.execute(text('select * from projects where id=:id and is_deleted=false'), {'id': str(project_id)})
    row = result.mappings().one_or_none()
    return dict(row) if row else None


async def update_project(db: AsyncSession, project_id: UUID, data: dict) -> None:
    sets = ', '.join([f"{k}=:{k}" for k in data.keys()]) + ', updated_at=now(), version=version+1'
    data['project_id'] = str(project_id)
    await db.execute(text(f'update projects set {sets} where id=:project_id and is_deleted=false'), data)


async def delete_project(db: AsyncSession, project_id: UUID) -> None:
    await db.execute(
        text(
            """
            update projects
            set is_deleted=true, updated_at=now(), version=version+1
            where id=:project_id and is_deleted=false
            """
        ),
        {'project_id': str(project_id)},
    )
