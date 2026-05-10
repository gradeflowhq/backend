import random
from typing import Any
from typing import cast as type_cast

import yaml
from fastapi import Request
from gradeflow_engine.core import (
    dump_submissions_to_blob,
)
from gradeflow_engine.question_sets.model import QuestionSet
from gradeflow_engine.questions.types import QuestionId
from gradeflow_engine.rubrics.model import Rubric
from gradeflow_engine.rules.models import QuestionRule
from gradeflow_engine.rules.result import QuestionResult
from gradeflow_engine.submissions.models import RawSubmission, Submission
from natsort import natsorted

from gradeflow_backend.config import get_settings
from gradeflow_backend.models.assessment import Assessment
from gradeflow_backend.models.submission import SubmissionResult
from gradeflow_backend.repositories.assessments import AssessmentRepository
from gradeflow_backend.repositories.grading_jobs import GradingJobRepository
from gradeflow_backend.repositories.submissions import SubmissionRepository
from gradeflow_backend.schemas.grading import (
    AdjustableSubmission,
    BulkGradeAdjustmentRequest,
    BulkGradeAdjustmentResponse,
    GradeAdjustmentRequest,
    GradingDownloadRequest,
    GradingDownloadResponse,
    GradingJob,
    GradingJobSpec,
    GradingLimitConfig,
    GradingPreviewRequest,
    GradingPreviewResponse,
    GradingPreviewResult,
    GradingResponse,
    GradingRunRequest,
    JobType,
)
from gradeflow_backend.services.base import BaseService
from gradeflow_backend.services.exceptions import (
    BadRequestError,
    NotFoundError,
    RubricValidationError,
)
from gradeflow_backend.services.jobs import JobsService
from gradeflow_backend.services.submissions import derive_raw_submissions
from gradeflow_backend.utils.jobs import build_grading_job
from gradeflow_backend.utils.loaders import load_question_set, load_rubric
from gradeflow_backend.utils.staleness import results_status


class GradingService(BaseService):
    def __init__(
        self,
        repo: AssessmentRepository,
        grading_jobs: GradingJobRepository,
        submission_repo: SubmissionRepository,
    ) -> None:
        super().__init__(repo)
        self.grading_jobs = grading_jobs
        self.submission_repo = submission_repo

    def _validate_or_raise(self, rubric: Rubric, qset: QuestionSet) -> None:
        errors = rubric.validate_rubric(qset)
        if errors:
            raise RubricValidationError(errors)

    @staticmethod
    def _random_raw_submissions(
        subs: list[RawSubmission],
        *,
        limit: int,
        seed: int | None,
    ) -> list[RawSubmission]:
        rnd = random.Random(seed)
        subs_copy = list(subs)
        if limit >= len(subs_copy):
            rnd.shuffle(subs_copy)
            return subs_copy
        return rnd.sample(subs_copy, k=limit)

    def _select_raw_submissions(
        self,
        subs: list[RawSubmission],
        *,
        rubric: Rubric,
        limit: int | None,
        selection: str,
        seed: int | None,
    ) -> list[RawSubmission]:
        if limit is None:
            return subs
        if limit <= 0:
            raise BadRequestError("limit must be a positive integer")
        if selection == "first":
            return sorted(subs, key=lambda s: s.student_id)[:limit]
        if selection == "random":
            return self._random_raw_submissions(subs, limit=limit, seed=seed)
        if selection == "random_unique":
            question_ids = list(natsorted(rubric.get_referenced_question_ids()))
            if not question_ids:
                return self._random_raw_submissions(subs, limit=limit, seed=seed)

            unique_subs_by_answer: dict[tuple[str, ...], RawSubmission] = {}
            for sub in sorted(subs, key=lambda s: s.student_id):
                answer_key = tuple(sub.raw_answer_map.get(qid, "") for qid in question_ids)
                unique_subs_by_answer.setdefault(answer_key, sub)

            return self._random_raw_submissions(
                list(unique_subs_by_answer.values()),
                limit=limit,
                seed=seed,
            )
        raise BadRequestError("selection must be 'first', 'random', or 'random_unique'")

    def _grading_response(self, a: Assessment) -> GradingResponse:
        rows = self.submission_repo.list_by_assessment(a.id)
        return GradingResponse(
            submissions=[SubmissionRepository.to_adjustable_submission(r) for r in rows],
            status=results_status(a),
        )

    def _run(
        self,
        assessment_id: str,
        type: JobType,
        request: Request,
        jobs: JobsService,
        rule: QuestionRule | None = None,
        config: GradingLimitConfig | None = None,
        remove_adjustments: bool = False,
        override_results: bool = True,
        grade_questions_without_rule: bool = True,
    ) -> GradingJob:
        a = self._get_or_404(assessment_id)
        qset = load_question_set(a)
        raw_subs = derive_raw_submissions(a)

        if rule is not None:
            rubric = Rubric(rules=[rule])
            raw_subs = [s.model_copy(update={"result_map": {}}) for s in raw_subs]
        else:
            rubric = load_rubric(a)

        self._validate_or_raise(rubric, qset)

        if config is not None:
            raw_subs = self._select_raw_submissions(
                raw_subs,
                rubric=rubric,
                limit=config.limit,
                selection=config.selection,
                seed=config.seed,
            )

        grading_settings = get_settings().grading
        metadata: dict[str, Any] = {}
        if type == "preview":
            metadata["answer_question_ids"] = list(natsorted(rubric.get_referenced_question_ids()))
            metadata["result_question_ids"] = list(natsorted(rubric.get_target_question_ids()))

        return jobs.submit(
            GradingJobSpec(
                assessment_id=assessment_id,
                type=type,
                raw_submissions=raw_subs,
                question_set=qset,
                rubric=rubric,
                remove_adjustments=remove_adjustments,
                override_results=override_results,
                grade_questions_without_rule=grade_questions_without_rule,
                rubric_grading_parallel_jobs=grading_settings.rubric_grading_parallel_jobs,
                rubric_grading_parallel_mode=grading_settings.rubric_grading_parallel_mode,
                metadata=metadata,
            ),
            request,
        )

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
            remove_adjustments=req.remove_adjustments,
            override_results=req.override_results,
            grade_questions_without_rule=True,
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
            override_results=True,
            grade_questions_without_rule=False,
        )

    def get(self, assessment_id: str) -> GradingResponse:
        return self._grading_response(self._get_or_404(assessment_id))

    def get_job(self, assessment_id: str, type: JobType, request: Request) -> GradingJob:
        record = self.grading_jobs.get_latest(assessment_id, type)
        if record is None:
            raise NotFoundError("No job found for this assessment")
        return build_grading_job(
            request,
            record,
            estimated_duration_seconds=self.grading_jobs.estimate_duration_seconds(
                record.assessment_id,
                type_cast(JobType, record.type),
            ),
        )

    def cancel_job(self, assessment_id: str, type: JobType, jobs: JobsService) -> None:
        record = self.grading_jobs.get_latest(assessment_id, type)
        if record is None:
            raise NotFoundError("No job found for this assessment")
        jobs.cancel_job(record.job_id)

    def delete(self, assessment_id: str) -> None:
        self._get_or_404(assessment_id)
        self.submission_repo.delete_by_assessment(assessment_id)

    @staticmethod
    def _validate_adjustment_points(
        adjusted_points: float | None, max_points: float, student_id: str, question_id: str
    ) -> str | None:
        """Return an error string if the adjustment is invalid, else None."""
        if adjusted_points is not None and adjusted_points > max_points:
            return (
                f"adjusted_points ({adjusted_points}) exceeds max_points ({max_points}) "
                f"for student_id={student_id}, question_id={question_id}"
            )
        return None

    def adjust(self, assessment_id: str, adj: GradeAdjustmentRequest) -> GradingResponse:
        a = self._get_or_404(assessment_id)
        result = self.submission_repo.get_result(assessment_id, adj.student_id, adj.question_id)
        if result is None:
            raise BadRequestError(
                f"No result found: student_id={adj.student_id}, question_id={adj.question_id}"
            )
        err = self._validate_adjustment_points(
            adj.adjusted_points, result.max_points, adj.student_id, adj.question_id
        )
        if err:
            raise BadRequestError(err)
        self.submission_repo.update_result(result, adj.adjusted_points, adj.adjusted_feedback)
        return self._grading_response(a)

    def bulk_adjust(
        self, assessment_id: str, req: BulkGradeAdjustmentRequest
    ) -> BulkGradeAdjustmentResponse:
        a = self._get_or_404(assessment_id)
        errors: list[str] = []

        # Fetch all required results in a single query.
        pairs = [(adj.student_id, adj.question_id) for adj in req.adjustments]
        result_map = self.submission_repo.bulk_get_results(assessment_id, pairs)

        # Validate and stage adjustments in memory.
        updates: list[tuple[SubmissionResult, float | None, str | None]] = []
        for adj in req.adjustments:
            key = (adj.student_id, adj.question_id)
            result = result_map.get(key)
            if result is None:
                errors.append(
                    f"No result: student_id={adj.student_id}, question_id={adj.question_id}"
                )
                continue
            err = self._validate_adjustment_points(
                adj.adjusted_points, result.max_points, adj.student_id, adj.question_id
            )
            if err:
                errors.append(err)
                continue
            updates.append((result, adj.adjusted_points, adj.adjusted_feedback))

        # Apply all valid adjustments and flush once.
        for result, adjusted_points, adjusted_feedback in updates:
            result.adjusted_points = adjusted_points
            result.adjusted_feedback = adjusted_feedback
            result.graded = True
        if updates:
            self.submission_repo.session().flush()

        return BulkGradeAdjustmentResponse(
            applied=len(updates),
            errors=errors,
            result=self._grading_response(a),
        )

    def download(self, assessment_id: str, req: GradingDownloadRequest) -> GradingDownloadResponse:
        a = self._get_or_404(assessment_id)
        rows = self.submission_repo.list_by_assessment(assessment_id)
        if not rows:
            raise BadRequestError("No graded results to download. Run grading first.")

        def _to_submission(ags: AdjustableSubmission) -> Submission:
            return Submission(
                student_id=ags.student_id,
                answer_map=ags.answer_map,
                result_map={
                    qid: QuestionResult(
                        output=r.output,
                        passed=r.passed,
                        feedback=r.adjusted_feedback
                        if r.adjusted_feedback is not None
                        else r.feedback,
                        rule=r.rule,
                        points=r.adjusted_points if r.adjusted_points is not None else r.points,
                        max_points=r.max_points,
                    )
                    for qid, r in ags.result_map.items()
                },
            )

        downloadable = [
            _to_submission(SubmissionRepository.to_adjustable_submission(r)) for r in rows
        ]
        out = dump_submissions_to_blob(
            downloadable,
            serializer_name=req.serializer.format,
            serializer_kwargs=req.serializer.model_dump(exclude={"format"}),
        )
        safe_name = "".join(
            c if c.isalnum() or c in (" ", "_", "-") else "_" for c in a.name
        ).rstrip()
        return GradingDownloadResponse(
            filename=f"graded_{safe_name}.{out.extension}",
            data=out.data,
            extension=out.extension,
            media_type=out.media_type,
        )

    def get_preview(self, assessment_id: str) -> GradingPreviewResponse:
        a = self._get_or_404(assessment_id)
        yaml_str = self.repo.get_preview_yaml(assessment_id)
        if not yaml_str:
            return GradingPreviewResponse(submissions=[], status=results_status(a))
        data: dict[str, Any] = yaml.safe_load(yaml_str) or {}
        self.repo.set_preview_yaml(assessment_id, None)

        preview_result = GradingPreviewResult.model_validate(data)
        answer_question_ids = type_cast(
            list[QuestionId], preview_result.metadata["answer_question_ids"]
        )
        result_question_ids = type_cast(
            list[QuestionId], preview_result.metadata["result_question_ids"]
        )
        items: list[dict[str, Any]] = []
        for submission in preview_result.submissions:
            item = submission.model_dump()
            answer_map = item["answer_map"]
            result_map = item["result_map"]
            item["answer_map"] = {
                qid: answer_map[qid] for qid in answer_question_ids if qid in answer_map
            }
            item["result_map"] = {
                qid: result_map[qid] for qid in result_question_ids if qid in result_map
            }
            items.append(item)

        return GradingPreviewResponse(
            submissions=[AdjustableSubmission.model_validate(obj) for obj in items],
            status=results_status(a),
            answer_question_ids=answer_question_ids,
            result_question_ids=result_question_ids,
        )
