from gradeflow_engine.adapters.raw_submissions import SubmissionsConfigAdapter
from gradeflow_engine.submissions.models import RawSubmission
from pydantic import BaseModel, Field


class SetSubmissionsByModelRequest(BaseModel):
    raw_submissions: list[RawSubmission]


class ImportSubmissionsRequest(BaseModel):
    data: str | bytes = Field(..., description="Source content; str or bytes")
    adapter: SubmissionsConfigAdapter  # e.g., {"name":"csv", "student_id_column":"student_id", ...}


class SubmissionsResponse(BaseModel):
    raw_submissions: list[RawSubmission]
