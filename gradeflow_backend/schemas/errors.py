from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    code: str = Field(..., description="Stable machine-readable error code")
    message: str = Field(..., description="Human-readable error summary")
    errors: list[str] = Field(
        default_factory=list,
        description=(
            "Specific error details. Usually contains the same message for single-error responses."
        ),
    )
