from datetime import datetime

from pydantic import BaseModel, Field


class AssessmentCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)


class AssessmentUpdateRequest(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=2000)


class AssessmentCoverage(BaseModel):
    total: int = 0
    covered: int = 0
    percentage: float = 0.0


class AssessmentSummary(BaseModel):
    submission_count: int | None = Field(
        default=None,
        description="Raw submission count (None when no source data uploaded)",
    )
    question_count: int | None = Field(
        default=None,
        description="Question count (None when no question set configured)",
    )
    graded_count: int = Field(
        default=0,
        description="Number of graded student submissions in the database",
    )
    coverage: AssessmentCoverage | None = Field(
        default=None,
        description="Rubric coverage stats (None when rubric or question set is absent)",
    )


class AssessmentResponse(BaseModel):
    id: str
    name: str
    description: str | None = None
    created_at: datetime
    updated_at: datetime
    source_updated_at: datetime | None = None
    question_set_updated_at: datetime | None = None
    rubric_updated_at: datetime | None = None
    results_updated_at: datetime | None = None
    summary: AssessmentSummary | None = Field(
        default=None,
        description="Pre-computed summary stats",
    )


class AssessmentsListResponse(BaseModel):
    items: list[AssessmentResponse]
