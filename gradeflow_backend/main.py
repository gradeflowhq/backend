import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from http import HTTPStatus

from fastapi import FastAPI, Request, status
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from gradeflow_engine.exceptions import GradeFlowError, GradeFlowValidationError
from pydantic import ValidationError
from pydantic_core import ErrorDetails

from gradeflow_backend.config import get_settings
from gradeflow_backend.db import init_db
from gradeflow_backend.openapi import patch_openapi_union_format
from gradeflow_backend.routers import (
    assessments,
    grading,
    health,
    jobs,
    memberships,
    question_sets,
    registry,
    rubrics,
    submissions,
    users,
)
from gradeflow_backend.schemas.errors import ErrorResponse
from gradeflow_backend.services.exceptions import (
    AppError,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Validate required Zitadel config before accepting requests
    cfg = settings.zitadel
    if not cfg.client_id:
        raise RuntimeError(
            "ZITADEL__CLIENT_ID is not set — cannot validate tokens without an audience"
        )
    if cfg.authority in ("", "https://zitadel.cloud"):
        logger.warning(
            "ZITADEL__AUTHORITY is using the default value '%s' — "
            "set it to your actual Zitadel instance URL for production",
            cfg.authority,
        )
    init_db()
    yield


app = FastAPI(
    title="GradeFlow API",
    version="0.1.0",
    description="Thin FastAPI wrapper over GradeFlow Engine",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors.allow_origins,
    allow_credentials=settings.cors.allow_credentials,
    allow_methods=settings.cors.allow_methods,
    allow_headers=settings.cors.allow_headers,
)


def _error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    errors: list[str] | None = None,
) -> JSONResponse:
    details = errors or [message]
    payload = ErrorResponse(code=code, message=message, errors=details).model_dump()
    return JSONResponse(status_code=status_code, content=payload)


def _validation_message(error: ErrorDetails) -> str:
    msg = str(error.get("msg") or "Invalid value")
    loc = error.get("loc")
    if isinstance(loc, tuple | list):
        path = " > ".join(str(part) for part in loc if part not in {"body", "query", "path"})
        if path:
            return f"{path}: {msg}"
    return msg


def _http_error_code(status_code: int) -> str:
    if status_code == status.HTTP_401_UNAUTHORIZED:
        return "UNAUTHORIZED"
    if status_code == status.HTTP_403_FORBIDDEN:
        return "FORBIDDEN"
    if status_code == status.HTTP_404_NOT_FOUND:
        return "NOT_FOUND"
    if status_code >= 500:
        return "INTERNAL_SERVER_ERROR"
    return "HTTP_ERROR"


def _http_message(status_code: int, detail: object) -> str:
    if isinstance(detail, str) and detail:
        return detail
    try:
        return HTTPStatus(status_code).phrase
    except ValueError:
        return "Request failed"


# Global exception handlers to return typed error payloads
@app.exception_handler(AppError)
async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    return _error_response(
        status_code=exc.status_code,
        code=exc.code,
        message=exc.message,
        errors=exc.errors,
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    message = _http_message(exc.status_code, exc.detail)
    return _error_response(
        status_code=exc.status_code,
        code=_http_error_code(exc.status_code),
        message=message,
    )


@app.exception_handler(RequestValidationError)
async def request_validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    messages = [_validation_message(e) for e in exc.errors()]
    return _error_response(
        status_code=422,
        code="VALIDATION_ERROR",
        message="Request validation failed",
        errors=messages,
    )


@app.exception_handler(ValidationError)
async def pydantic_validation_handler(_: Request, exc: ValidationError) -> JSONResponse:
    messages = [_validation_message(e) for e in exc.errors()]
    return _error_response(
        status_code=422,
        code="VALIDATION_ERROR",
        message="Validation failed",
        errors=messages,
    )


@app.exception_handler(GradeFlowValidationError)
async def gradeflow_validation_handler(_: Request, exc: GradeFlowValidationError) -> JSONResponse:
    messages = [_validation_message(e) for e in exc.errors()]
    return _error_response(
        status_code=422,
        code="GRADEFLOW_VALIDATION_ERROR",
        message="GradeFlow validation failed",
        errors=messages,
    )


@app.exception_handler(GradeFlowError)
async def gradeflow_error_handler(_: Request, exc: GradeFlowError) -> JSONResponse:
    return _error_response(
        status_code=422,
        code="GRADEFLOW_ERROR",
        message=str(exc),
    )


@app.exception_handler(Exception)
async def unexpected_error_handler(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled API error")
    return _error_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        code="INTERNAL_SERVER_ERROR",
        message="Internal server error.",
    )


# Include routers
app.include_router(health.router)
app.include_router(registry.router)
app.include_router(assessments.router)
app.include_router(submissions.router)
app.include_router(question_sets.router)
app.include_router(rubrics.router)
app.include_router(grading.router)
app.include_router(memberships.router)
app.include_router(jobs.router)
app.include_router(users.router)


# Install OpenAPI patcher
patch_openapi_union_format(app)
