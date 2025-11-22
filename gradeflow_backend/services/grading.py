import yaml
from gradeflow_engine.core import save_graded_submissions
from gradeflow_engine.question_sets.model import QuestionSet
from gradeflow_engine.rubrics.model import Rubric
from gradeflow_engine.rules.result import QuestionResult
from gradeflow_engine.submissions.models import GradedSubmission, RawSubmission
from sqlalchemy.exc import NoResultFound

from gradeflow_backend.repositories.assessments import AssessmentRepository
from gradeflow_backend.schemas.grading import (
    AdjustableGradedSubmission,
    AdjustableQuestionResult,
    GradeAdjustmentRequest,
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

        qset_yaml = a.question_set_yaml
        if not qset_yaml:
            raise NotFoundError("Question set not set")
        qset = QuestionSet.model_validate(yaml.safe_load(qset_yaml))

        rubric_yaml = a.rubric_yaml
        if not rubric_yaml:
            raise NotFoundError("Rubric not set")
        rubric = Rubric.model_validate(yaml.safe_load(rubric_yaml))

        validation_errors = rubric.validate_rubric(qset)
        if validation_errors:
            raise RubricValidationError(validation_errors)

        subs_yaml = a.submissions_yaml
        if not subs_yaml:
            raise NotFoundError("Submissions not set")
        raw_items: list[dict[str, object]] = yaml.safe_load(subs_yaml)
        raw_subs: list[RawSubmission] = [RawSubmission.model_validate(obj) for obj in raw_items]

        submissions = qset.parse(raw_subs)
        graded = rubric.grade(submissions)
        graded_adjustable: list[AdjustableGradedSubmission] = [
            AdjustableGradedSubmission(
                **{k: v for k, v in gs.model_dump().items() if k != "results"},
                results=[
                    AdjustableQuestionResult(
                        **res.model_dump(),
                        adjusted_points=None,
                        adjusted_feedback=None,
                    )
                    for res in gs.results
                ],
            )
            for gs in graded
        ]

        graded_payload = [gs.model_dump() for gs in graded_adjustable]
        self.repo.set_graded_yaml(assessment_id, yaml.safe_dump(graded_payload))

        return GradingResponse(graded_submissions=graded_adjustable)

    def get(self, assessment_id: str) -> GradingResponse:
        try:
            graded_yaml = self.repo.get_graded_yaml(assessment_id)
        except NoResultFound as e:
            raise NotFoundError("Assessment not found") from e
        if not graded_yaml:
            return GradingResponse(graded_submissions=[])

        graded_items: list[dict[str, object]] = yaml.safe_load(graded_yaml)
        graded_adjustable = [AdjustableGradedSubmission.model_validate(obj) for obj in graded_items]
        return GradingResponse(graded_submissions=graded_adjustable)

    def delete(self, assessment_id: str) -> None:
        try:
            self.repo.set_graded_yaml(assessment_id, None)
        except NoResultFound as e:
            raise NotFoundError("Assessment not found") from e

    def adjust(self, assessment_id: str, req: GradeAdjustmentRequest) -> GradingResponse:
        try:
            graded_yaml = self.repo.get_graded_yaml(assessment_id)
        except NoResultFound as e:
            raise NotFoundError("Assessment not found") from e
        if not graded_yaml:
            raise BadRequestError("No graded results to adjust. Run grading first.")

        graded_items: list[dict[str, object]] = yaml.safe_load(graded_yaml)
        graded = [AdjustableGradedSubmission.model_validate(obj) for obj in graded_items]

        # Build lookup: (student_id, question_id) -> AdjustableQuestionResult
        index: dict[tuple[str, str], AdjustableQuestionResult] = {}
        for gs in graded:
            for res in gs.results:
                index[(gs.student_id, res.question_id)] = res

        # Apply adjustments
        for adj in req.adjustments:
            key = (adj.student_id, adj.question_id)
            if key not in index:
                raise BadRequestError(
                    f"No result found: student_id={adj.student_id}, question_id={adj.question_id}"
                )
            target = index[key]
            # Validate and set adjusted_points if provided
            if adj.adjusted_points is not None:
                new_points = float(adj.adjusted_points)
                if new_points < 0:
                    raise BadRequestError("adjusted_points must be >= 0")
                if new_points > target.max_points:
                    raise BadRequestError(
                        f"adjusted_points ({new_points}) exceeds max_points ({target.max_points})"
                    )
                target.adjusted_points = new_points
            # Set adjusted_feedback if provided
            if adj.adjusted_feedback is not None:
                target.adjusted_feedback = adj.adjusted_feedback

        # Persist
        payload = [gs.model_dump() for gs in graded]
        self.repo.set_graded_yaml(assessment_id, yaml.safe_dump(payload))

        return GradingResponse(graded_submissions=graded)

    def export(self, assessment_id: str, req: GradingExportRequest) -> GradingExportResponse:
        try:
            a = self.repo.get(assessment_id)
        except NoResultFound as e:
            raise NotFoundError("Assessment not found") from e
        graded_yaml = a.graded_submissions_yaml
        if not graded_yaml:
            raise BadRequestError("No graded results to export. Run grading first.")

        graded_items: list[dict[str, object]] = yaml.safe_load(graded_yaml)
        adjustable = [AdjustableGradedSubmission.model_validate(obj) for obj in graded_items]

        # Build GradedSubmission objects using adjusted values when present
        adjusted_for_export: list[GradedSubmission] = []
        for ags in adjustable:
            # Convert results: use adjusted_points/feedback if available
            converted_results: list[QuestionResult] = []
            for r in ags.results:
                converted_results.append(
                    QuestionResult(
                        output=r.output,
                        passed=r.passed,
                        feedback=r.adjusted_feedback
                        if r.adjusted_feedback is not None
                        else r.feedback,
                        rule=r.rule,
                        question_id=r.question_id,
                        points=r.adjusted_points if r.adjusted_points is not None else r.points,
                        max_points=r.max_points,
                    )
                )
            adjusted_for_export.append(
                GradedSubmission(
                    student_id=ags.student_id, answer_map=ags.answer_map, results=converted_results
                )
            )

        out = save_graded_submissions(
            graded_submissions=adjusted_for_export,
            saver_name=req.saver_name,
            **(req.submissions_saver_kwargs or {}),
        )

        safe_assessment_name = "".join(
            c if c.isalnum() or c in (" ", "_", "-") else "_" for c in a.name
        ).rstrip()
        filename = f"graded_{safe_assessment_name}.{out.extension}"
        return GradingExportResponse(data=out.data, extension=out.extension, filename=filename)
