from datetime import date
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def create_worker(db: AsyncSession, payload: dict) -> UUID:
    result = await db.execute(
        text(
            """
            insert into workers (
              site_id, name, salary_type, daily_wage, monthly_salary, is_attendance_based, phone, created_by
            )
            values (
              :site_id, :name, :salary_type, :daily_wage, :monthly_salary, :is_attendance_based, :phone, :created_by
            )
            returning id
            """
        ),
        payload,
    )
    return result.scalar_one()


async def list_workers(db: AsyncSession, site_id: str | None = None, site_ids: list[str] | None = None) -> list[dict]:
    query = """
        select
          id,
          name,
          site_id,
          salary_type,
          daily_wage,
          monthly_salary,
          is_attendance_based,
          phone,
          created_at
        from workers
        where is_deleted=false
    """
    params: dict = {}
    if site_id:
        query += " and site_id=:site_id"
        params['site_id'] = site_id
    if site_ids is not None:
        query += " and site_id = any(:site_ids)"
        params['site_ids'] = site_ids
    query += " order by created_at desc"
    result = await db.execute(text(query), params)
    return [dict(row) for row in result.mappings().all()]


async def get_worker(db: AsyncSession, worker_id: UUID) -> dict | None:
    result = await db.execute(
        text(
            """
            select
              id,
              name,
              site_id,
              salary_type,
              daily_wage,
              monthly_salary,
              is_attendance_based,
              phone,
              created_at
            from workers
            where id=:worker_id and is_deleted=false
            """
        ),
        {'worker_id': str(worker_id)},
    )
    row = result.mappings().one_or_none()
    return dict(row) if row else None


async def create_attendance(db: AsyncSession, payload: dict) -> UUID:
    result = await db.execute(
        text(
            """
            insert into attendance (worker_id, site_id, date, status, marked_by)
            values (:worker_id, :site_id, :date, :status, :marked_by)
            returning id
            """
        ),
        payload,
    )
    return result.scalar_one()


async def list_attendance(
    db: AsyncSession,
    worker_id: str | None = None,
    site_id: str | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    site_ids: list[str] | None = None,
) -> list[dict]:
    query = """
        select id, worker_id, site_id, date, status, marked_by, created_at
        from attendance
        where 1=1
    """
    params: dict = {}
    if worker_id:
        query += " and worker_id=:worker_id"
        params['worker_id'] = worker_id
    if site_id:
        query += " and site_id=:site_id"
        params['site_id'] = site_id
    if from_date:
        query += " and date>=:from_date"
        params['from_date'] = from_date
    if to_date:
        query += " and date<=:to_date"
        params['to_date'] = to_date
    if site_ids is not None:
        query += " and site_id = any(:site_ids)"
        params['site_ids'] = site_ids

    query += " order by date desc, created_at desc"
    result = await db.execute(text(query), params)
    return [dict(row) for row in result.mappings().all()]


async def list_attendance_for_worker_range(db: AsyncSession, worker_id: UUID, from_date: date, to_date: date) -> list[dict]:
    result = await db.execute(
        text(
            """
            select date, status
            from attendance
            where worker_id=:worker_id and date between :from_date and :to_date
            order by date
            """
        ),
        {'worker_id': str(worker_id), 'from_date': from_date, 'to_date': to_date},
    )
    return [dict(row) for row in result.mappings().all()]


async def create_bonus(db: AsyncSession, payload: dict) -> UUID:
    result = await db.execute(
        text(
            """
            insert into bonuses (worker_id, amount, date, note)
            values (:worker_id, :amount, :date, :note)
            returning id
            """
        ),
        payload,
    )
    return result.scalar_one()


async def list_bonus(
    db: AsyncSession,
    worker_id: str | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    site_ids: list[str] | None = None,
) -> list[dict]:
    query = """
        select b.id, b.worker_id, w.site_id, b.amount, b.date, b.note
        from bonuses b
        join workers w on w.id=b.worker_id
        where w.is_deleted=false
    """
    params: dict = {}
    if worker_id:
        query += " and b.worker_id=:worker_id"
        params['worker_id'] = worker_id
    if from_date:
        query += " and b.date>=:from_date"
        params['from_date'] = from_date
    if to_date:
        query += " and b.date<=:to_date"
        params['to_date'] = to_date
    if site_ids is not None:
        query += " and w.site_id = any(:site_ids)"
        params['site_ids'] = site_ids

    query += " order by b.date desc"
    result = await db.execute(text(query), params)
    return [dict(row) for row in result.mappings().all()]


async def sum_bonus(db: AsyncSession, worker_id: UUID, from_date: date, to_date: date):
    result = await db.execute(
        text(
            """
            select coalesce(sum(amount), 0)
            from bonuses
            where worker_id=:worker_id and date between :from_date and :to_date
            """
        ),
        {'worker_id': str(worker_id), 'from_date': from_date, 'to_date': to_date},
    )
    return result.scalar_one()


async def upsert_salary_settlement(db: AsyncSession, payload: dict) -> UUID:
    result = await db.execute(
        text(
            """
            insert into salary_settlements (worker_id, from_date, to_date, is_paid, paid_on, marked_by)
            values (:worker_id, :from_date, :to_date, :is_paid, :paid_on, :marked_by)
            on conflict (worker_id, from_date, to_date)
            do update set
              is_paid=excluded.is_paid,
              paid_on=excluded.paid_on,
              marked_by=excluded.marked_by,
              updated_at=now()
            returning id
            """
        ),
        payload,
    )
    return result.scalar_one()


async def get_salary_settlement(db: AsyncSession, worker_id: UUID, from_date: date, to_date: date) -> dict | None:
    result = await db.execute(
        text(
            """
            select id, worker_id, from_date, to_date, is_paid, paid_on, marked_by, created_at, updated_at
            from salary_settlements
            where worker_id=:worker_id and from_date=:from_date and to_date=:to_date
            """
        ),
        {'worker_id': str(worker_id), 'from_date': from_date, 'to_date': to_date},
    )
    row = result.mappings().one_or_none()
    return dict(row) if row else None
