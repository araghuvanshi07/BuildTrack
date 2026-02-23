from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def create_task(db: AsyncSession, payload: dict) -> UUID:
    result = await db.execute(
        text(
            """
            insert into tasks (site_id, title, status, progress_percent, media_url)
            values (:site_id, :title, :status, :progress_percent, :media_url)
            returning id
            """
        ),
        payload,
    )
    return result.scalar_one()


async def update_task(db: AsyncSession, task_id: UUID, data: dict) -> None:
    sets = ', '.join([f"{k}=:{k}" for k in data.keys()]) + ', updated_at=now(), version=version+1'
    data['task_id'] = str(task_id)
    await db.execute(text(f'update tasks set {sets} where id=:task_id and is_deleted=false'), data)


async def get_task(db: AsyncSession, task_id: UUID) -> dict | None:
    result = await db.execute(text('select * from tasks where id=:id and is_deleted=false'), {'id': str(task_id)})
    row = result.mappings().one_or_none()
    return dict(row) if row else None


async def list_tasks(db: AsyncSession, site_id: UUID) -> list[dict]:
    result = await db.execute(
        text('select * from tasks where site_id=:site_id and is_deleted=false order by created_at desc'),
        {'site_id': str(site_id)},
    )
    return [dict(row) for row in result.mappings().all()]


async def delete_task(db: AsyncSession, task_id: UUID) -> None:
    await db.execute(
        text(
            """
            update tasks
            set is_deleted=true, updated_at=now(), version=version+1
            where id=:task_id and is_deleted=false
            """
        ),
        {'task_id': str(task_id)},
    )
