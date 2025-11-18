class NotFoundError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class BadRequestError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class RubricValidationError(Exception):
    def __init__(self, errors: list[str]) -> None:
        super().__init__("Rubric validation failed")
        self.errors = errors
