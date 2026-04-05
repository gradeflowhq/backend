import random

import yaml
from fastapi import Request
from gradeflow_engine.core import (
    dump_submissions_to_blob,
)
from gradeflow_engine.question_sets.model import QuestionSet
from gradeflow_engine.rubrics.model import Rubric
from gradeflow_engine.rules.models import QuestionRule
from gradeflow_engine.rules.result import QuestionResult
from gradeflow_engine.submissions.models import RawSubmission, Submission

from gradeflow_backend.models.assessment import Assessment
from gradeflow_backend.repositories.assessments import AssessmentRepository
from gradeflow_backend.repositories.grading_jobs import GradingJobRepository
from gradeflow_backend.repositories.submissions import SubmissionRepository
from gradeflow_backend.schemas.grading import (
    AdjustableSubmission,
    GradeAdjustmentRequest,
    GradingDownloadRequest,
    GradingDownloadResponse,
    GradingJob,
    GradingJobSpec,
    GradingLimitConfig,
    GradingPreviewRequest,
    GradingResponse,
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
            return sorted(subs, key=lambda s: s.student_id)[:limit]
        if selection == "random":
            rnd = random.Random(seed)
            subs_copy = list(subs)
            if limit >= len(subs_copy):
                rnd.shuffle(subs_copy)
                return subs_copy
            return rnd.sample(subs_copy, k=limit)
        raise BadRequestError("selection must be 'first' or 'random'")

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
            raw_subs = self._limit_raw_submissions(
                raw_subs,
                limit=config.limit,
                selection=config.selection,
                seed=config.seed,
            )

        return jobs.submit(
            GradingJobSpec(
                assessment_id=assessment_id,
                type=type,
                raw_submissions=raw_subs,
                question_set=qset,
                rubric=rubric,
            ),
            request,
        )

    def run(
        self,
        assessment_id: str,
        request: Request,
        jobs: JobsService,
    ) -> GradingJob:
        return self._run(assessment_id, type="run", request=request, jobs=jobs)

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

    def get(self, assessment_id: str) -> GradingResponse:
        return self._grading_response(self._get_or_404(assessment_id))

    def get_job(self, assessment_id: str, type: JobType, request: Request) -> GradingJob:
        job_id = self.grading_jobs.get_job_id(assessment_id, type)
        if not job_id:
            raise NotFoundError("No job found for this assessment")
        return build_grading_job(request, job_id)

    def delete(self, assessment_id: str) -> None:
        self._get_or_404(assessment_id)
        self.submission_repo.delete_by_assessment(assessment_id)

    def adjust(self, assessment_id: str, adj: GradeAdjustmentRequest) -> GradingResponse:
        a = self._get_or_404(assessment_id)
        result = self.submission_repo.get_result(assessment_id, adj.student_id, adj.question_id)
        if result is None:
            raise BadRequestError(
                f"No result found: student_id={adj.student_id}, question_id={adj.question_id}"
            )
        if adj.adjusted_points is not None and adj.adjusted_points > result.max_points:
            raise BadRequestError(
                f"adjusted_points ({adj.adjusted_points}) exceeds max_points ({result.max_points})"
            )
        self.submission_repo.update_result(result, adj.adjusted_points, adj.adjusted_feedback)
        return self._grading_response(a)

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

    def get_preview(self, assessment_id: str) -> GradingResponse:
        a = self._get_or_404(assessment_id)
        yaml_str = self.repo.get_preview_yaml(assessment_id)
        if not yaml_str:
            return GradingResponse(submissions=[], status=results_status(a))
        items: list[dict[str, object]] = yaml.safe_load(yaml_str) or []
        self.repo.set_preview_yaml(assessment_id, None)
        return GradingResponse(
            submissions=[AdjustableSubmission.model_validate(obj) for obj in items],
            status=results_status(a),
        )
