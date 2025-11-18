import json

from gradeflow_engine.core import save_graded_submissions
from gradeflow_engine.question_sets.model import QuestionSet
from gradeflow_engine.rubrics.model import Rubric
from gradeflow_engine.submissions.models import GradedSubmission, RawSubmission
from sqlalchemy.exc import NoResultFound

from gradeflow_backend.repositories.assessments import AssessmentRepository
from gradeflow_backend.schemas.grading import (
    GradingExportRequest,
    GradingExportResponse,
    GradingResponse,
    GradingRunRequest,
)
from gradeflow_backend.services.exceptions import (
    BadRequestError,
    NotFoundError,
    RubricValidationError,
)


class GradingService:
    def __init__(self, repo: AssessmentRepository) -> None:
        self.repo = repo

    def run(self, assessment_id: str, req: GradingRunRequest) -> GradingResponse:
        try:
            a = self.repo.get(assessment_id)
        except NoResultFound as e:
            raise NotFoundError("Assessment not found") from e

        qset_json = a.question_set_json
        if not qset_json:
            raise NotFoundError("Question set not set")
        qset = QuestionSet.model_validate_json(qset_json)

        rubric_json = a.rubric_json
        if not rubric_json:
            raise NotFoundError("Rubric not set")
        rubric = Rubric.model_validate_json(rubric_json)

        validation_errors = rubric.validate_rubric(qset)
        if validation_errors:
            raise RubricValidationError(validation_errors)

        subs_json = a.submissions_json
        if not subs_json:
            raise NotFoundError("Submissions not set")
        raw_items: list[dict[str, object]] = json.loads(subs_json)
        raw_subs: list[RawSubmission] = [RawSubmission.model_validate(obj) for obj in raw_items]

        submissions = qset.parse(raw_subs)
        graded: list[GradedSubmission] = rubric.grade(submissions)

        graded_payload = [gs.model_dump() for gs in graded]
        self.repo.set_graded_json(assessment_id, json.dumps(graded_payload))

        return GradingResponse(graded_submissions=graded)

    def get(self, assessment_id: str) -> GradingResponse:
        try:
            graded_json = self.repo.get_graded_json(assessment_id)
        except NoResultFound as e:
            raise NotFoundError("Assessment not found") from e
        if not graded_json:
            return GradingResponse(graded_submissions=[])

        graded_items: list[dict[str, object]] = json.loads(graded_json)
        graded = [GradedSubmission.model_validate(obj) for obj in graded_items]
        return GradingResponse(graded_submissions=graded)

    def delete(self, assessment_id: str) -> None:
        try:
            self.repo.set_graded_json(assessment_id, None)
        except NoResultFound as e:
            raise NotFoundError("Assessment not found") from e

    def export(self, assessment_id: str, req: GradingExportRequest) -> GradingExportResponse:
        try:
            graded_json = self.repo.get_graded_json(assessment_id)
        except NoResultFound as e:
            raise NotFoundError("Assessment not found") from e
        if not graded_json:
            raise BadRequestError("No graded results to export. Run grading first.")

        graded_items: list[dict[str, object]] = json.loads(graded_json)
        graded = [GradedSubmission.model_validate(obj) for obj in graded_items]

        out = save_graded_submissions(
            graded_submissions=graded,
            saver_name=req.saver_name,
            **(req.submissions_saver_kwargs or {}),
        )

        filename = f"graded_{assessment_id}.{out.extension}"
        return GradingExportResponse(data=out.data, extension=out.extension, filename=filename)
