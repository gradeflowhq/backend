import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from gradeflow_engine.exceptions import GradeFlowError, GradeFlowValidationError
from pydantic import ValidationError

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
    BadRequestError,
    NotFoundError,
    RubricValidationError,
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


# Global exception handlers to return typed error payloads
@app.exception_handler(NotFoundError)
async def not_found_handler(_: Request, exc: NotFoundError) -> JSONResponse:
    payload = ErrorResponse(errors=[exc.message]).model_dump()
    return JSONResponse(status_code=404, content=payload)


@app.exception_handler(BadRequestError)
async def bad_request_handler(_: Request, exc: BadRequestError) -> JSONResponse:
    payload = ErrorResponse(errors=[exc.message]).model_dump()
    return JSONResponse(status_code=400, content=payload)


@app.exception_handler(RubricValidationError)
async def rubric_validation_handler(_: Request, exc: RubricValidationError) -> JSONResponse:
    messages = [str(e) for e in exc.errors]  # normalize to strings
    payload = ErrorResponse(errors=messages).model_dump()
    return JSONResponse(status_code=422, content=payload)


@app.exception_handler(ValidationError)
async def pydantic_validation_handler(_: Request, exc: ValidationError) -> JSONResponse:
    messages = [str(e) for e in exc.errors()]  # extract error messages
    payload = ErrorResponse(errors=messages).model_dump()
    return JSONResponse(status_code=422, content=payload)


@app.exception_handler(GradeFlowValidationError)
async def gradeflow_validation_handler(_: Request, exc: GradeFlowValidationError) -> JSONResponse:
    messages = [str(e) for e in exc.errors()]  # extract error messages
    payload = ErrorResponse(errors=messages).model_dump()
    return JSONResponse(status_code=422, content=payload)


@app.exception_handler(GradeFlowError)
async def gradeflow_error_handler(_: Request, exc: GradeFlowError) -> JSONResponse:
    payload = ErrorResponse(errors=[str(exc)]).model_dump()
    return JSONResponse(status_code=422, content=payload)


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
