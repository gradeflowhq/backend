from gradeflow_engine.adapters.question_set import QuestionSetAdapterConfig
from gradeflow_engine.question_sets.inference import (
    DEFAULT_CHOICE_DELIMITER,
    DEFAULT_CHOICE_OPTION_LIMIT,
    DEFAULT_MULTI_VALUE_DELIMITER,
)
from gradeflow_engine.question_sets.model import QuestionSet
from gradeflow_engine.serializations.question_set import QuestionSetSerializerConfig
from gradeflow_engine.submissions.models import RawSubmission, Submission
from pydantic import BaseModel, Field


class SetQuestionSetByModelRequest(BaseModel):
    question_set: QuestionSet


class LoadQuestionSetRequest(BaseModel):
    data: str
    serializer: QuestionSetSerializerConfig  # discriminated by "format" (e.g., {"format":"yaml"})


class ImportQuestionSetRequest(BaseModel):
    data: str | bytes = Field(..., description="Source content; str or bytes")
    adapter: QuestionSetAdapterConfig  # e.g., {"name":"examplify", ...}


class QuestionSetResponse(BaseModel):
    question_set: QuestionSet


class InferQuestionSetRequest(BaseModel):
    use_stored_submissions: bool = True
    raw_submissions: list[RawSubmission] | None = None
    choice_delimiter: str = Field(default=DEFAULT_CHOICE_DELIMITER)
    choice_option_limit: int = Field(default=DEFAULT_CHOICE_OPTION_LIMIT)
    multi_value_delimiter: str = Field(default=DEFAULT_MULTI_VALUE_DELIMITER)
    commit: bool = Field(default=True, description="If true, store as question set")


class ParseSubmissionsRequest(BaseModel):
    use_stored_question_set: bool = True
    use_stored_submissions: bool = True
    question_set: QuestionSet | None = None
    raw_submissions: list[RawSubmission] | None = None


class ParseSubmissionsResponse(BaseModel):
    submissions: list[Submission]
