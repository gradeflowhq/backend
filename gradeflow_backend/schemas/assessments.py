import re
from datetime import datetime
from typing import TypeAlias

from pydantic import BaseModel, Field, JsonValue, field_validator

AssessmentMetadata: TypeAlias = dict[str, JsonValue]
METADATA_KEY_PATTERN = r"^[A-Za-z0-9_.:-]+$"
_METADATA_KEY_RE = re.compile(METADATA_KEY_PATTERN)


class AssessmentCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)


class AssessmentUpdateRequest(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=2000)


class AssessmentMetadataRequest(BaseModel):
    metadata: AssessmentMetadata = Field(default_factory=dict)

    @field_validator("metadata")
    @classmethod
    def validate_keys(cls, metadata: AssessmentMetadata) -> AssessmentMetadata:
        for key in metadata:
            if len(key) > 128 or not _METADATA_KEY_RE.fullmatch(key):
                raise ValueError(
                    "metadata keys must be 1-128 characters and contain only letters, "
                    "numbers, underscores, periods, colons, or hyphens"
                )
        return metadata


class AssessmentMetadataResponse(BaseModel):
    metadata: AssessmentMetadata = Field(default_factory=dict)


class AssessmentMetadataValueRequest(BaseModel):
    value: JsonValue


class AssessmentMetadataValueResponse(BaseModel):
    key: str
    value: JsonValue


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
