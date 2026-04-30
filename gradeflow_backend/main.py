import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from gradeflow_backend.config import get_settings
from gradeflow_backend.db import init_db
from gradeflow_backend.exception_handlers import register_handlers
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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Validate required Zitadel config before accepting requests
    cfg = get_settings().zitadel
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


def create_app() -> FastAPI:
    settings = get_settings()
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

    register_handlers(app)

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
    return app


app = create_app()
