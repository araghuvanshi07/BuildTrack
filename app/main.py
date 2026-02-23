from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import get_settings

settings = get_settings()


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, debug=settings.app_debug)

    @app.get('/health')
    async def health() -> dict:
        return {'status': 'ok'}

    app.include_router(api_router, prefix=settings.api_prefix)
    return app


app = create_app()
