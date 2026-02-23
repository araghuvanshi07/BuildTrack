import asyncio

from sqlalchemy import text

from app.db.session import SessionLocal
from app.db.sql import PUBLIC_STATEMENTS


async def run() -> None:
    async with SessionLocal() as session:
        async with session.begin():
            for stmt in PUBLIC_STATEMENTS:
                await session.execute(text(stmt))


if __name__ == '__main__':
    asyncio.run(run())
