from gradeflow_engine.submissions.models import RawSubmission
from pydantic import BaseModel, Field


class UploadSourceDataRequest(BaseModel):
    data: str = Field(
        ..., description="Processed CSV text (rows trimmed, student IDs optionally encrypted)"
    )
    student_id_column: str = Field(
        ..., description="Name of the student ID column in the uploaded CSV"
    )


class SourceDataResponse(BaseModel):
    headers: list[str]
    rows: list[list[str]]
    total_rows: int
    student_id_column: str | None = None


class SubmissionsImportConfig(BaseModel):
    answer_columns: list[str] | None = None
    point_columns: dict[str, str] | None = None  # question_id (= column name) -> points CSV column


class SubmissionsResponse(BaseModel):
    raw_submissions: list[RawSubmission]
