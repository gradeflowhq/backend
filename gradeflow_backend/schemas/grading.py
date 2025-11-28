from typing import Any, Literal

from gradeflow_engine.question_sets.model import QuestionSet
from gradeflow_engine.rubrics.model import Rubric
from gradeflow_engine.rules.models import QuestionRule
from gradeflow_engine.rules.result import QuestionResult
from gradeflow_engine.submissions.models import GradedSubmission, RawSubmission, Submission
from gradeflow_engine.submissions.savers.base import SubmissionsSaverOutput
from pydantic import BaseModel, Field


class AdjustableQuestionResult(QuestionResult):
    adjusted_points: float | None = Field(
        default=None, description="Adjusted points for this question"
    )
    adjusted_feedback: str | None = Field(
        default=None, description="Adjusted feedback for this question"
    )


class AdjustableGradedSubmission(Submission):
    results: list[AdjustableQuestionResult]


class GradingRunRequest(BaseModel):
    pass


class GradingResponse(BaseModel):
    graded_submissions: list[AdjustableGradedSubmission]


class GradingExportRequest(BaseModel):
    saver_name: Literal["CSV"] = "CSV"
    submissions_saver_kwargs: dict[str, Any] | None = None


class GradingExportResponse(SubmissionsSaverOutput):
    filename: str


class GradeAdjustment(BaseModel):
    student_id: str = Field(..., description="Student ID to adjust")
    question_id: str = Field(..., description="Question ID to adjust")
    adjusted_points: float | None = Field(default=None, description="New points (optional)")
    adjusted_feedback: str | None = Field(default=None, description="New feedback (optional)")


class GradeAdjustmentRequest(BaseModel):
    adjustments: list[GradeAdjustment] = Field(..., min_length=1)


class GradingLimitConfig(BaseModel):
    limit: int | None = Field(
        default=5,
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
    graded_submissions: list[GradedSubmission]


class GradingJob(BaseModel):
    job_id: str
    url: str
