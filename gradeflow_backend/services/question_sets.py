from gradeflow_engine.core import (
    dump_question_set_to_blob,
    load_question_set_from_blob,
    load_question_set_via_adapter,
)
from gradeflow_engine.exceptions import GradeFlowError
from gradeflow_engine.question_sets.model import QuestionSet

from gradeflow_backend.repositories.assessments import AssessmentRepository
from gradeflow_backend.schemas.question_sets import (
    ExportQuestionSetRequest,
    ExportQuestionSetResponse,
    ImportQuestionSetRequest,
    InferQuestionSetRequest,
    LoadQuestionSetRequest,
    ParseSubmissionsRequest,
    ParseSubmissionsResponse,
    QuestionSetResponse,
    SetQuestionSetByModelRequest,
)
from gradeflow_backend.services.base import BaseService
from gradeflow_backend.services.exceptions import BadRequestError
from gradeflow_backend.services.submissions import derive_raw_submissions
from gradeflow_backend.utils.filenames import make_safe_export_basename
from gradeflow_backend.utils.io import blob_from_str, source_from_data
from gradeflow_backend.utils.loaders import load_question_set
from gradeflow_backend.utils.resolvers import resolve_or_require
from gradeflow_backend.utils.staleness import question_set_status


class QuestionSetService(BaseService):
    def __init__(self, repo: AssessmentRepository) -> None:
        super().__init__(repo)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_by_model(
        self, assessment_id: str, req: SetQuestionSetByModelRequest
    ) -> QuestionSetResponse:
        self._get_or_404(assessment_id)
        return self._store_and_respond(assessment_id, req.question_set)

    def set_by_data(self, assessment_id: str, req: LoadQuestionSetRequest) -> QuestionSetResponse:
        question_set = load_question_set_from_blob(
            blob_from_str(
                req.data,
                media_type="application/octet-stream",
                ext=req.serializer.format,
            ),
            serializer_name=req.serializer.format,
            serializer_kwargs=req.serializer.model_dump(exclude={"format"}),
        )
        return self._store_and_respond(assessment_id, question_set)

    def set_by_adapter(
        self, assessment_id: str, req: ImportQuestionSetRequest
    ) -> QuestionSetResponse:
        question_set = load_question_set_via_adapter(
            source_from_data(req.data),
            adapter_name=req.adapter.name,
            adapter_kwargs=req.adapter.model_dump(exclude={"name"}),
        )
        return self._store_and_respond(assessment_id, question_set)

    def get(self, assessment_id: str) -> QuestionSetResponse:
        a = self._get_or_404(assessment_id)
        return QuestionSetResponse(
            question_set=load_question_set(a),
            status=question_set_status(a),
        )

    def export(
        self, assessment_id: str, req: ExportQuestionSetRequest
    ) -> ExportQuestionSetResponse:
        a = self._get_or_404(assessment_id)
        question_set = load_question_set(a)
        blob = dump_question_set_to_blob(
            question_set,
            serializer_name=req.serializer.format,
            serializer_kwargs=req.serializer.model_dump(exclude={"format"}),
        )
        safe_name = make_safe_export_basename(a.name)
        return ExportQuestionSetResponse(
            filename=f"{safe_name}-questions.{blob.extension}",
            data=blob.data,
            extension=blob.extension,
            media_type=blob.media_type,
        )

    def delete(self, assessment_id: str) -> None:
        self._get_or_404(assessment_id)
        self.repo.set_question_set_yaml(assessment_id, None)

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

    def _store_and_respond(
        self, assessment_id: str, question_set: QuestionSet
    ) -> QuestionSetResponse:
        blob = dump_question_set_to_blob(question_set, serializer_name="yaml")
        self.repo.set_question_set_yaml(assessment_id, blob.data.decode("utf-8"))
        return QuestionSetResponse(
            question_set=question_set,
            status=question_set_status(self._get_or_404(assessment_id)),
        )
