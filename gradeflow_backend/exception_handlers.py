import logging
from http import HTTPStatus
from typing import cast

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from gradeflow_engine.error_formatting import format_validation_error_details
from gradeflow_engine.exceptions import GradeFlowError, GradeFlowValidationError
from pydantic import ValidationError
from pydantic_core import ErrorDetails
from starlette.exceptions import HTTPException as StarletteHTTPException

from gradeflow_backend.schemas.errors import ErrorResponse
from gradeflow_backend.services.exceptions import AppError

logger = logging.getLogger(__name__)

_REQUEST_VALIDATION_LOCATION_PREFIXES = {"body", "query", "path", "header", "cookie"}


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


def _strip_request_validation_location_prefix(error: ErrorDetails) -> ErrorDetails:
    loc = error.get("loc")
    if (
        not isinstance(loc, tuple | list)
        or not loc
        or loc[0] not in _REQUEST_VALIDATION_LOCATION_PREFIXES
    ):
        return error
    return cast(ErrorDetails, {**error, "loc": tuple(loc[1:])})


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
        assert isinstance(exc, StarletteHTTPException)
        message = _http_message(exc.status_code, exc.detail)
        return _error_response(
            status_code=exc.status_code,
            code=_http_error_code(exc.status_code),
            message=message,
        )

    async def request_validation_handler(_: Request, exc: Exception) -> JSONResponse:
        assert isinstance(exc, RequestValidationError)
        errors = cast(list[ErrorDetails], exc.errors())
        messages = format_validation_error_details(
            [_strip_request_validation_location_prefix(error) for error in errors]
        )
        return _error_response(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="VALIDATION_ERROR",
            message="Request validation failed",
            errors=messages,
        )

    async def pydantic_validation_handler(_: Request, exc: Exception) -> JSONResponse:
        assert isinstance(exc, ValidationError)
        messages = format_validation_error_details(exc.errors())
        return _error_response(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="VALIDATION_ERROR",
            message="Validation failed",
            errors=messages,
        )

    async def gradeflow_validation_handler(_: Request, exc: Exception) -> JSONResponse:
        assert isinstance(exc, GradeFlowValidationError)
        return _error_response(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="GRADEFLOW_VALIDATION_ERROR",
            message=str(exc).splitlines()[0],
            errors=exc.messages,
        )

    async def gradeflow_error_handler(_: Request, exc: Exception) -> JSONResponse:
        return _error_response(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
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
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, request_validation_handler)
    app.add_exception_handler(ValidationError, pydantic_validation_handler)
    app.add_exception_handler(GradeFlowValidationError, gradeflow_validation_handler)
    app.add_exception_handler(GradeFlowError, gradeflow_error_handler)
    app.add_exception_handler(Exception, unexpected_error_handler)
