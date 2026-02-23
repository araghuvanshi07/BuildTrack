from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas import ExpenseCreateRequest, UserContext
from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.services.expenses_service import create_expense, list_expenses

router = APIRouter(tags=['expenses'])


@router.post('/expenses')
async def create_expense_endpoint(
    payload: ExpenseCreateRequest,
    actor: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    expense_id = await create_expense(db, actor, payload)
    return {'id': str(expense_id)}


@router.get('/site/{site_id}/expenses')
async def list_expenses_endpoint(
    site_id: UUID,
    actor: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    return await list_expenses(db, actor, site_id)
