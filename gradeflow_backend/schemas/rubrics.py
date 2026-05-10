from gradeflow_engine.adapters.rubric import RubricAdapterConfig
from gradeflow_engine.question_sets.model import QuestionSet
from gradeflow_engine.rubrics.model import (
    Rubric,
    RubricCoverage,
    StaleRuleReference,
)
from gradeflow_engine.rules.models import (
    MultiTargetQuestionRule,
    QuestionRule,
    SingleTargetQuestionRule,
)
from gradeflow_engine.rules.types import RuleValidationError
from gradeflow_engine.serializations.rubric import RubricSerializerConfig
from pydantic import BaseModel, Field

from gradeflow_backend.schemas.status import SectionStatus


class SetRubricByModelRequest(BaseModel):
    rubric: Rubric


class LoadRubricRequest(BaseModel):
    data: str
    serializer: RubricSerializerConfig  # discriminated by "format" (e.g., {"format":"yaml"})


class ImportRubricRequest(BaseModel):
    data: str | bytes = Field(..., description="Source content; str or bytes")
    adapter: RubricAdapterConfig  # e.g., {"name":"examplify", ...}


class RubricResponse(BaseModel):
    rubric: Rubric
    status: SectionStatus


class RuleCreateRequest(BaseModel):
    rule: QuestionRule


class RuleUpdateRequest(BaseModel):
    rule: QuestionRule


class RulesResponse(BaseModel):
    rules: list[QuestionRule]
    status: SectionStatus


class ExportRubricRequest(BaseModel):
    serializer: RubricSerializerConfig


class ExportRubricResponse(BaseModel):
    filename: str
    data: bytes
    extension: str
    media_type: str


class ValidateRubricRequest(BaseModel):
    use_stored_rubric: bool = True
    use_stored_question_set: bool = True
    rubric: Rubric | None = None
    question_set: QuestionSet | None = None


class ValidateRubricResponse(BaseModel):
    errors: list[RuleValidationError]


class RubricOverviewResponse(BaseModel):
    question_rules: list[SingleTargetQuestionRule]
    global_rules: list[MultiTargetQuestionRule]
    coverage: RubricCoverage
    stale_rules: list[StaleRuleReference]
    status: SectionStatus
    validation_errors: list[str] = Field(default_factory=list)
