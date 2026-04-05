from datetime import datetime

from pydantic import BaseModel, Field


class AssessmentCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)


class AssessmentUpdateRequest(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=2000)


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


class AssessmentsListResponse(BaseModel):
    items: list[AssessmentResponse]
