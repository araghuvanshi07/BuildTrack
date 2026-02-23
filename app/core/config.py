from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    app_name: str = 'BuildTrack Backend'
    app_env: str = 'dev'
    app_debug: bool = True
    api_prefix: str = '/api/v1'

    database_url: str = 'postgresql+asyncpg://postgres:postgres@localhost:5432/buildtrack'

    jwt_secret_key: str = 'change_me'
    jwt_algorithm: str = 'HS256'
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 30

    tenant_header: str = 'X-Tenant-ID'
    app_base_url: str = 'http://localhost:8000'
    smtp_host: str = 'localhost'
    smtp_port: int = 1025
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from_email: str = 'no-reply@buildtrack.local'
    smtp_use_tls: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
