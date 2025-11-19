from typing import Any, Literal

from gradeflow_engine.rules.result import QuestionResult
from gradeflow_engine.submissions.models import Submission
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
