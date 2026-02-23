from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def get_summary(db: AsyncSession) -> dict:
    site_counts = await db.execute(
        text(
            """
            select
              count(*) as total_sites,
              count(*) filter (where status='active') as active_sites
            from sites
            where is_deleted=false
            """
        )
    )
    site_row = site_counts.mappings().one()

    expense_result = await db.execute(text('select coalesce(sum(amount),0) as total_expense from expenses where is_deleted=false'))
    total_expense = expense_result.scalar_one()

    material_cost_result = await db.execute(
        text(
            """
            select coalesce(sum(quantity_used * coalesce(unit_cost, 0)), 0) as total_material_cost
            from material_transactions
            where is_deleted=false
            """
        )
    )
    total_material_cost = material_cost_result.scalar_one()

    progress_result = await db.execute(
        text(
            """
            select coalesce(avg(progress_percent),0) as overall_progress_percentage
            from tasks
            where is_deleted=false
            """
        )
    )
    overall_progress = progress_result.scalar_one()

    return {
        'total_sites': int(site_row['total_sites']),
        'active_sites': int(site_row['active_sites']),
        'total_expense': float(total_expense),
        'total_material_cost': float(total_material_cost),
        'overall_progress_percentage': round(float(overall_progress), 2),
    }
