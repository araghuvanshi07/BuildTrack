import asyncio
import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine


# Force tests to use dedicated test DB before app modules are imported.
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/buildtrack_test",
)
os.environ.setdefault("APP_ENV", "test")

from app.core.config import get_settings  # noqa: E402
from app.db.bootstrap import run as bootstrap_run  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402


def _sync(coro):
    return asyncio.run(coro)


async def _ensure_test_database_exists() -> None:
    settings = get_settings()
    db_url = make_url(settings.database_url)
    test_db_name = db_url.database
    if not test_db_name:
        raise RuntimeError("DATABASE_URL must include a database name")

    admin_url = db_url.set(database="postgres")
    admin_engine = create_async_engine(
        admin_url.render_as_string(hide_password=False),
        isolation_level="AUTOCOMMIT",
    )
    try:
        async with admin_engine.connect() as conn:
            exists = await conn.execute(
                text("select 1 from pg_database where datname = :db_name"),
                {"db_name": test_db_name},
            )
            if not exists.scalar_one_or_none():
                await conn.execute(text(f'create database "{test_db_name}"'))
    finally:
        await admin_engine.dispose()


@pytest.fixture(scope="session", autouse=True)
def setup_test_database() -> None:
    get_settings.cache_clear()
    _sync(_ensure_test_database_exists())
    _sync(bootstrap_run())


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture()
def tenant_headers(client: TestClient) -> dict[str, str]:
    schema_name = f"t{uuid4().hex[:10]}"
    response = client.post(
        "/api/v1/tenants",
        json={
            "name": f"Contractor-{uuid4().hex[:6]}",
            "schema_name": schema_name,
        },
    )
    assert response.status_code == 200
    tenant_id = response.json()["tenant_id"]
    return {"X-Tenant-ID": tenant_id}


@pytest.fixture()
def expire_subscription() -> callable:
    def _expire(tenant_id: str) -> None:
        async def _run() -> None:
            async with SessionLocal() as session:
                async with session.begin():
                    await session.execute(
                        text(
                            """
                            update public.tenant_subscriptions
                            set is_trial_active=false,
                                trial_start_date=current_date - 60,
                                trial_end_date=current_date - 1,
                                is_active=false,
                                start_date=current_date - 60,
                                end_date=current_date - 1,
                                updated_at=now()
                            where tenant_id=:tenant_id
                            """
                        ),
                        {"tenant_id": tenant_id},
                    )

        _sync(_run())

    return _expire
