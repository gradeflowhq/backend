import yaml
from gradeflow_engine.core import load_rubric_from_blob, load_rubric_via_adapter
from gradeflow_engine.rubrics.model import Rubric

from gradeflow_backend.models.assessment import Assessment
from gradeflow_backend.repositories.assessments import AssessmentRepository
from gradeflow_backend.schemas.rubrics import (
    CoverageRequest,
    CoverageResponse,
    ImportRubricRequest,
    LoadRubricRequest,
    RubricResponse,
    SetRubricByModelRequest,
    ValidateRubricRequest,
    ValidateRubricResponse,
)
from gradeflow_backend.services.base import BaseService
from gradeflow_backend.utils.engine import model_dump_minimal
from gradeflow_backend.utils.io import blob_from_str, source_from_data
from gradeflow_backend.utils.loaders import load_question_set, load_rubric
from gradeflow_backend.utils.resolvers import resolve_or_require
from gradeflow_backend.utils.staleness import rubric_status


class RubricService(BaseService):
    def __init__(self, repo: AssessmentRepository) -> None:
        super().__init__(repo)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_by_model(self, assessment_id: str, req: SetRubricByModelRequest) -> RubricResponse:
        self._get_or_404(assessment_id)
        return self._store_and_respond(assessment_id, req.rubric)

    def set_by_data(self, assessment_id: str, req: LoadRubricRequest) -> RubricResponse:
        rubric = load_rubric_from_blob(
            blob_from_str(
                req.data,
                media_type="application/octet-stream",
                ext=req.serializer.format,
            ),
            serializer_name=req.serializer.format,
            serializer_kwargs=req.serializer.model_dump(exclude={"format"}),
        )
        return self._store_and_respond(assessment_id, rubric)

    def set_by_adapter(self, assessment_id: str, req: ImportRubricRequest) -> RubricResponse:
        rubric = load_rubric_via_adapter(
            source_from_data(req.data),
            adapter_name=req.adapter.name,
            adapter_kwargs=req.adapter.model_dump(exclude={"name"}),
        )
        return self._store_and_respond(assessment_id, rubric)

    def get(self, assessment_id: str) -> RubricResponse:
        a = self._get_or_404(assessment_id)
        return self._respond(a, load_rubric(a))

    def delete(self, assessment_id: str) -> None:
        self._get_or_404(assessment_id)
        self.repo.set_rubric_yaml(assessment_id, None)

    def validate(self, assessment_id: str, req: ValidateRubricRequest) -> ValidateRubricResponse:
        a = self._get_or_404(assessment_id)
        rubric = resolve_or_require(
            use_stored=req.use_stored_rubric,
            load=lambda: load_rubric(a),
            override=req.rubric,
            field_name="rubric",
        )
        question_set = resolve_or_require(
            use_stored=req.use_stored_question_set,
            load=lambda: load_question_set(a),
            override=req.question_set,
            field_name="question_set",
        )
        return ValidateRubricResponse(errors=rubric.validate_rubric(question_set))

    def coverage(self, assessment_id: str, req: CoverageRequest) -> CoverageResponse:
        a = self._get_or_404(assessment_id)
        rubric = resolve_or_require(
            use_stored=req.use_stored_rubric,
            load=lambda: load_rubric(a),
            override=req.rubric,
            field_name="rubric",
        )
        question_set = resolve_or_require(
            use_stored=req.use_stored_question_set,
            load=lambda: load_question_set(a),
            override=req.question_set,
            field_name="question_set",
        )
        return CoverageResponse(coverage=rubric.get_coverage(question_set))

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _store_and_respond(self, assessment_id: str, rubric: Rubric) -> RubricResponse:
        self.repo.set_rubric_yaml(assessment_id, yaml.safe_dump(model_dump_minimal(rubric)))
        return self._respond(self._get_or_404(assessment_id), rubric)

    def _respond(self, a: Assessment, rubric: Rubric) -> RubricResponse:
        return RubricResponse(rubric=rubric, status=rubric_status(a))
