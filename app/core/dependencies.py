import hmac
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas import TenantContext, UserContext, UserRole
from app.core.config import get_settings
from app.core.security import decode_token
from app.db.session import get_db
from app.services.access_control_service import get_user_context
from app.services.tenants_service import check_subscription_access, get_tenant_context


async def get_current_tenant(
    db: AsyncSession = Depends(get_db),
    x_tenant_id: str | None = Header(default=None, alias='X-Tenant-ID'),
) -> TenantContext:
    settings = get_settings()
    if not x_tenant_id:
        raise HTTPException(status_code=400, detail=f'Missing tenant header: {settings.tenant_header}')

    try:
        tenant_id = UUID(x_tenant_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail='Invalid tenant UUID header') from exc

    return await get_tenant_context(db, tenant_id)


async def get_current_paid_tenant(
    request: Request,
    tenant: TenantContext = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> TenantContext:
    return await check_subscription_access(db, tenant, request.method)


async def get_current_user(
    tenant: TenantContext = Depends(get_current_paid_tenant),
    db: AsyncSession = Depends(get_db),
    authorization: str | None = Header(default=None, alias='Authorization'),
    x_user_id: str | None = Header(default=None, alias='X-User-ID'),
) -> UserContext:
    base = UserContext(tenant_id=tenant.tenant_id, schema_name=tenant.schema_name, user_id=None, role=UserRole.CONTRACTOR)
    if authorization and authorization.lower().startswith('bearer '):
        token = authorization.split(' ', 1)[1].strip()
        try:
            payload = decode_token(token)
            token_tenant = payload.get('tenant_id')
            token_user_id = payload.get('user_id')
            token_role = payload.get('role')
            if token_tenant and str(token_tenant) != str(tenant.tenant_id):
                raise HTTPException(status_code=403, detail='Token tenant mismatch')
            if token_user_id and token_role:
                return UserContext(
                    tenant_id=tenant.tenant_id,
                    schema_name=tenant.schema_name,
                    user_id=UUID(str(token_user_id)),
                    role=UserRole(str(token_role)),
                )
        except HTTPException:
            raise
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=401, detail='Invalid access token') from exc

    if not x_user_id:
        return base
    try:
        user_id = UUID(x_user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail='Invalid user UUID header') from exc
    return await get_user_context(db, base, user_id)


async def verify_razorpay_webhook(
    x_razorpay_webhook_secret: str | None = Header(default=None, alias='X-Razorpay-Webhook-Secret'),
) -> None:
    settings = get_settings()
    if not x_razorpay_webhook_secret or not hmac.compare_digest(x_razorpay_webhook_secret, settings.razorpay_webhook_secret):
        raise HTTPException(status_code=401, detail='Invalid Razorpay webhook secret')
