import yaml
from gradeflow_engine.core import infer_question_set, load_question_set
from gradeflow_engine.question_sets.model import QuestionSet
from gradeflow_engine.submissions.models import RawSubmission
from sqlalchemy.exc import NoResultFound

from gradeflow_backend.repositories.assessments import AssessmentRepository
from gradeflow_backend.schemas.question_sets import (
    InferQuestionSetRequest,
    ParseSubmissionsRequest,
    ParseSubmissionsResponse,
    QuestionSetResponse,
    SetQuestionSetByDataRequest,
    SetQuestionSetByModelRequest,
)
from gradeflow_backend.services.exceptions import BadRequestError, NotFoundError


class QuestionSetService:
    def __init__(self, repo: AssessmentRepository) -> None:
        self.repo = repo

    def set_by_model(
        self, assessment_id: str, req: SetQuestionSetByModelRequest
    ) -> QuestionSetResponse:
        try:
            self.repo.set_question_set_yaml(
                assessment_id, yaml.safe_dump(req.question_set.model_dump())
            )
        except NoResultFound as e:
            raise NotFoundError("Assessment not found") from e
        return QuestionSetResponse(question_set=req.question_set)

    def set_by_data(
        self, assessment_id: str, req: SetQuestionSetByDataRequest
    ) -> QuestionSetResponse:
        qset = load_question_set(req.data, loader_name=req.loader_name)
        try:
            self.repo.set_question_set_yaml(assessment_id, yaml.safe_dump(qset.model_dump()))
        except NoResultFound as e:
            raise NotFoundError("Assessment not found") from e
        return QuestionSetResponse(question_set=qset)

    def get(self, assessment_id: str) -> QuestionSetResponse:
        try:
            yaml_str = self.repo.get_question_set_yaml(assessment_id)
        except NoResultFound as e:
            raise NotFoundError("Assessment not found") from e
        if not yaml_str:
            raise NotFoundError("Question set not set")
        qset = QuestionSet.model_validate(yaml.safe_load(yaml_str))
        return QuestionSetResponse(question_set=qset)

    def delete(self, assessment_id: str) -> None:
        try:
            self.repo.set_question_set_yaml(assessment_id, None)
        except NoResultFound as e:
            raise NotFoundError("Assessment not found") from e

    def infer(self, assessment_id: str, req: InferQuestionSetRequest) -> QuestionSetResponse:
        try:
            a = self.repo.get(assessment_id)
        except NoResultFound as e:
            raise NotFoundError("Assessment not found") from e

        raw_subs: list[RawSubmission]
        if req.use_stored_submissions:
            subs_yaml = a.submissions_yaml
            if not subs_yaml:
                raise NotFoundError("No submissions stored for this assessment")
            items = yaml.safe_load(subs_yaml)
            raw_subs = [RawSubmission.model_validate(obj) for obj in items]
        else:
            if not req.raw_submissions:
                raise BadRequestError(
                    "raw_submissions must be provided when use_stored_submissions=false"
                )
            raw_subs = req.raw_submissions

        qset = infer_question_set(
            raw_submissions=raw_subs,
            choice_delimiter=req.choice_delimiter,
            choice_option_limit=req.choice_option_limit,
            multi_value_delimiter=req.multi_value_delimiter,
        )
        if req.commit:
            self.repo.set_question_set_yaml(assessment_id, yaml.safe_dump(qset.model_dump()))
        return QuestionSetResponse(question_set=qset)

    def parse(self, assessment_id: str, req: ParseSubmissionsRequest) -> ParseSubmissionsResponse:
        try:
            a = self.repo.get(assessment_id)
        except NoResultFound as e:
            raise NotFoundError("Assessment not found") from e

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

        if req.use_stored_submissions:
            subs_yaml = a.submissions_yaml
            if not subs_yaml:
                raise NotFoundError("Submissions not set")
            items = yaml.safe_load(subs_yaml)
            raw_subs = [RawSubmission.model_validate(obj) for obj in items]
        else:
            if req.raw_submissions is None:
                raise BadRequestError(
                    "raw_submissions must be provided when use_stored_submissions=false"
                )
            raw_subs = req.raw_submissions

        try:
            submissions = qset.parse(raw_subs)
        except ValueError as e:
            raise BadRequestError(f"Failed to parse submissions: {e}") from e
        return ParseSubmissionsResponse(submissions=submissions)
