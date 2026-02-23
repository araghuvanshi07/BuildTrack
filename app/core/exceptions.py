from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.core.logging import get_logger

logger = get_logger(__name__)


class AppError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(_: Request, exc: AppError):
        return JSONResponse(
            status_code=exc.status_code,
            content={'error': {'code': exc.code, 'message': exc.message}},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(_: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={'error': {'code': 'VALIDATION_ERROR', 'message': 'Invalid request payload', 'details': exc.errors()}},
        )

    @app.exception_handler(SQLAlchemyError)
    async def db_error_handler(_: Request, exc: SQLAlchemyError):
        logger.exception('Database error: %s', exc)
        return JSONResponse(
            status_code=500,
            content={'error': {'code': 'DB_ERROR', 'message': 'Database operation failed'}},
        )

    @app.exception_handler(Exception)
    async def fallback_error_handler(_: Request, exc: Exception):
        if isinstance(exc, HTTPException):
            raise exc
        logger.exception('Unhandled error: %s', exc)
        return JSONResponse(
            status_code=500,
            content={'error': {'code': 'INTERNAL_ERROR', 'message': 'Internal server error'}},
        )
