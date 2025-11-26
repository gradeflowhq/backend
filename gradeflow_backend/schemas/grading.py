from typing import Any, Literal

from gradeflow_engine.question_sets.model import QuestionSet
from gradeflow_engine.rubrics.model import Rubric
from gradeflow_engine.rules.models import QuestionRule
from gradeflow_engine.rules.result import QuestionResult
from gradeflow_engine.submissions.models import RawSubmission, Submission
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


class GradingPreviewRequest(BaseModel):
    use_stored_question_set: bool = True
    use_stored_rubric: bool = True
    use_stored_submissions: bool = True
    question_set: QuestionSet | None = None
    rubric: Rubric | None = None
    raw_submissions: list[RawSubmission] | None = None

    rule: QuestionRule | None = Field(
        default=None,
        description="If provided, preview grading for this single rule only.",
    )

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
