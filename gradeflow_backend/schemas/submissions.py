from typing import Any, Literal

from gradeflow_engine.submissions.models import RawSubmission
from pydantic import BaseModel


class SetSubmissionsByModelRequest(BaseModel):
    raw_submissions: list[RawSubmission]


class SetSubmissionsByDataRequest(BaseModel):
    data: str
    loader_name: Literal["CSV"] = "CSV"
    loader_kwargs: dict[str, Any] = {}


class SubmissionsResponse(BaseModel):
    raw_submissions: list[RawSubmission]
