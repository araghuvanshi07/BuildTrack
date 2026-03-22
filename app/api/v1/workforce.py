from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas import (
    AttendanceCreateRequest,
    BonusCreateRequest,
    SalarySettlementUpsertRequest,
    UserContext,
    WorkerCreateRequest,
)
from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.services.workforce_service import (
    calculate_salary_summary,
    create_attendance,
    create_bonus,
    create_worker,
    list_attendance,
    list_bonus,
    list_workers,
    upsert_salary_settlement,
)

router = APIRouter(tags=['workforce'])


@router.post('/workers')
async def create_worker_endpoint(
    payload: WorkerCreateRequest,
    actor: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    worker_id = await create_worker(db, actor, payload)
    return {'id': str(worker_id)}


@router.get('/workers')
async def list_workers_endpoint(
    site_id: UUID | None = Query(default=None),
    actor: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    return await list_workers(db, actor, site_id)


@router.post('/attendance')
async def create_attendance_endpoint(
    payload: AttendanceCreateRequest,
    actor: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    attendance_id = await create_attendance(db, actor, payload)
    return {'id': str(attendance_id)}


@router.get('/attendance')
async def list_attendance_endpoint(
    worker_id: UUID | None = Query(default=None),
    site_id: UUID | None = Query(default=None),
    from_date: date | None = Query(default=None, alias='from'),
    to_date: date | None = Query(default=None, alias='to'),
    actor: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    return await list_attendance(db, actor, worker_id, site_id, from_date, to_date)


@router.post('/bonus')
async def create_bonus_endpoint(
    payload: BonusCreateRequest,
    actor: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    bonus_id = await create_bonus(db, actor, payload)
    return {'id': str(bonus_id)}


@router.get('/bonus')
async def list_bonus_endpoint(
    worker_id: UUID | None = Query(default=None),
    from_date: date | None = Query(default=None, alias='from'),
    to_date: date | None = Query(default=None, alias='to'),
    actor: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    return await list_bonus(db, actor, worker_id, from_date, to_date)


@router.post('/salary-settlements')
async def upsert_salary_settlement_endpoint(
    payload: SalarySettlementUpsertRequest,
    actor: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    settlement_id = await upsert_salary_settlement(db, actor, payload)
    return {'id': str(settlement_id)}


@router.get('/salary-summary')
async def salary_summary_endpoint(
    worker_id: UUID,
    from_date: date = Query(alias='from'),
    to_date: date = Query(alias='to'),
    actor: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await calculate_salary_summary(db, actor, worker_id, from_date, to_date)
