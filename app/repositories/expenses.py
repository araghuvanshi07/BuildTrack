from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def create_expense(db: AsyncSession, payload: dict) -> UUID:
    result = await db.execute(
        text(
            """
            insert into expenses (site_id, category, amount, description, receipt_url)
            values (:site_id, :category, :amount, :description, :receipt_url)
            returning id
            """
        ),
        payload,
    )
    return result.scalar_one()


async def list_expenses(db: AsyncSession, site_id: UUID) -> list[dict]:
    result = await db.execute(
        text('select * from expenses where site_id=:site_id and is_deleted=false order by created_at desc'),
        {'site_id': str(site_id)},
    )
    return [dict(row) for row in result.mappings().all()]
