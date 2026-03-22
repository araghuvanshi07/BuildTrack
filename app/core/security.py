import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from jose import jwt

from app.core.config import get_settings


settings = get_settings()
_PBKDF2_SCHEME = 'pbkdf2-sha256'
_PBKDF2_ROUNDS = 29000


def _b64decode_nopad(value: str) -> bytes:
    return base64.b64decode(value + ('=' * (-len(value) % 4)))


def create_access_token(subject: str, claims: dict | None = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {'sub': subject, 'exp': expire, 'type': 'access'}
    if claims:
        payload.update(claims)
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(subject: str, claims: dict | None = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)
    payload = {'sub': subject, 'exp': expire, 'type': 'refresh'}
    if claims:
        payload.update(claims)
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_set_password_token(*, tenant_id: str, user_id: str, email: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=30)
    payload = {'sub': email, 'tenant_id': tenant_id, 'user_id': user_id, 'exp': expire, 'type': 'set_password'}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])


def hash_password(password: str) -> str:
    salt = base64.b64encode(secrets.token_bytes(16)).decode().rstrip('=')
    dk = hashlib.pbkdf2_hmac('sha256', password.encode(), _b64decode_nopad(salt), _PBKDF2_ROUNDS)
    checksum = base64.b64encode(dk).decode().rstrip('=')
    return f'${_PBKDF2_SCHEME}${_PBKDF2_ROUNDS}${salt}${checksum}'


def verify_password(password: str, password_hash: str) -> bool:
    try:
        _, scheme, rounds_text, salt_b64, expected_checksum = password_hash.split('$', 4)
        if scheme != _PBKDF2_SCHEME:
            return False
        rounds = int(rounds_text)
        dk = hashlib.pbkdf2_hmac('sha256', password.encode(), _b64decode_nopad(salt_b64), rounds)
        actual_checksum = base64.b64encode(dk).decode().rstrip('=')
        return hmac.compare_digest(expected_checksum, actual_checksum)
    except Exception:
        return False
