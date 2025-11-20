from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import gradeflow_engine as gradeflow_engine
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from gradeflow_backend.db import init_db
from gradeflow_backend.openapi import patch_openapi_union_format
from gradeflow_backend.routers import (
    assessments,
    auth,
    grading,
    health,
    memberships,
    question_sets,
    registry,
    rubrics,
    submissions,
)
from gradeflow_backend.schemas.errors import ErrorResponse
from gradeflow_backend.services.exceptions import (
    BadRequestError,
    NotFoundError,
    RubricValidationError,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
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
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
    messages = [e["msg"] for e in exc.errors()]  # extract error messages
    payload = ErrorResponse(errors=messages).model_dump()
    return JSONResponse(status_code=422, content=payload)


# Include routers
app.include_router(health.router)
app.include_router(registry.router)
app.include_router(assessments.router)
app.include_router(submissions.router)
app.include_router(question_sets.router)
app.include_router(rubrics.router)
app.include_router(grading.router)
app.include_router(auth.router)
app.include_router(memberships.router)


# Install OpenAPI patcher
patch_openapi_union_format(app)
