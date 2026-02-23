from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas import TaskCreateRequest, TaskUpdateRequest, UserContext
from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.services.tasks_service import create_task, delete_task, get_task, list_tasks, update_task

router = APIRouter(tags=['tasks'])


@router.post('/tasks')
async def create_task_endpoint(
    payload: TaskCreateRequest,
    actor: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    task_id = await create_task(db, actor, payload)
    return {'id': str(task_id)}


@router.put('/tasks/{task_id}')
async def update_task_endpoint(
    task_id: UUID,
    payload: TaskUpdateRequest,
    actor: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await update_task(db, actor, task_id, payload)
    return {'message': 'Updated'}


@router.get('/tasks/{task_id}')
async def get_task_endpoint(
    task_id: UUID,
    actor: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await get_task(db, actor, task_id)


@router.get('/site/{site_id}/tasks')
async def list_tasks_endpoint(
    site_id: UUID,
    actor: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    return await list_tasks(db, actor, site_id)


@router.delete('/tasks/{task_id}')
async def delete_task_endpoint(
    task_id: UUID,
    actor: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await delete_task(db, actor, task_id)
    return {'message': 'Deleted'}
