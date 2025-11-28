import random

import yaml
from fastapi import Request
from gradeflow_engine.core import save_graded_submissions
from gradeflow_engine.question_sets.model import QuestionSet
from gradeflow_engine.rubrics.model import Rubric
from gradeflow_engine.rules.models import QuestionRule
from gradeflow_engine.rules.result import QuestionResult
from gradeflow_engine.submissions.models import GradedSubmission, RawSubmission
from sqlalchemy.exc import NoResultFound

from gradeflow_backend.models.assessment import Assessment
from gradeflow_backend.repositories.assessments import AssessmentRepository
from gradeflow_backend.schemas.grading import (
    AdjustableGradedSubmission,
    AdjustableQuestionResult,
    GradeAdjustmentRequest,
    GradingExportRequest,
    GradingExportResponse,
    GradingJob,
    GradingJobSpec,
    GradingLimitConfig,
    GradingPreviewRequest,
    GradingResponse,
    GradingRunRequest,
    JobType,
)
from gradeflow_backend.services.exceptions import (
    BadRequestError,
    NotFoundError,
    RubricValidationError,
)
from gradeflow_backend.services.jobs import JobsService
from gradeflow_backend.utils.jobs import build_grading_job


class GradingService:
    def __init__(self, repo: AssessmentRepository) -> None:
        self.repo = repo

    # ---------------------------
    # Shared helpers
    # ---------------------------

    def _get_assessment(self, assessment_id: str) -> Assessment:
        try:
            return self.repo.get(assessment_id)
        except NoResultFound as e:
            raise NotFoundError("Assessment not found") from e

    def _load_question_set_yaml(self, yaml_str: str | None) -> QuestionSet:
        if not yaml_str:
            raise NotFoundError("Question set not set")
        return QuestionSet.model_validate(yaml.safe_load(yaml_str))

    def _load_rubric_yaml(self, yaml_str: str | None) -> Rubric:
        if not yaml_str:
            raise NotFoundError("Rubric not set")
        return Rubric.model_validate(yaml.safe_load(yaml_str))

    def _load_raw_submissions_yaml(self, yaml_str: str | None) -> list[RawSubmission]:
        if not yaml_str:
            raise NotFoundError("Submissions not set")
        items: list[dict[str, object]] = yaml.safe_load(yaml_str)
        return [RawSubmission.model_validate(obj) for obj in items]

    def _validate_or_raise(self, rubric: Rubric, qset: QuestionSet) -> None:
        errors = rubric.validate_rubric(qset)
        if errors:
            raise RubricValidationError(errors)

    def _limit_raw_submissions(
        self,
        subs: list[RawSubmission],
        *,
        limit: int | None,
        selection: str,
        seed: int | None,
    ) -> list[RawSubmission]:
        if limit is None:
            return subs
        if limit <= 0:
            raise BadRequestError("limit must be a positive integer")
        if selection == "first":
            ordered = sorted(subs, key=lambda s: s.student_id)
            return ordered[: min(limit, len(ordered))]
        if selection == "random":
            rnd = random.Random(seed)
            subs_copy = list(subs)
            if limit >= len(subs_copy):
                rnd.shuffle(subs_copy)
                return subs_copy
            return rnd.sample(subs_copy, k=limit)
        raise BadRequestError("selection must be 'first' or 'random'")

    def _run(
        self,
        assessment_id: str,
        type: JobType,
        request: Request,
        jobs: JobsService,
        rule: QuestionRule | None = None,
        config: GradingLimitConfig | None = None,
    ) -> GradingJob:
        a = self._get_assessment(assessment_id)
        qset = self._load_question_set_yaml(a.question_set_yaml)
        raw_subs = self._load_raw_submissions_yaml(a.submissions_yaml)

        # If a single rule is provided, build a transient rubric; else use stored
        rubric = Rubric(rules=[rule]) if rule is not None else self._load_rubric_yaml(a.rubric_yaml)

        self._validate_or_raise(rubric, qset)

        if config is not None:
            raw_subs = self._limit_raw_submissions(
                raw_subs,
                limit=config.limit,
                selection=config.selection,
                seed=config.seed,
            )

        spec = GradingJobSpec(
            assessment_id=assessment_id,
            type=type,
            raw_submissions=raw_subs,
            question_set=qset,
            rubric=rubric,
        )
        return jobs.submit(spec, request)

    # ---------------------------
    # Grading job submission
    # ---------------------------

    def run(
        self,
        assessment_id: str,
        req: GradingRunRequest,
        request: Request,
        jobs: JobsService,
    ) -> GradingJob:
        return self._run(
            assessment_id,
            type="run",
            request=request,
            jobs=jobs,
            rule=None,
            config=None,
        )

    def run_preview(
        self,
        assessment_id: str,
        req: GradingPreviewRequest,
        request: Request,
        jobs: JobsService,
    ) -> GradingJob:
        return self._run(
            assessment_id,
            type="preview",
            request=request,
            jobs=jobs,
            rule=req.rule,
            config=req.config,
        )

    # ---------------------------
    # Grading results management
    # ---------------------------

    def get(self, assessment_id: str) -> GradingResponse:
        try:
            graded_yaml = self.repo.get_graded_yaml(assessment_id)
        except NoResultFound as e:
            raise NotFoundError("Assessment not found") from e
        if not graded_yaml:
            return GradingResponse(graded_submissions=[])
        items: list[dict[str, object]] = yaml.safe_load(graded_yaml)
        adjustable = [AdjustableGradedSubmission.model_validate(obj) for obj in items]
        return GradingResponse(graded_submissions=adjustable)

    def get_job(self, assessment_id: str, request: Request) -> GradingJob:
        try:
            job_id = self.repo.get_run_job_id(assessment_id)
        except NoResultFound as e:
            raise NotFoundError("Assessment not found") from e
        if not job_id:
            raise NotFoundError("No job found for this assessment")
        return build_grading_job(request, job_id)

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

        items: list[dict[str, object]] = yaml.safe_load(graded_yaml)
        graded = [AdjustableGradedSubmission.model_validate(obj) for obj in items]

        index: dict[tuple[str, str], AdjustableQuestionResult] = {}
        for gs in graded:
            for res in gs.results:
                index[(gs.student_id, res.question_id)] = res

        for adj in req.adjustments:
            key = (adj.student_id, adj.question_id)
            if key not in index:
                raise BadRequestError(
                    f"No result found: student_id={adj.student_id}, question_id={adj.question_id}"
                )
            target = index[key]
            if adj.adjusted_points is not None:
                new_points = float(adj.adjusted_points)
                if new_points < 0:
                    raise BadRequestError("adjusted_points must be >= 0")
                if new_points > target.max_points:
                    raise BadRequestError(
                        f"adjusted_points ({new_points}) exceeds max_points ({target.max_points})"
                    )
                target.adjusted_points = new_points
            else:
                target.adjusted_points = None
            target.adjusted_feedback = (
                adj.adjusted_feedback if adj.adjusted_feedback is not None else None
            )

        payload = [gs.model_dump() for gs in graded]
        self.repo.set_graded_yaml(assessment_id, yaml.safe_dump(payload))
        return GradingResponse(graded_submissions=graded)

    def export(self, assessment_id: str, req: GradingExportRequest) -> GradingExportResponse:
        a = self._get_assessment(assessment_id)
        graded_yaml = a.graded_submissions_yaml
        if not graded_yaml:
            raise BadRequestError("No graded results to export. Run grading first.")

        items: list[dict[str, object]] = yaml.safe_load(graded_yaml)
        adjustable = [AdjustableGradedSubmission.model_validate(obj) for obj in items]

        exportable: list[GradedSubmission] = []
        for ags in adjustable:
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
            exportable.append(
                GradedSubmission(
                    student_id=ags.student_id, answer_map=ags.answer_map, results=converted_results
                )
            )

        out = save_graded_submissions(
            graded_submissions=exportable,
            saver_name=req.saver_name,
            **(req.submissions_saver_kwargs or {}),
        )

        safe_assessment_name = "".join(
            c if c.isalnum() or c in (" ", "_", "-") else "_" for c in a.name
        ).rstrip()
        filename = f"graded_{safe_assessment_name}.{out.extension}"
        return GradingExportResponse(data=out.data, extension=out.extension, filename=filename)

    def get_preview(self, assessment_id: str) -> GradingResponse:
        try:
            yaml_str = self.repo.get_graded_preview_yaml(assessment_id)
        except NoResultFound as e:
            raise NotFoundError("Assessment not found") from e
        if not yaml_str:
            return GradingResponse(graded_submissions=[])
        items: list[dict[str, object]] = yaml.safe_load(yaml_str)
        adjustable = [AdjustableGradedSubmission.model_validate(obj) for obj in items]
        # Clear after retrieval
        self.repo.set_graded_preview_yaml(assessment_id, None)
        return GradingResponse(graded_submissions=adjustable)

    def get_preview_job(self, assessment_id: str, request: Request) -> GradingJob:
        try:
            job_id = self.repo.get_preview_job_id(assessment_id)
        except NoResultFound as e:
            raise NotFoundError("Assessment not found") from e
        if not job_id:
            raise NotFoundError("No preview job found for this assessment")
        return build_grading_job(request, job_id)
