from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def get_user_by_id(db: AsyncSession, user_id: UUID) -> dict | None:
    result = await db.execute(
        text('select id, name, email, phone, role, is_active from users where id=:id and is_active=true'),
        {'id': str(user_id)},
    )
    row = result.mappings().one_or_none()
    return dict(row) if row else None


async def create_supervisor(db: AsyncSession, payload: dict) -> UUID:
    result = await db.execute(
        text(
            """
            insert into users (name, email, phone, role, is_active)
            values (:name, :email, :phone, 'SUPERVISOR', true)
            returning id
            """
        ),
        payload,
    )
    return result.scalar_one()


async def upsert_supervisor_permission(db: AsyncSession, supervisor_id: UUID, permission_code: str, is_enabled: bool) -> None:
    await db.execute(
        text(
            """
            insert into supervisor_permissions (supervisor_id, permission_code, is_enabled)
            values (:supervisor_id, :permission_code, :is_enabled)
            on conflict (supervisor_id, permission_code)
            do update set is_enabled=excluded.is_enabled, updated_at=now()
            """
        ),
        {'supervisor_id': str(supervisor_id), 'permission_code': permission_code, 'is_enabled': is_enabled},
    )


async def list_supervisor_permissions(db: AsyncSession, supervisor_id: UUID) -> list[dict]:
    result = await db.execute(
        text(
            """
            select permission_code, is_enabled
            from supervisor_permissions
            where supervisor_id=:supervisor_id
            order by permission_code
            """
        ),
        {'supervisor_id': str(supervisor_id)},
    )
    return [dict(row) for row in result.mappings().all()]


async def has_permission(db: AsyncSession, supervisor_id: UUID, permission_code: str) -> bool:
    result = await db.execute(
        text(
            """
            select coalesce((
              select is_enabled
              from supervisor_permissions
              where supervisor_id=:supervisor_id and permission_code=:permission_code
              limit 1
            ), false)
            """
        ),
        {'supervisor_id': str(supervisor_id), 'permission_code': permission_code},
    )
    return bool(result.scalar_one())


async def assign_supervisor_to_site(db: AsyncSession, supervisor_id: UUID, site_id: UUID) -> None:
    await db.execute(
        text(
            """
            insert into supervisor_site_assignments (supervisor_id, site_id)
            values (:supervisor_id, :site_id)
            on conflict (supervisor_id, site_id) do nothing
            """
        ),
        {'supervisor_id': str(supervisor_id), 'site_id': str(site_id)},
    )


async def is_supervisor_assigned_to_site(db: AsyncSession, supervisor_id: UUID, site_id: UUID) -> bool:
    result = await db.execute(
        text(
            """
            select exists(
              select 1
              from supervisor_site_assignments
              where supervisor_id=:supervisor_id and site_id=:site_id
            )
            """
        ),
        {'supervisor_id': str(supervisor_id), 'site_id': str(site_id)},
    )
    return bool(result.scalar_one())


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


async def list_supervisors(db: AsyncSession) -> list[dict]:
    result = await db.execute(
        text(
            """
            select id, name, phone, role, is_active, created_at, updated_at
            from users
            where role='SUPERVISOR' and is_active=true
            order by created_at desc
            """
        )
    )
    return [dict(row) for row in result.mappings().all()]


async def get_supervisor_detail(db: AsyncSession, supervisor_id: UUID) -> dict | None:
    result = await db.execute(
        text(
            """
            select id, name, phone, role, is_active, created_at, updated_at
            from users
            where id=:id and role='SUPERVISOR' and is_active=true
            """
        ),
        {'id': str(supervisor_id)},
    )
    row = result.mappings().one_or_none()
    return dict(row) if row else None


async def list_assigned_site_ids(db: AsyncSession, supervisor_id: UUID) -> list[str]:
    result = await db.execute(
        text(
            """
            select site_id
            from supervisor_site_assignments
            where supervisor_id=:supervisor_id
            order by site_id
            """
        ),
        {'supervisor_id': str(supervisor_id)},
    )
    return [str(row['site_id']) for row in result.mappings().all()]
