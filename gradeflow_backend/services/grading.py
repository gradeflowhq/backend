import random
from collections.abc import Sequence
from dataclasses import dataclass

import yaml
from gradeflow_engine.core import save_graded_submissions
from gradeflow_engine.question_sets.model import QuestionSet
from gradeflow_engine.rubrics.model import Rubric
from gradeflow_engine.rules.models import QuestionRule
from gradeflow_engine.rules.result import QuestionResult
from gradeflow_engine.submissions.models import GradedSubmission, RawSubmission, Submission
from sqlalchemy.exc import NoResultFound

from gradeflow_backend.models.assessment import Assessment
from gradeflow_backend.repositories.assessments import AssessmentRepository
from gradeflow_backend.schemas.grading import (
    AdjustableGradedSubmission,
    AdjustableQuestionResult,
    GradeAdjustmentRequest,
    GradingExportRequest,
    GradingExportResponse,
    GradingPreviewRequest,
    GradingResponse,
    GradingRunRequest,
)
from gradeflow_backend.services.exceptions import (
    BadRequestError,
    NotFoundError,
    RubricValidationError,
)


@dataclass(frozen=True)
class ParsedBundle:
    qset: QuestionSet
    submissions: list[Submission]


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

    def _resolve_question_set(
        self, *, stored_yaml: str | None, provided: QuestionSet | None, use_stored: bool
    ) -> QuestionSet:
        if use_stored:
            return self._load_question_set_yaml(stored_yaml)
        if provided is None:
            raise BadRequestError(
                "question_set must be provided when use_stored_question_set=false"
            )
        return provided

    def _resolve_rubric(
        self, *, stored_yaml: str | None, provided: Rubric | None, use_stored: bool
    ) -> Rubric:
        if use_stored:
            return self._load_rubric_yaml(stored_yaml)
        if provided is None:
            raise BadRequestError("rubric must be provided when use_stored_rubric=false")
        return provided

    def _resolve_raw_submissions(
        self, *, stored_yaml: str | None, provided: list[RawSubmission] | None, use_stored: bool
    ) -> list[RawSubmission]:
        if use_stored:
            return self._load_raw_submissions_yaml(stored_yaml)
        if provided is None:
            raise BadRequestError(
                "raw_submissions must be provided when use_stored_submissions=false"
            )
        return provided

    def _validate_or_raise(self, rubric: Rubric, qset: QuestionSet) -> None:
        errors = rubric.validate_rubric(qset)
        if errors:
            raise RubricValidationError(errors)

    def _limit_raw_submissions(
        self, subs: list[RawSubmission], *, limit: int | None, selection: str, seed: int | None
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
            if limit >= len(subs):
                rnd.shuffle(subs)
                return subs
            return rnd.sample(subs, k=limit)
        raise BadRequestError("selection must be 'first' or 'random'")

    def _parse_bundle(self, qset: QuestionSet, raw_subs: Sequence[RawSubmission]) -> ParsedBundle:
        submissions = qset.parse(list(raw_subs))
        return ParsedBundle(qset=qset, submissions=submissions)

    def _grade_adjustable(
        self, rubric: Rubric, bundle: ParsedBundle
    ) -> list[AdjustableGradedSubmission]:
        graded = rubric.grade(bundle.submissions)
        return [
            AdjustableGradedSubmission(
                student_id=gs.student_id,
                answer_map=gs.answer_map,
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

    def _filter_results_to_targets(
        self,
        adjustable: list[AdjustableGradedSubmission],
        target_ids: set[str],
        *,
        drop_empty_submissions: bool = True,
    ) -> list[AdjustableGradedSubmission]:
        filtered: list[AdjustableGradedSubmission] = []
        for gs in adjustable:
            kept = [r for r in gs.results if r.question_id in target_ids]
            if drop_empty_submissions and not kept:
                continue
            filtered.append(
                AdjustableGradedSubmission(
                    student_id=gs.student_id,
                    answer_map=gs.answer_map,
                    results=kept,
                )
            )
        return filtered

    def _persist_graded_yaml(
        self, assessment_id: str, adjustable: list[AdjustableGradedSubmission]
    ) -> None:
        payload = [gs.model_dump() for gs in adjustable]
        self.repo.set_graded_yaml(assessment_id, yaml.safe_dump(payload))

    # ---------------------------
    # Single internal pipeline (used by both run and preview)
    # ---------------------------

    def _grade_pipeline(
        self,
        *,
        assessment_id: str,
        # Artifact sources
        use_stored_qset: bool,
        qset_provided: QuestionSet | None,
        use_stored_rubric: bool,
        rubric_provided: Rubric | None,
        use_stored_subs: bool,
        subs_provided: list[RawSubmission] | None,
        # Preview/run controls
        limit: int | None = None,
        selection: str = "first",
        seed: int | None = None,
        single_rule: QuestionRule | None = None,
        filter_to_target_ids: bool = False,
        persist_results: bool = False,
    ) -> list[AdjustableGradedSubmission]:
        a = self._get_assessment(assessment_id)

        qset = self._resolve_question_set(
            stored_yaml=a.question_set_yaml, provided=qset_provided, use_stored=use_stored_qset
        )
        raw_subs_all = self._resolve_raw_submissions(
            stored_yaml=a.submissions_yaml, provided=subs_provided, use_stored=use_stored_subs
        )
        raw_subs = self._limit_raw_submissions(
            raw_subs_all, limit=limit, selection=selection, seed=seed
        )

        rubric = (
            Rubric(rules=[single_rule])
            if single_rule is not None
            else self._resolve_rubric(
                stored_yaml=a.rubric_yaml, provided=rubric_provided, use_stored=use_stored_rubric
            )
        )

        self._validate_or_raise(rubric, qset)
        bundle = self._parse_bundle(qset, raw_subs)
        adjustable = self._grade_adjustable(rubric, bundle)

        if single_rule is not None and filter_to_target_ids:
            target_ids = single_rule.get_target_question_ids()
            adjustable = self._filter_results_to_targets(
                adjustable, target_ids, drop_empty_submissions=True
            )

        if persist_results:
            self._persist_graded_yaml(assessment_id, adjustable)

        return adjustable

    # ---------------------------
    # Public methods (thin wrappers)
    # ---------------------------

    def run(self, assessment_id: str, req: GradingRunRequest) -> GradingResponse:
        adjustable = self._grade_pipeline(
            assessment_id=assessment_id,
            use_stored_qset=True,
            qset_provided=None,
            use_stored_rubric=True,
            rubric_provided=None,
            use_stored_subs=True,
            subs_provided=None,
            persist_results=True,  # run persists
        )
        return GradingResponse(graded_submissions=adjustable)

    def preview(self, assessment_id: str, req: GradingPreviewRequest) -> GradingResponse:
        adjustable = self._grade_pipeline(
            assessment_id=assessment_id,
            use_stored_qset=req.use_stored_question_set,
            qset_provided=req.question_set,
            use_stored_rubric=req.use_stored_rubric,
            rubric_provided=req.rubric,
            use_stored_subs=req.use_stored_submissions,
            subs_provided=req.raw_submissions,
            limit=req.limit,
            selection=req.selection,
            seed=req.seed,
            single_rule=req.rule,  # only rule-focused if provided
            filter_to_target_ids=req.rule is not None,
            persist_results=False,  # preview never persists
        )
        return GradingResponse(graded_submissions=adjustable)

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
