from typing import Annotated, Literal

from gradeflow_engine.question_sets.model import QuestionSet
from gradeflow_engine.questions.types import QuestionId
from gradeflow_engine.rubrics.model import Rubric
from gradeflow_engine.rules.models import QuestionRule
from gradeflow_engine.rules.result import QuestionResult
from gradeflow_engine.serializations.submissions import SubmissionsSerializerConfig
from gradeflow_engine.submissions.models import RawSubmission, Submission
from pydantic import BaseModel, Field

from gradeflow_backend.config import get_settings
from gradeflow_backend.schemas.status import SectionStatus

grading_settings = get_settings().grading


class AdjustableQuestionResult(QuestionResult):
    adjusted_points: float | None = Field(
        default=None, description="Adjusted points for this question"
    )
    adjusted_feedback: str | None = Field(
        default=None, description="Adjusted feedback for this question"
    )


class AdjustableSubmission(Submission):
    result_map: Annotated[dict[QuestionId, AdjustableQuestionResult], Field(default_factory=dict)]  # type: ignore[assignment]


class GradingRunRequest(BaseModel):
    pass


class GradingResponse(BaseModel):
    submissions: list[AdjustableSubmission]
    status: SectionStatus


class GradingDownloadRequest(BaseModel):
    serializer: SubmissionsSerializerConfig  # discriminated by "format" (csv|json|yaml)


class GradingDownloadResponse(BaseModel):
    filename: str
    data: bytes
    extension: str
    media_type: str  # e.g. "text/csv" | "application/json" | "application/yaml"


class GradeAdjustmentRequest(BaseModel):
    student_id: str = Field(..., description="Student ID to adjust")
    question_id: str = Field(..., description="Question ID to adjust")
    adjusted_points: float | None = Field(default=None, ge=0, description="New points (optional)")
    adjusted_feedback: str | None = Field(default=None, description="New feedback (optional)")


class GradingLimitConfig(BaseModel):
    limit: int | None = Field(
        default=5,
        ge=1,
        le=grading_settings.max_submission_preview,
        description="If provided, preview only this many submissions.",
    )
    selection: Literal["first", "random"] = Field(
        default="first",
        description="How to select limited submissions: 'first' (deterministic) or 'random'.",
    )
    seed: int | None = Field(
        default=None,
        description="Random seed used when selection='random' for reproducibility.",
    )


class GradingPreviewRequest(BaseModel):
    rule: QuestionRule | None = Field(
        default=None,
        description="If provided, preview grading for this single rule only.",
    )
    config: GradingLimitConfig = Field(
        default_factory=GradingLimitConfig,
        description="Configuration for limiting the number of submissions to preview.",
    )


JobType = Literal["run", "preview"]
JobStatus = Literal["queued", "running", "completed", "failed"]


class JobStatusResponse(BaseModel):
    job_id: str
    status: JobStatus


class GradingJobSpec(BaseModel):
    assessment_id: str
    type: JobType
    raw_submissions: list[RawSubmission] = Field(..., min_length=1)
    question_set: QuestionSet
    rubric: Rubric


class GradingJobResult(BaseModel):
    assessment_id: str
    type: JobType
    submissions: list[Submission]


class GradingJob(BaseModel):
    job_id: str
    url: str
