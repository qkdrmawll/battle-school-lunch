import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

import httpx
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from battle_school_lunch.api.routes import router
from battle_school_lunch.clients.neis import NeisClient
from battle_school_lunch.config import Settings, get_settings
from battle_school_lunch.errors import AppError
from battle_school_lunch.models import ErrorDetail, ErrorResponse
from battle_school_lunch.services.schools import SchoolService

logger = logging.getLogger(__name__)


def error_response(status_code: int, code: str, message: str) -> JSONResponse:
    payload = ErrorResponse(error=ErrorDetail(code=code, message=message))
    return JSONResponse(status_code=status_code, content=payload.model_dump(by_alias=True))


def create_app(
    *,
    settings: Settings | None = None,
    http_client: httpx.AsyncClient | None = None,
) -> FastAPI:
    app_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        client = NeisClient(
            app_settings.neis_api_key,
            http_client=http_client,
            timeout_seconds=app_settings.neis_timeout_seconds,
        )
        app.state.school_service = SchoolService(client)
        try:
            yield
        finally:
            await client.close()

    app = FastAPI(title="Battle School Lunch API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[app_settings.frontend_origin],
        allow_credentials=False,
        allow_methods=["GET"],
        allow_headers=["Accept", "Content-Type"],
    )

    @app.exception_handler(AppError)
    async def handle_app_error(_request: Request, exc: AppError) -> JSONResponse:
        if exc.status_code >= 500:
            logger.warning(
                "upstream_request_failed",
                extra={"error_code": exc.code, "status_code": exc.status_code},
            )
        return error_response(exc.status_code, exc.code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_request: Request, _exc: RequestValidationError) -> JSONResponse:
        return error_response(422, "VALIDATION_ERROR", "요청 값이 API 계약에 맞지 않습니다.")

    app.include_router(router)
    return app


app = create_app()
