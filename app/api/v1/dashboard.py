from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas import UserContext
from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.services.dashboard_service import get_summary

router = APIRouter(prefix='/dashboard', tags=['dashboard'])


@router.get('/summary')
async def dashboard_summary_endpoint(
    actor: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await get_summary(db, actor)
