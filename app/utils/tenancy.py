import re

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_IDENTIFIER = re.compile(r'^[a-z][a-z0-9_]{2,62}$')


def validate_schema_name(value: str) -> str:
    if not _IDENTIFIER.fullmatch(value):
        raise HTTPException(status_code=400, detail='Invalid schema_name format')
    return value


async def set_tenant_search_path(db: AsyncSession, schema_name: str) -> None:
    validate_schema_name(schema_name)
    await db.execute(text(f'set local search_path to {schema_name}, public'))
