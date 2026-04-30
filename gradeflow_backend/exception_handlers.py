import logging
from http import HTTPStatus

from fastapi import FastAPI, Request, status
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.responses import JSONResponse
from gradeflow_engine.exceptions import GradeFlowError, GradeFlowValidationError
from pydantic import ValidationError
from pydantic_core import ErrorDetails

from gradeflow_backend.schemas.errors import ErrorResponse
from gradeflow_backend.services.exceptions import AppError

logger = logging.getLogger(__name__)


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


def register_handlers(app: FastAPI) -> None:
    async def app_error_handler(_: Request, exc: Exception) -> JSONResponse:
        assert isinstance(exc, AppError)
        return _error_response(
            status_code=exc.status_code,
            code=exc.code,
            message=exc.message,
            errors=exc.errors,
        )

    async def http_exception_handler(_: Request, exc: Exception) -> JSONResponse:
        assert isinstance(exc, HTTPException)
        message = _http_message(exc.status_code, exc.detail)
        return _error_response(
            status_code=exc.status_code,
            code=_http_error_code(exc.status_code),
            message=message,
        )

    async def request_validation_handler(_: Request, exc: Exception) -> JSONResponse:
        assert isinstance(exc, RequestValidationError)
        messages = [_validation_message(e) for e in exc.errors()]
        return _error_response(
            status_code=422,
            code="VALIDATION_ERROR",
            message="Request validation failed",
            errors=messages,
        )

    async def pydantic_validation_handler(_: Request, exc: Exception) -> JSONResponse:
        assert isinstance(exc, ValidationError)
        messages = [_validation_message(e) for e in exc.errors()]
        return _error_response(
            status_code=422,
            code="VALIDATION_ERROR",
            message="Validation failed",
            errors=messages,
        )

    async def gradeflow_validation_handler(_: Request, exc: Exception) -> JSONResponse:
        assert isinstance(exc, GradeFlowValidationError)
        messages = [_validation_message(e) for e in exc.errors()]
        return _error_response(
            status_code=422,
            code="GRADEFLOW_VALIDATION_ERROR",
            message="GradeFlow validation failed",
            errors=messages,
        )

    async def gradeflow_error_handler(_: Request, exc: Exception) -> JSONResponse:
        return _error_response(
            status_code=422,
            code="GRADEFLOW_ERROR",
            message=str(exc),
        )

    async def unexpected_error_handler(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled API error")
        return _error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="INTERNAL_SERVER_ERROR",
            message="Internal server error.",
        )

    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, request_validation_handler)
    app.add_exception_handler(ValidationError, pydantic_validation_handler)
    app.add_exception_handler(GradeFlowValidationError, gradeflow_validation_handler)
    app.add_exception_handler(GradeFlowError, gradeflow_error_handler)
    app.add_exception_handler(Exception, unexpected_error_handler)
