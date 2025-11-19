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


class RubricService:
    def __init__(self, repo: AssessmentRepository) -> None:
        self.repo = repo

    def set_by_model(self, assessment_id: str, req: SetRubricByModelRequest) -> RubricResponse:
        try:
            self.repo.set_rubric_json(assessment_id, req.rubric.model_dump_json())
        except NoResultFound as e:
            raise NotFoundError("Assessment not found") from e
        return RubricResponse(rubric=req.rubric)

    def set_by_data(self, assessment_id: str, req: SetRubricByDataRequest) -> RubricResponse:
        rubric = load_rubric(req.data, loader_name=req.loader_name)
        try:
            self.repo.set_rubric_json(assessment_id, rubric.model_dump_json())
        except NoResultFound as e:
            raise NotFoundError("Assessment not found") from e
        return RubricResponse(rubric=rubric)

    def get(self, assessment_id: str) -> RubricResponse:
        try:
            json_str = self.repo.get_rubric_json(assessment_id)
        except NoResultFound as e:
            raise NotFoundError("Assessment not found") from e
        if not json_str:
            raise NotFoundError("Rubric not set")
        rubric = Rubric.model_validate_json(json_str)
        return RubricResponse(rubric=rubric)

    def delete(self, assessment_id: str) -> None:
        try:
            self.repo.set_rubric_json(assessment_id, None)
        except NoResultFound as e:
            raise NotFoundError("Assessment not found") from e

    def validate(self, assessment_id: str, req: ValidateRubricRequest) -> ValidateRubricResponse:
        try:
            a = self.repo.get(assessment_id)
        except NoResultFound as e:
            raise NotFoundError("Assessment not found") from e

        if req.use_stored_rubric:
            rubric_json = a.rubric_json
            if not rubric_json:
                raise NotFoundError("Rubric not set")
            rubric = Rubric.model_validate_json(rubric_json)
        else:
            if req.rubric is None:
                raise BadRequestError("rubric must be provided when use_stored_rubric=false")
            rubric = req.rubric

        if req.use_stored_question_set:
            qset_json = a.question_set_json
            if not qset_json:
                raise NotFoundError("Question set not set")
            qset = QuestionSet.model_validate_json(qset_json)
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
            rubric_json = a.rubric_json
            if not rubric_json:
                raise NotFoundError("Rubric not set")
            rubric = Rubric.model_validate_json(rubric_json)
        else:
            if req.rubric is None:
                raise BadRequestError("rubric must be provided when use_stored_rubric=false")
            rubric = req.rubric

        if req.use_stored_question_set:
            qset_json = a.question_set_json
            if not qset_json:
                raise NotFoundError("Question set not set")
            qset = QuestionSet.model_validate_json(qset_json)
        else:
            if req.question_set is None:
                raise BadRequestError(
                    "question_set must be provided when use_stored_question_set=false"
                )
            qset = req.question_set

        cov = rubric.get_coverage(qset)
        return CoverageResponse(coverage=cov)
