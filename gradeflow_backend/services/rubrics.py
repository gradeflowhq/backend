from typing import Any

from gradeflow_engine.core import (
    dump_rubric_to_blob,
    load_rubric_from_blob,
    load_rubric_via_adapter,
)
from gradeflow_engine.exceptions import RubricValidationError as EngineRubricValidationError
from gradeflow_engine.io.sources import DataSource
from gradeflow_engine.rubrics.model import Rubric
from gradeflow_engine.rules.models import QuestionRule
from gradeflow_engine.rules.models.base import new_rule_id
from gradeflow_engine.serializations.base import DataBlob

from gradeflow_backend.models.assessment import Assessment
from gradeflow_backend.schemas.rubrics import (
    ExportRubricRequest,
    ExportRubricResponse,
    ImportRubricRequest,
    LoadRubricRequest,
    RubricOverviewResponse,
    RubricResponse,
    RuleCreateRequest,
    RulesResponse,
    RuleUpdateRequest,
    SetRubricByModelRequest,
    ValidateRubricRequest,
    ValidateRubricResponse,
)
from gradeflow_backend.schemas.rules import (
    CompatibleRulesResponse,
    RuleSchemaResponse,
)
from gradeflow_backend.services.exceptions import (
    BadRequestError,
    NotFoundError,
    RubricValidationError,
)
from gradeflow_backend.services.rule_schemas import (
    build_rule_schema,
    list_compatible_rules,
)
from gradeflow_backend.services.submissions import derive_raw_submissions
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

    def list_rules(self, assessment_id: str) -> RulesResponse:
        assessment = self._get_or_404(assessment_id)
        rubric = self._load_stored_or_empty(assessment, strict=False)
        return RulesResponse(
            rules=rubric.rules,
            status=rubric_status(assessment),
        )

    def get_rule(self, assessment_id: str, rule_id: str) -> QuestionRule:
        rubric = self._load_stored(self._get_or_404(assessment_id), strict=False)
        index = self._rule_index(rule_id, rubric)
        return rubric.rules[index]

    def list_compatible_rules(
        self,
        assessment_id: str,
        *,
        question_id: str | None = None,
        path: str | None = None,
    ) -> CompatibleRulesResponse:
        assessment = self._get_or_404(assessment_id)
        question_set = load_question_set(assessment)
        return list_compatible_rules(question_set, question_id=question_id, path=path)

    def get_rule_schema(
        self,
        assessment_id: str,
        *,
        rule_type: str,
        question_id: str | None = None,
        path: str | None = None,
    ) -> RuleSchemaResponse:
        assessment = self._get_or_404(assessment_id)
        question_set = load_question_set(assessment)
        submissions = (
            question_set.parse(derive_raw_submissions(assessment)) if assessment.source_data else []
        )
        return build_rule_schema(
            question_set,
            rule_type=rule_type,
            question_id=question_id,
            path=path,
            submissions=submissions,
        )

    def create_rule(self, assessment_id: str, req: RuleCreateRequest) -> RubricResponse:
        assessment = self._get_or_404(assessment_id)
        rubric = self._load_stored_or_empty(assessment)
        rule = req.rule.model_copy(update={"id": new_rule_id()})
        next_rubric = Rubric(rules=[*rubric.rules, rule])
        self._validate_or_raise(assessment, next_rubric)
        return self._store_and_respond(assessment_id, next_rubric)

    def update_rule(
        self,
        assessment_id: str,
        rule_id: str,
        req: RuleUpdateRequest,
    ) -> RubricResponse:
        assessment = self._get_or_404(assessment_id)
        rubric = self._load_stored(assessment)
        index = self._rule_index(rule_id, rubric)
        if req.rule.id != rule_id:
            raise BadRequestError("Rule id in request body must match path rule id")
        rules = list(rubric.rules)
        rules[index] = req.rule
        next_rubric = Rubric(rules=rules)
        self._validate_or_raise(assessment, next_rubric)
        return self._store_and_respond(assessment_id, next_rubric)

    def delete_rule(self, assessment_id: str, rule_id: str) -> None:
        assessment = self._get_or_404(assessment_id)
        rubric = self._load_stored(assessment)
        index = self._rule_index(rule_id, rubric)
        rules = [rule for i, rule in enumerate(rubric.rules) if i != index]
        self._store_rubric_yaml(assessment_id, Rubric(rules=rules))

    def acknowledge_rubric_staleness(self, assessment_id: str) -> RubricResponse:
        assessment = self._get_or_404(assessment_id)
        rubric = self._load_stored(assessment)
        return self._store_and_respond(assessment_id, rubric)

    def create_empty_rubric(self, assessment_id: str) -> RubricResponse:
        assessment = self._get_or_404(assessment_id)
        if assessment.rubric_yaml:
            raise BadRequestError("Rubric already set")
        return self._store_and_respond(assessment_id, Rubric(rules=[]))

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

    def sync_stale_rules(self, assessment_id: str) -> RubricResponse:
        assessment = self._get_or_404(assessment_id)
        rubric = self._load_stored(assessment)
        question_set = load_question_set(assessment)
        return self._store_and_respond(assessment_id, rubric.remove_stale_rules(question_set))

    def repair(self, assessment_id: str) -> RubricResponse:
        assessment = self._get_or_404(assessment_id)
        rubric = self._load_stored(assessment, strict=False)
        return self._store_and_respond(assessment_id, rubric)

    def overview(self, assessment_id: str) -> RubricOverviewResponse:
        assessment = self._get_or_404(assessment_id)
        if not assessment.rubric_yaml:
            raise NotFoundError("Rubric not set")
        question_set = load_question_set(assessment)
        try:
            rubric = self._load_stored(assessment)
            validation_errors: list[str] = []
        except EngineRubricValidationError as e:
            rubric = self._load_stored(assessment, strict=False)
            validation_errors = e.messages
        return RubricOverviewResponse(
            question_rules=[rule for rule in rubric.rules if rule.scope == "question"],
            global_rules=[rule for rule in rubric.rules if rule.scope == "global"],
            coverage=rubric.get_coverage(question_set),
            stale_rules=rubric.get_stale_rule_references(question_set),
            status=rubric_status(assessment),
            validation_errors=validation_errors,
        )

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

    def _load_stored(self, assessment: Assessment, *, strict: bool = True) -> Rubric:
        return load_rubric(assessment, strict=strict)

    def _load_stored_or_empty(self, assessment: Assessment, *, strict: bool = True) -> Rubric:
        if not assessment.rubric_yaml:
            return Rubric(rules=[])
        return self._load_stored(assessment, strict=strict)

    def _validate_or_raise(self, assessment: Assessment, rubric: Rubric) -> None:
        errors = rubric.validate_rubric(load_question_set(assessment))
        if errors:
            raise RubricValidationError(errors)

    def _rule_index(self, rule_id: str, rubric: Rubric) -> int:
        for index, rule in enumerate(rubric.rules):
            if rule.id == rule_id:
                return index
        raise NotFoundError(f"Rule {rule_id} not found")

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

    def _store_rubric_yaml(self, assessment_id: str, rubric: Rubric) -> None:
        blob = self._dump_to_blob(rubric, serializer_name="yaml")
        self._store_yaml(assessment_id, blob.data.decode("utf-8"))

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
