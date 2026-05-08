from typing import Any

from gradeflow_engine.core import (
    dump_question_set_to_blob,
    load_question_set_from_blob,
    load_question_set_via_adapter,
)
from gradeflow_engine.exceptions import GradeFlowError
from gradeflow_engine.io.sources import DataSource
from gradeflow_engine.question_sets.model import QuestionSet
from gradeflow_engine.questions.models import Question
from gradeflow_engine.questions.types import QuestionId
from gradeflow_engine.serializations.base import DataBlob

from gradeflow_backend.models.assessment import Assessment
from gradeflow_backend.schemas.question_sets import (
    ExportQuestionSetRequest,
    ExportQuestionSetResponse,
    ImportQuestionSetRequest,
    InferQuestionSetRequest,
    LoadQuestionSetRequest,
    ParseSubmissionsRequest,
    ParseSubmissionsResponse,
    QuestionCreateRequest,
    QuestionSetResponse,
    QuestionSetStatusResponse,
    QuestionUpdateRequest,
    SetQuestionSetByModelRequest,
)
from gradeflow_backend.services.exceptions import BadRequestError, NotFoundError
from gradeflow_backend.services.submissions import derive_raw_submissions
from gradeflow_backend.services.yaml_artifacts import YamlArtifactService
from gradeflow_backend.utils.filenames import make_safe_export_basename
from gradeflow_backend.utils.loaders import load_question_set
from gradeflow_backend.utils.resolvers import resolve_or_require
from gradeflow_backend.utils.staleness import question_set_status


class QuestionSetService(
    YamlArtifactService[QuestionSet, QuestionSetResponse, ExportQuestionSetResponse]
):
    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_by_model(
        self, assessment_id: str, req: SetQuestionSetByModelRequest
    ) -> QuestionSetResponse:
        return self._set_by_model(assessment_id, req.question_set)

    def set_by_data(self, assessment_id: str, req: LoadQuestionSetRequest) -> QuestionSetResponse:
        return self._set_by_data(assessment_id, req.data, req.serializer)

    def set_by_adapter(
        self, assessment_id: str, req: ImportQuestionSetRequest
    ) -> QuestionSetResponse:
        return self._set_by_adapter(assessment_id, req.data, req.adapter)

    def get(self, assessment_id: str) -> QuestionSetResponse:
        return self._get_response(assessment_id)

    def get_status(self, assessment_id: str) -> QuestionSetStatusResponse:
        assessment = self._get_or_404(assessment_id)
        question_set = self._load_stored_or_empty(assessment)
        raw_submissions = derive_raw_submissions(assessment)
        return QuestionSetStatusResponse(
            status=question_set_status(assessment),
            drift=question_set.get_drift(raw_submissions),
        )

    def sync(self, assessment_id: str) -> QuestionSetResponse:
        assessment = self._get_or_404(assessment_id)
        question_set = self._load_stored_or_empty(assessment)
        synced_question_set = question_set.sync_from_submissions(derive_raw_submissions(assessment))
        return self._store_and_respond(assessment_id, synced_question_set)

    def acknowledge_question_set_staleness(self, assessment_id: str) -> QuestionSetResponse:
        assessment = self._get_or_404(assessment_id)
        question_set = self._load_stored(assessment)
        return self._store_and_respond(assessment_id, question_set)

    def export(
        self, assessment_id: str, req: ExportQuestionSetRequest
    ) -> ExportQuestionSetResponse:
        return self._export_artifact(assessment_id, req.serializer)

    def delete(self, assessment_id: str) -> None:
        self._delete_artifact(assessment_id)

    def get_question(self, assessment_id: str, question_id: QuestionId) -> Question:
        question_set = self._load_stored(self._get_or_404(assessment_id))
        return self._question_or_404(question_set, question_id)

    def create_question(
        self,
        assessment_id: str,
        req: QuestionCreateRequest,
    ) -> QuestionSetResponse:
        assessment = self._get_or_404(assessment_id)
        question_set = self._load_stored_or_empty(assessment)
        if req.question_id in question_set.question_map:
            raise BadRequestError(f"Question {req.question_id} already exists")
        return self._store_and_respond(
            assessment_id,
            QuestionSet(
                question_map={
                    **question_set.question_map,
                    req.question_id: req.question,
                }
            ),
        )

    def update_question(
        self,
        assessment_id: str,
        question_id: QuestionId,
        req: QuestionUpdateRequest,
    ) -> QuestionSetResponse:
        assessment = self._get_or_404(assessment_id)
        question_set = self._load_stored(assessment)
        self._question_or_404(question_set, question_id)
        question_map = dict(question_set.question_map)
        question_map[question_id] = req.question
        return self._store_and_respond(assessment_id, QuestionSet(question_map=question_map))

    def delete_question(self, assessment_id: str, question_id: QuestionId) -> None:
        assessment = self._get_or_404(assessment_id)
        question_set = self._load_stored(assessment)
        self._question_or_404(question_set, question_id)
        question_map = {
            qid: question
            for qid, question in question_set.question_map.items()
            if qid != question_id
        }
        self._store_question_set_yaml(assessment_id, QuestionSet(question_map=question_map))

    def infer(self, assessment_id: str, req: InferQuestionSetRequest) -> QuestionSetResponse:
        a = self._get_or_404(assessment_id)
        raw_submissions = resolve_or_require(
            use_stored=req.use_stored_submissions,
            load=lambda: derive_raw_submissions(a),
            override=req.raw_submissions,
            field_name="raw_submissions",
        )
        question_set = QuestionSet.infer(
            raw_submissions,
            choice_delimiter=req.choice_delimiter,
            choice_option_limit=req.choice_option_limit,
            multi_value_delimiter=req.multi_value_delimiter,
        )
        if req.commit:
            return self._store_and_respond(assessment_id, question_set)
        return QuestionSetResponse(question_set=question_set, status=question_set_status(a))

    def parse(self, assessment_id: str, req: ParseSubmissionsRequest) -> ParseSubmissionsResponse:
        a = self._get_or_404(assessment_id)
        question_set = resolve_or_require(
            use_stored=req.use_stored_question_set,
            load=lambda: load_question_set(a),
            override=req.question_set,
            field_name="question_set",
        )
        raw_submissions = resolve_or_require(
            use_stored=req.use_stored_submissions,
            load=lambda: derive_raw_submissions(a),
            override=req.raw_submissions,
            field_name="raw_submissions",
        )
        try:
            return ParseSubmissionsResponse(submissions=question_set.parse(raw_submissions))
        except GradeFlowError as e:
            raise BadRequestError(f"Failed to parse submissions: {e}") from e

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load_from_blob(
        self,
        blob: DataBlob,
        *,
        serializer_name: str,
        serializer_kwargs: dict[str, Any] | None = None,
    ) -> QuestionSet:
        return load_question_set_from_blob(
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
    ) -> QuestionSet:
        return load_question_set_via_adapter(
            source,
            adapter_name=adapter_name,
            adapter_kwargs=adapter_kwargs,
        )

    def _load_stored(self, assessment: Assessment) -> QuestionSet:
        return load_question_set(assessment)

    def _load_stored_or_empty(self, assessment: Assessment) -> QuestionSet:
        if not assessment.question_set_yaml:
            return QuestionSet(question_map={})
        return self._load_stored(assessment)

    def _question_or_404(self, question_set: QuestionSet, question_id: QuestionId) -> Question:
        question = question_set.question_map.get(question_id)
        if question is None:
            raise NotFoundError(f"Question {question_id} not found")
        return question

    def _dump_to_blob(
        self,
        artifact: QuestionSet,
        *,
        serializer_name: str,
        serializer_kwargs: dict[str, Any] | None = None,
    ) -> DataBlob:
        return dump_question_set_to_blob(
            artifact,
            serializer_name=serializer_name,
            serializer_kwargs=serializer_kwargs,
        )

    def _store_yaml(self, assessment_id: str, yaml_str: str | None) -> None:
        self.repo.set_question_set_yaml(assessment_id, yaml_str)

    def _store_question_set_yaml(self, assessment_id: str, question_set: QuestionSet) -> None:
        blob = self._dump_to_blob(question_set, serializer_name="yaml")
        self._store_yaml(assessment_id, blob.data.decode("utf-8"))

    def _build_response(self, assessment: Assessment, artifact: QuestionSet) -> QuestionSetResponse:
        return QuestionSetResponse(
            question_set=artifact,
            status=question_set_status(assessment),
        )

    def _build_export_response(
        self,
        assessment: Assessment,
        blob: DataBlob,
    ) -> ExportQuestionSetResponse:
        safe_name = make_safe_export_basename(assessment.name)
        return ExportQuestionSetResponse(
            filename=f"{safe_name}-questions.{blob.extension}",
            data=blob.data,
            extension=blob.extension,
            media_type=blob.media_type,
        )
