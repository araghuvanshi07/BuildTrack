from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def create_material(db: AsyncSession, payload: dict):
    result = await db.execute(
        text(
            """
            insert into materials (name, unit, default_unit_cost)
            values (:name, :unit, :default_unit_cost)
            returning id
            """
        ),
        payload,
    )
    return result.scalar_one()


async def create_material_transaction(db: AsyncSession, payload: dict):
    result = await db.execute(
        text(
            """
            insert into material_transactions (
              site_id, material_id, quantity_received, quantity_used, unit_cost, photo_url, notes
            ) values (
              :site_id, :material_id, :quantity_received, :quantity_used, :unit_cost, :photo_url, :notes
            ) returning id
            """
        ),
        payload,
    )
    return result.scalar_one()


async def materials_summary(db: AsyncSession, site_id: str) -> list[dict]:
    result = await db.execute(
        text(
            """
            select
              mt.material_id,
              m.name,
              m.unit,
              coalesce(sum(mt.quantity_received), 0) as total_received,
              coalesce(sum(mt.quantity_used), 0) as total_used,
              coalesce(sum(mt.quantity_received), 0) - coalesce(sum(mt.quantity_used), 0) as remaining_stock
            from material_transactions mt
            join materials m on m.id = mt.material_id
            where mt.site_id=:site_id and mt.is_deleted=false
            group by mt.material_id, m.name, m.unit
            order by m.name
            """
        ),
        {'site_id': site_id},
    )
    return [dict(row) for row in result.mappings().all()]
