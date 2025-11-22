import yaml
from gradeflow_engine.core import load_rubric
from gradeflow_engine.question_sets.model import QuestionSet
from gradeflow_engine.rubrics.model import Rubric
from sqlalchemy.exc import NoResultFound

from gradeflow_backend.repositories.assessments import AssessmentRepository
from gradeflow_backend.schemas.rubrics import (
    CoverageRequest,
    CoverageResponse,
    RubricResponse,
    SetRubricByDataRequest,
    SetRubricByModelRequest,
    ValidateRubricRequest,
    ValidateRubricResponse,
)
from gradeflow_backend.services.exceptions import BadRequestError, NotFoundError
from gradeflow_backend.utils.engine import model_dump_minimal


class RubricService:
    def __init__(self, repo: AssessmentRepository) -> None:
        self.repo = repo

    def set_by_model(self, assessment_id: str, req: SetRubricByModelRequest) -> RubricResponse:
        try:
            self.repo.set_rubric_yaml(assessment_id, yaml.safe_dump(model_dump_minimal(req.rubric)))
        except NoResultFound as e:
            raise NotFoundError("Assessment not found") from e
        return RubricResponse(rubric=req.rubric)

    def set_by_data(self, assessment_id: str, req: SetRubricByDataRequest) -> RubricResponse:
        rubric = load_rubric(req.data, loader_name=req.loader_name)
        try:
            self.repo.set_rubric_yaml(assessment_id, yaml.safe_dump(model_dump_minimal(rubric)))
        except NoResultFound as e:
            raise NotFoundError("Assessment not found") from e
        return RubricResponse(rubric=rubric)

    def get(self, assessment_id: str) -> RubricResponse:
        try:
            yaml_str = self.repo.get_rubric_yaml(assessment_id)
        except NoResultFound as e:
            raise NotFoundError("Assessment not found") from e
        if not yaml_str:
            raise NotFoundError("Rubric not set")
        rubric = Rubric.model_validate(yaml.safe_load(yaml_str))
        return RubricResponse(rubric=rubric)

    def delete(self, assessment_id: str) -> None:
        try:
            self.repo.set_rubric_yaml(assessment_id, None)
        except NoResultFound as e:
            raise NotFoundError("Assessment not found") from e

    def validate(self, assessment_id: str, req: ValidateRubricRequest) -> ValidateRubricResponse:
        try:
            a = self.repo.get(assessment_id)
        except NoResultFound as e:
            raise NotFoundError("Assessment not found") from e

        if req.use_stored_rubric:
            rubric_yaml = a.rubric_yaml
            if not rubric_yaml:
                raise NotFoundError("Rubric not set")
            rubric = Rubric.model_validate(yaml.safe_load(rubric_yaml))
        else:
            if req.rubric is None:
                raise BadRequestError("rubric must be provided when use_stored_rubric=false")
            rubric = req.rubric

        if req.use_stored_question_set:
            qset_yaml = a.question_set_yaml
            if not qset_yaml:
                raise NotFoundError("Question set not set")
            qset = QuestionSet.model_validate(yaml.safe_load(qset_yaml))
        else:
            if req.question_set is None:
                raise BadRequestError(
                    "question_set must be provided when use_stored_question_set=false"
                )
            qset = req.question_set

        errors = rubric.validate_rubric(qset)
        return ValidateRubricResponse(errors=errors)

    def coverage(self, assessment_id: str, req: CoverageRequest) -> CoverageResponse:
        try:
            a = self.repo.get(assessment_id)
        except NoResultFound as e:
            raise NotFoundError("Assessment not found") from e

        if req.use_stored_rubric:
            rubric_yaml = a.rubric_yaml
            if not rubric_yaml:
                raise NotFoundError("Rubric not set")
            rubric = Rubric.model_validate(yaml.safe_load(rubric_yaml))
        else:
            if req.rubric is None:
                raise BadRequestError("rubric must be provided when use_stored_rubric=false")
            rubric = req.rubric

        if req.use_stored_question_set:
            qset_yaml = a.question_set_yaml
            if not qset_yaml:
                raise NotFoundError("Question set not set")
            qset = QuestionSet.model_validate(yaml.safe_load(qset_yaml))
        else:
            if req.question_set is None:
                raise BadRequestError(
                    "question_set must be provided when use_stored_question_set=false"
                )
            qset = req.question_set

        cov = rubric.get_coverage(qset)
        return CoverageResponse(coverage=cov)
