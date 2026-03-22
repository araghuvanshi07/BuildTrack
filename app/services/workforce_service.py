import calendar
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas import (
    AttendanceCreateRequest,
    BonusCreateRequest,
    SalarySettlementUpsertRequest,
    UserContext,
    UserRole,
    WorkerCreateRequest,
)
from app.repositories import access_control as access_repo
from app.repositories import workforce as repo
from app.services.access_control_service import require_permission
from app.utils.payloads import to_db_payload
from app.utils.tenancy import set_tenant_search_path


def _require_contractor(actor: UserContext) -> None:
    if actor.role != UserRole.CONTRACTOR:
        raise HTTPException(status_code=403, detail='Only contractor can perform this action')


def _validate_period(from_date: date, to_date: date) -> None:
    if to_date < from_date:
        raise HTTPException(status_code=400, detail='Invalid date range')


async def _ensure_worker_scope(
    db: AsyncSession,
    actor: UserContext,
    worker_id: UUID,
    *,
    expected_site_id: UUID | None = None,
) -> dict:
    worker = await repo.get_worker(db, worker_id)
    if not worker:
        raise HTTPException(status_code=404, detail='Worker not found')

    if expected_site_id and worker['site_id'] != expected_site_id:
        raise HTTPException(status_code=400, detail='worker_id does not belong to site_id')

    if actor.role == UserRole.SUPERVISOR:
        if not actor.user_id:
            raise HTTPException(status_code=403, detail='Supervisor identity missing')
        assigned = await access_repo.is_supervisor_assigned_to_site(db, actor.user_id, worker['site_id'])
        if not assigned:
            raise HTTPException(status_code=403, detail='Supervisor is not assigned to this site')

    return worker


async def create_worker(db: AsyncSession, actor: UserContext, payload: WorkerCreateRequest) -> UUID:
    await require_permission(db, actor, 'add_worker', payload.site_id)
    await set_tenant_search_path(db, actor.schema_name)
    body = to_db_payload(payload, uuid_fields={'site_id'}, enum_fields={'salary_type'})
    body['created_by'] = str(actor.user_id) if actor.user_id else None
    return await repo.create_worker(db, body)


async def list_workers(db: AsyncSession, actor: UserContext, site_id: UUID | None = None) -> list[dict]:
    await set_tenant_search_path(db, actor.schema_name)

    site_filter = str(site_id) if site_id else None
    site_ids: list[str] | None = None
    if actor.role == UserRole.SUPERVISOR:
        if not actor.user_id:
            raise HTTPException(status_code=403, detail='Supervisor identity missing')
        if site_id:
            assigned = await access_repo.is_supervisor_assigned_to_site(db, actor.user_id, site_id)
            if not assigned:
                raise HTTPException(status_code=403, detail='Supervisor is not assigned to this site')
        else:
            site_ids = await access_repo.list_assigned_site_ids(db, actor.user_id)

    rows = await repo.list_workers(db, site_filter, site_ids)
    return [{**row, 'id': str(row['id']), 'site_id': str(row['site_id'])} for row in rows]


async def create_attendance(db: AsyncSession, actor: UserContext, payload: AttendanceCreateRequest) -> UUID:
    await require_permission(db, actor, 'mark_attendance', payload.site_id)
    await set_tenant_search_path(db, actor.schema_name)

    await _ensure_worker_scope(db, actor, payload.worker_id, expected_site_id=payload.site_id)
    body = to_db_payload(payload, uuid_fields={'worker_id', 'site_id'}, enum_fields={'status'})
    body['marked_by'] = str(actor.user_id) if actor.user_id else None

    try:
        return await repo.create_attendance(db, body)
    except IntegrityError as exc:
        msg = str(exc)
        if 'uq_attendance_worker_date' in msg or 'attendance_worker_id_date_key' in msg:
            raise HTTPException(status_code=409, detail='Attendance already marked for this worker and date') from exc
        raise


async def list_attendance(
    db: AsyncSession,
    actor: UserContext,
    worker_id: UUID | None = None,
    site_id: UUID | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
) -> list[dict]:
    if from_date and to_date:
        _validate_period(from_date, to_date)

    await set_tenant_search_path(db, actor.schema_name)
    scoped_site_ids: list[str] | None = None
    if actor.role == UserRole.SUPERVISOR:
        if not actor.user_id:
            raise HTTPException(status_code=403, detail='Supervisor identity missing')
        if site_id:
            assigned = await access_repo.is_supervisor_assigned_to_site(db, actor.user_id, site_id)
            if not assigned:
                raise HTTPException(status_code=403, detail='Supervisor is not assigned to this site')
        else:
            scoped_site_ids = await access_repo.list_assigned_site_ids(db, actor.user_id)

    rows = await repo.list_attendance(
        db,
        worker_id=str(worker_id) if worker_id else None,
        site_id=str(site_id) if site_id else None,
        from_date=from_date,
        to_date=to_date,
        site_ids=scoped_site_ids,
    )
    return [
        {
            **row,
            'id': str(row['id']),
            'worker_id': str(row['worker_id']),
            'site_id': str(row['site_id']),
            'marked_by': str(row['marked_by']) if row['marked_by'] else None,
        }
        for row in rows
    ]


async def create_bonus(db: AsyncSession, actor: UserContext, payload: BonusCreateRequest) -> UUID:
    _require_contractor(actor)
    await set_tenant_search_path(db, actor.schema_name)

    await _ensure_worker_scope(db, actor, payload.worker_id)
    body = to_db_payload(payload, uuid_fields={'worker_id'})
    return await repo.create_bonus(db, body)


async def list_bonus(
    db: AsyncSession,
    actor: UserContext,
    worker_id: UUID | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
) -> list[dict]:
    if from_date and to_date:
        _validate_period(from_date, to_date)

    await set_tenant_search_path(db, actor.schema_name)
    site_ids: list[str] | None = None
    if actor.role == UserRole.SUPERVISOR:
        if not actor.user_id:
            raise HTTPException(status_code=403, detail='Supervisor identity missing')
        site_ids = await access_repo.list_assigned_site_ids(db, actor.user_id)

    rows = await repo.list_bonus(
        db,
        worker_id=str(worker_id) if worker_id else None,
        from_date=from_date,
        to_date=to_date,
        site_ids=site_ids,
    )
    return [{**row, 'id': str(row['id']), 'worker_id': str(row['worker_id']), 'site_id': str(row['site_id'])} for row in rows]


def _attendance_unit(status: str) -> Decimal:
    if status in {'present', 'paid_leave'}:
        return Decimal('1')
    if status == 'half_day':
        return Decimal('0.5')
    return Decimal('0')


def _days_in_range(from_date: date, to_date: date) -> int:
    return (to_date - from_date).days + 1


def _month_day_count(value: date) -> int:
    return calendar.monthrange(value.year, value.month)[1]


def _money(value: Decimal) -> float:
    return float(value.quantize(Decimal('0.01')))


async def calculate_salary_summary(
    db: AsyncSession,
    actor: UserContext,
    worker_id: UUID,
    from_date: date,
    to_date: date,
) -> dict:
    _validate_period(from_date, to_date)
    await set_tenant_search_path(db, actor.schema_name)

    worker = await _ensure_worker_scope(db, actor, worker_id)
    attendance_rows = await repo.list_attendance_for_worker_range(db, worker_id, from_date, to_date)

    present_days = 0
    paid_leave_days = 0
    half_day_count = 0

    base_salary = Decimal('0')
    if worker['salary_type'] == 'daily':
        units = Decimal('0')
        for row in attendance_rows:
            status = row['status']
            unit = _attendance_unit(status)
            units += unit
            if status == 'present':
                present_days += 1
            elif status == 'paid_leave':
                paid_leave_days += 1
            elif status == 'half_day':
                half_day_count += 1
        base_salary = (worker['daily_wage'] or Decimal('0')) * units
    else:
        monthly_salary = worker['monthly_salary'] or Decimal('0')
        if worker['is_attendance_based']:
            for row in attendance_rows:
                status = row['status']
                unit = _attendance_unit(status)
                if unit == 0:
                    continue
                current_date: date = row['date']
                per_day_salary = monthly_salary / Decimal(_month_day_count(current_date))
                base_salary += per_day_salary * unit
                if status == 'present':
                    present_days += 1
                elif status == 'paid_leave':
                    paid_leave_days += 1
                elif status == 'half_day':
                    half_day_count += 1
        else:
            running = from_date
            while running <= to_date:
                base_salary += monthly_salary / Decimal(_month_day_count(running))
                running += timedelta(days=1)
            present_days = _days_in_range(from_date, to_date)

    total_bonus = repo.sum_bonus(db, worker_id, from_date, to_date)
    total_bonus_value = await total_bonus
    total_paid_value = Decimal('0')

    total_salary = base_salary + total_bonus_value
    pending_salary = total_salary - total_paid_value

    settlement = await repo.get_salary_settlement(db, worker_id, from_date, to_date)
    is_paid = bool(settlement and settlement['is_paid'])

    return {
        'worker_id': str(worker_id),
        'site_id': str(worker['site_id']),
        'from_date': from_date,
        'to_date': to_date,
        'total_days': _days_in_range(from_date, to_date),
        'present_days': present_days,
        'paid_leave_days': paid_leave_days,
        'half_day_days': half_day_count,
        'base_salary': _money(base_salary),
        'total_bonus': _money(total_bonus_value),
        'total_salary': _money(total_salary),
        'total_paid': _money(total_paid_value),
        'pending_salary': _money(pending_salary),
        'status': 'PAID' if is_paid else 'UNPAID',
        'is_paid': is_paid,
        'paid_on': settlement['paid_on'] if settlement else None,
        'marked_by': str(settlement['marked_by']) if settlement and settlement['marked_by'] else None,
    }


async def upsert_salary_settlement(db: AsyncSession, actor: UserContext, payload: SalarySettlementUpsertRequest) -> UUID:
    if actor.role not in {UserRole.CONTRACTOR, UserRole.SUPERVISOR}:
        raise HTTPException(status_code=403, detail='Role not allowed')
    await set_tenant_search_path(db, actor.schema_name)
    await _ensure_worker_scope(db, actor, payload.worker_id)

    body = to_db_payload(payload, uuid_fields={'worker_id'})
    body['marked_by'] = str(actor.user_id) if actor.user_id else None
    return await repo.upsert_salary_settlement(db, body)
