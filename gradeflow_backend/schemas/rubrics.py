from typing import Literal

from gradeflow_engine.question_sets.model import QuestionSet
from gradeflow_engine.rubrics.model import Rubric, RubricCoverage
from gradeflow_engine.rules.types import RuleValidationError
from pydantic import BaseModel


class SetRubricByModelRequest(BaseModel):
    rubric: Rubric


class SetRubricByDataRequest(BaseModel):
    data: str
    loader_name: Literal["YAML"] = "YAML"


class RubricResponse(BaseModel):
    rubric: Rubric


class ValidateRubricRequest(BaseModel):
    use_stored_rubric: bool = True
    use_stored_question_set: bool = True
    rubric: Rubric | None = None
    question_set: QuestionSet | None = None


class ValidateRubricResponse(BaseModel):
    errors: list[RuleValidationError]


class CoverageRequest(BaseModel):
    use_stored_rubric: bool = True
    use_stored_question_set: bool = True
    rubric: Rubric | None = None
    question_set: QuestionSet | None = None


class CoverageResponse(BaseModel):
    coverage: RubricCoverage
