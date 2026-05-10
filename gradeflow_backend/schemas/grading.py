from datetime import datetime
from typing import Annotated, Literal

from gradeflow_engine.question_sets.model import QuestionSet
from gradeflow_engine.questions.types import QuestionId
from gradeflow_engine.rubrics.model import Rubric, RubricGradingParallelMode
from gradeflow_engine.rules.models import QuestionRule
from gradeflow_engine.rules.result import QuestionResult
from gradeflow_engine.serializations.submissions import SubmissionsSerializerConfig
from gradeflow_engine.submissions.models import RawSubmission, Submission
from pydantic import BaseModel, Field, JsonValue

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
    remove_adjustments: bool = Field(
        default=False,
        description="When True, clear all manual adjustments on re-graded submissions.",
    )
    override_results: bool = Field(
        default=True,
        description="When True, a rule result overwrites any pre-existing points/feedback.",
    )


class GradingResponse(BaseModel):
    submissions: list[AdjustableSubmission]
    status: SectionStatus


class GradingPreviewResult(BaseModel):
    submissions: list[Submission]
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class GradingPreviewResponse(BaseModel):
    submissions: list[AdjustableSubmission]
    status: SectionStatus
    answer_question_ids: list[QuestionId] = Field(default_factory=list)
    result_question_ids: list[QuestionId] = Field(default_factory=list)


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


class BulkGradeAdjustmentRequest(BaseModel):
    adjustments: list[GradeAdjustmentRequest] = Field(
        ..., min_length=1, description="List of grade adjustments to apply in a single request"
    )


class BulkGradeAdjustmentResponse(BaseModel):
    applied: int = Field(..., description="Number of adjustments successfully applied")
    errors: list[str] = Field(
        default_factory=list, description="Error messages for failed adjustments"
    )
    result: GradingResponse = Field(..., description="Updated grading results")


class GradingLimitConfig(BaseModel):
    limit: int | None = Field(
        default=5,
        ge=1,
        le=grading_settings.max_submission_preview,
        description="If provided, preview only this many submissions.",
    )
    selection: Literal["first", "random", "random_unique"] = Field(
        default="random_unique",
        description=(
            "How to select limited submissions: 'first' (deterministic), 'random', "
            "or 'random_unique' (random unique answers)."
        ),
    )
    seed: int | None = Field(
        default=None,
        description=(
            "Random seed used when selection='random' or selection='random_unique' "
            "for reproducibility."
        ),
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


class GradingJobSpec(BaseModel):
    assessment_id: str
    type: JobType
    raw_submissions: list[RawSubmission] = Field(..., min_length=1)
    question_set: QuestionSet
    rubric: Rubric
    remove_adjustments: bool = Field(
        default=False,
        description="When True, clear all manual adjustments on re-graded submissions.",
    )
    override_results: bool = Field(default=True)
    grade_questions_without_rule: bool = Field(default=True)
    rubric_grading_parallel_jobs: int = Field(default=1)
    rubric_grading_parallel_mode: RubricGradingParallelMode = Field(default="processes")
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class GradingJobResult(BaseModel):
    job_id: str
    assessment_id: str
    type: JobType
    submissions: list[Submission]
    remove_adjustments: bool = Field(
        default=False,
        description="When True, clear all manual adjustments on re-graded submissions.",
    )
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class JobTiming(BaseModel):
    finished_at: datetime | None = None
    duration_seconds: float | None = None
    estimated_duration_seconds: float | None = None
    estimated_completion_at: datetime | None = None


class JobStatusResponse(JobTiming):
    job_id: str
    status: JobStatus
    error: str | None = None
    created_at: datetime


class GradingJob(JobTiming):
    job_id: str
    url: str
    status: JobStatus
    error: str | None = None
    created_at: datetime
