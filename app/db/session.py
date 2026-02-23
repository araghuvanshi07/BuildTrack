from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings

settings = get_settings()

engine_kwargs = {'echo': False, 'future': True}
if settings.app_env == 'test':
    engine_kwargs['poolclass'] = NullPool

engine = create_async_engine(settings.database_url, **engine_kwargs)
SessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncSession:
    async with SessionLocal() as session:
        async with session.begin():
            yield session
