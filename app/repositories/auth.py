from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def get_user_by_email(db: AsyncSession, email: str) -> dict | None:
    result = await db.execute(
        text(
            """
            select id, name, email, phone, role, password_hash, is_active
            from users
            where lower(email)=lower(:email) and is_active=true
            """
        ),
        {'email': email},
    )
    row = result.mappings().one_or_none()
    return dict(row) if row else None


async def get_user_by_id(db: AsyncSession, user_id: UUID) -> dict | None:
    result = await db.execute(
        text(
            """
            select id, name, email, phone, role, password_hash, is_active
            from users
            where id=:id and is_active=true
            """
        ),
        {'id': str(user_id)},
    )
    row = result.mappings().one_or_none()
    return dict(row) if row else None


async def update_password_hash(db: AsyncSession, user_id: UUID, password_hash: str) -> None:
    await db.execute(
        text(
            """
            update users
            set password_hash=:password_hash, password_updated_at=now(), updated_at=now()
            where id=:id and is_active=true
            """
        ),
        {'id': str(user_id), 'password_hash': password_hash},
    )


async def create_contractor_user(db: AsyncSession, payload: dict) -> UUID:
    result = await db.execute(
        text(
            """
            insert into users (name, email, phone, role, is_active)
            values (:name, :email, :phone, 'CONTRACTOR', true)
            returning id
            """
        ),
        payload,
    )
    return result.scalar_one()
