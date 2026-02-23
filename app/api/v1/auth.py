from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas import (
    EmailLoginRequest,
    InviteContractorRequest,
    OTPRequest,
    OTPVerify,
    RefreshTokenRequest,
    ResendSetPasswordLinkRequest,
    SetPasswordRequest,
    TenantContext,
)
from app.core.dependencies import get_current_tenant
from app.db.session import get_db
from app.services.auth_service import (
    invite_contractor,
    login_with_password,
    refresh_token,
    resend_set_password_link,
    send_otp,
    set_password,
    verify_otp,
)

router = APIRouter(prefix='/auth', tags=['auth'])


@router.post('/send-otp')
async def send_otp_endpoint(payload: OTPRequest) -> dict:
    return send_otp(payload.phone)


@router.post('/verify-otp')
async def verify_otp_endpoint(payload: OTPVerify) -> dict:
    return verify_otp(payload.phone, payload.otp)


@router.post('/refresh-token')
async def refresh_token_endpoint(payload: RefreshTokenRequest) -> dict:
    return refresh_token(payload.subject)


@router.post('/invite-contractor')
async def invite_contractor_endpoint(
    payload: InviteContractorRequest,
    tenant: TenantContext = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await invite_contractor(db, tenant, payload)


@router.post('/resend-set-password-link')
async def resend_set_password_link_endpoint(
    payload: ResendSetPasswordLinkRequest,
    tenant: TenantContext = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await resend_set_password_link(db, tenant, payload)


@router.post('/set-password')
async def set_password_endpoint(payload: SetPasswordRequest, db: AsyncSession = Depends(get_db)) -> dict:
    return await set_password(db, payload)


@router.post('/login')
async def login_endpoint(
    payload: EmailLoginRequest,
    tenant: TenantContext = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await login_with_password(db, tenant, payload)
