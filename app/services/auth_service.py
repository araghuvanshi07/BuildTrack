from fastapi import HTTPException
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas import EmailLoginRequest, InviteContractorRequest, ResendSetPasswordLinkRequest, SetPasswordRequest, TenantContext
from app.core.config import get_settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    create_set_password_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.repositories import auth as auth_repo
from app.utils.email import send_email
from app.utils.tenancy import set_tenant_search_path

_otp_store: dict[str, str] = {}


def send_otp(phone: str) -> dict:
    otp = '123456'
    _otp_store[phone] = otp
    return {'message': 'OTP sent', 'otp_for_dev': otp}


def verify_otp(phone: str, otp: str) -> dict:
    expected = _otp_store.get(phone)
    if expected != otp:
        raise HTTPException(status_code=401, detail='Invalid OTP')

    _otp_store.pop(phone, None)
    return {
        'access_token': create_access_token(phone),
        'refresh_token': create_refresh_token(phone),
        'token_type': 'bearer',
    }


def refresh_token(subject: str | None) -> dict:
    principal = subject or 'user'
    return {'access_token': create_access_token(principal), 'token_type': 'bearer'}


def _build_set_password_link(token: str) -> str:
    settings = get_settings()
    return f'{settings.app_base_url}/set-password?token={token}'


async def send_set_password_for_user(db: AsyncSession, tenant: TenantContext, user: dict) -> None:
    token = create_set_password_token(tenant_id=str(tenant.tenant_id), user_id=str(user['id']), email=user['email'])
    link = _build_set_password_link(token)
    send_email(
        to_email=user['email'],
        subject='BuildTrack - Set your password',
        body=f'Hello {user["name"]},\n\nSet your password using this link:\n{link}\n\nThis link expires in 30 minutes.',
    )


async def invite_contractor(db: AsyncSession, tenant: TenantContext, payload: InviteContractorRequest) -> dict:
    await set_tenant_search_path(db, tenant.schema_name)
    existing = await auth_repo.get_user_by_email(db, payload.email)
    if existing:
        raise HTTPException(status_code=409, detail='Email already exists in tenant')
    user_id = await auth_repo.create_contractor_user(db, {'name': payload.name, 'email': payload.email, 'phone': payload.phone})
    created = await auth_repo.get_user_by_id(db, user_id)
    if not created:
        raise HTTPException(status_code=500, detail='Failed to create contractor user')
    await send_set_password_for_user(db, tenant, created)
    return {'id': str(user_id), 'message': 'Invitation sent'}


async def resend_set_password_link(db: AsyncSession, tenant: TenantContext, payload: ResendSetPasswordLinkRequest) -> dict:
    await set_tenant_search_path(db, tenant.schema_name)
    user = await auth_repo.get_user_by_email(db, payload.email)
    if not user:
        return {'message': 'If the email exists, reset link sent'}
    await send_set_password_for_user(db, tenant, user)
    return {'message': 'If the email exists, reset link sent'}


async def login_with_password(db: AsyncSession, tenant: TenantContext, payload: EmailLoginRequest) -> dict:
    await set_tenant_search_path(db, tenant.schema_name)
    user = await auth_repo.get_user_by_email(db, payload.email)
    if not user or not user.get('password_hash'):
        raise HTTPException(status_code=401, detail='Invalid credentials')
    if not verify_password(payload.password, user['password_hash']):
        raise HTTPException(status_code=401, detail='Invalid credentials')
    claims = {'tenant_id': str(tenant.tenant_id), 'user_id': str(user['id']), 'role': user['role']}
    return {
        'access_token': create_access_token(payload.email, claims=claims),
        'refresh_token': create_refresh_token(payload.email, claims=claims),
        'token_type': 'bearer',
    }


async def set_password(db: AsyncSession, payload: SetPasswordRequest) -> dict:
    try:
        token_payload = decode_token(payload.token)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail='Invalid or expired token') from exc

    if token_payload.get('type') != 'set_password':
        raise HTTPException(status_code=400, detail='Invalid token type')

    tenant_id = token_payload.get('tenant_id')
    user_id = token_payload.get('user_id')
    if not tenant_id or not user_id:
        raise HTTPException(status_code=400, detail='Invalid token payload')

    from app.services.tenants_service import get_tenant_context  # lazy import to avoid cycle

    tenant = await get_tenant_context(db, UUID(str(tenant_id)))
    await set_tenant_search_path(db, tenant.schema_name)
    user = await auth_repo.get_user_by_id(db, UUID(str(user_id)))
    if not user:
        raise HTTPException(status_code=404, detail='User not found')
    await auth_repo.update_password_hash(db, user['id'], hash_password(payload.new_password))
    return {'message': 'Password set successfully'}
