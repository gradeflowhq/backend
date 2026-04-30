from typing import Any

from gradeflow_engine.core import (
    dump_rubric_to_blob,
    load_rubric_from_blob,
    load_rubric_via_adapter,
)
from gradeflow_engine.io.sources import DataSource
from gradeflow_engine.rubrics.model import Rubric
from gradeflow_engine.serializations.base import DataBlob

from gradeflow_backend.models.assessment import Assessment
from gradeflow_backend.schemas.rubrics import (
    CoverageRequest,
    CoverageResponse,
    ExportRubricRequest,
    ExportRubricResponse,
    ImportRubricRequest,
    LoadRubricRequest,
    RubricResponse,
    SetRubricByModelRequest,
    ValidateRubricRequest,
    ValidateRubricResponse,
)
from gradeflow_backend.services.yaml_artifacts import YamlArtifactService
from gradeflow_backend.utils.filenames import make_safe_export_basename
from gradeflow_backend.utils.loaders import load_question_set, load_rubric
from gradeflow_backend.utils.resolvers import resolve_or_require
from gradeflow_backend.utils.staleness import rubric_status


class RubricService(YamlArtifactService[Rubric, RubricResponse, ExportRubricResponse]):
    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_by_model(self, assessment_id: str, req: SetRubricByModelRequest) -> RubricResponse:
        return self._set_by_model(assessment_id, req.rubric)

    def set_by_data(self, assessment_id: str, req: LoadRubricRequest) -> RubricResponse:
        return self._set_by_data(assessment_id, req.data, req.serializer)

    def set_by_adapter(self, assessment_id: str, req: ImportRubricRequest) -> RubricResponse:
        return self._set_by_adapter(assessment_id, req.data, req.adapter)

    def get(self, assessment_id: str) -> RubricResponse:
        return self._get_response(assessment_id)

    def export(self, assessment_id: str, req: ExportRubricRequest) -> ExportRubricResponse:
        return self._export_artifact(assessment_id, req.serializer)

    def delete(self, assessment_id: str) -> None:
        self._delete_artifact(assessment_id)

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

    def _load_from_blob(
        self,
        blob: DataBlob,
        *,
        serializer_name: str,
        serializer_kwargs: dict[str, Any] | None = None,
    ) -> Rubric:
        return load_rubric_from_blob(
            blob,
            serializer_name=serializer_name,
            serializer_kwargs=serializer_kwargs,
        )

    def _load_via_adapter(
        self,
        source: DataSource,
        *,
        adapter_name: str,
        adapter_kwargs: dict[str, Any] | None = None,
    ) -> Rubric:
        return load_rubric_via_adapter(
            source,
            adapter_name=adapter_name,
            adapter_kwargs=adapter_kwargs,
        )

    def _load_stored(self, assessment: Assessment) -> Rubric:
        return load_rubric(assessment)

    def _dump_to_blob(
        self,
        artifact: Rubric,
        *,
        serializer_name: str,
        serializer_kwargs: dict[str, Any] | None = None,
    ) -> DataBlob:
        return dump_rubric_to_blob(
            artifact,
            serializer_name=serializer_name,
            serializer_kwargs=serializer_kwargs,
        )

    def _store_yaml(self, assessment_id: str, yaml_str: str | None) -> None:
        self.repo.set_rubric_yaml(assessment_id, yaml_str)

    def _build_response(self, assessment: Assessment, artifact: Rubric) -> RubricResponse:
        return RubricResponse(rubric=artifact, status=rubric_status(assessment))

    def _build_export_response(
        self,
        assessment: Assessment,
        blob: DataBlob,
    ) -> ExportRubricResponse:
        safe_name = make_safe_export_basename(assessment.name)
        return ExportRubricResponse(
            filename=f"{safe_name}-rules.{blob.extension}",
            data=blob.data,
            extension=blob.extension,
            media_type=blob.media_type,
        )
