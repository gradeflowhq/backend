from typing import Any, Literal

from gradeflow_engine.submissions.models import GradedSubmission
from gradeflow_engine.submissions.savers.base import SubmissionsSaverOutput
from pydantic import BaseModel


class GradingRunRequest(BaseModel):
    pass


class GradingResponse(BaseModel):
    graded_submissions: list[GradedSubmission]


class GradingExportRequest(BaseModel):
    saver_name: Literal["CSV"] = "CSV"
    submissions_saver_kwargs: dict[str, Any] | None = None


class GradingExportResponse(SubmissionsSaverOutput):
    filename: str
