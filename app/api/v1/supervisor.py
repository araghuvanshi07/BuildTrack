from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas import UserContext, WorkerCreateRequest
from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.services.access_control_service import create_worker

router = APIRouter(prefix='/supervisor', tags=['supervisor'])


@router.post('/workers')
async def create_worker_endpoint(
    payload: WorkerCreateRequest,
    actor: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    worker_id = await create_worker(db, actor, payload)
    return {'id': str(worker_id)}
