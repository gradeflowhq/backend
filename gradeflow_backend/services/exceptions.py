class AppError(Exception):
    status_code = 500
    code = "INTERNAL_SERVER_ERROR"

    def __init__(self, message: str, *, errors: list[str] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.errors = errors or [message]


class NotFoundError(AppError):
    status_code = 404
    code = "NOT_FOUND"


class BadRequestError(AppError):
    status_code = 400
    code = "BAD_REQUEST"


class ServiceUnavailableError(AppError):
    status_code = 503
    code = "SERVICE_UNAVAILABLE"


class RubricValidationError(AppError):
    status_code = 422
    code = "RUBRIC_VALIDATION_ERROR"

    def __init__(self, errors: list[str]) -> None:
        super().__init__("Rubric validation failed", errors=errors)
