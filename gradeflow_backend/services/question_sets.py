from gradeflow_engine.core import (
    dump_question_set_to_blob,
    load_question_set_from_blob,
    load_question_set_via_adapter,
)
from gradeflow_engine.question_sets.model import QuestionSet
from gradeflow_engine.submissions.models import RawSubmission
from sqlalchemy.exc import NoResultFound

from gradeflow_backend.repositories.assessments import AssessmentRepository
from gradeflow_backend.schemas.question_sets import (
    ImportQuestionSetRequest,
    InferQuestionSetRequest,
    LoadQuestionSetRequest,
    ParseSubmissionsRequest,
    ParseSubmissionsResponse,
    QuestionSetResponse,
    SetQuestionSetByModelRequest,
)
from gradeflow_backend.services.exceptions import BadRequestError, NotFoundError
from gradeflow_backend.services.submissions import derive_raw_submissions
from gradeflow_backend.utils.io import blob_from_str, source_from_data


class QuestionSetService:
    def __init__(self, repo: AssessmentRepository) -> None:
        self.repo = repo

    def set_by_model(
        self, assessment_id: str, req: SetQuestionSetByModelRequest
    ) -> QuestionSetResponse:
        try:
            blob = dump_question_set_to_blob(req.question_set, serializer_name="yaml")
            self.repo.set_question_set_yaml(assessment_id, blob.data.decode("utf-8"))
        except NoResultFound as e:
            raise NotFoundError("Assessment not found") from e
        return QuestionSetResponse(question_set=req.question_set)

    def set_by_data(self, assessment_id: str, req: LoadQuestionSetRequest) -> QuestionSetResponse:
        # Do not hardcode media types; let the engine serializer handle parsing by format
        blob_in = blob_from_str(
            req.data,
            media_type="application/octet-stream",
            ext=req.serializer.format,
        )
        qset = load_question_set_from_blob(
            blob_in,
            serializer_name=req.serializer.format,
            serializer_kwargs=req.serializer.model_dump(exclude={"format"}),
        )
        try:
            blob_out = dump_question_set_to_blob(qset, serializer_name="yaml")
            self.repo.set_question_set_yaml(assessment_id, blob_out.data.decode("utf-8"))
        except NoResultFound as e:
            raise NotFoundError("Assessment not found") from e
        return QuestionSetResponse(question_set=qset)

    def set_by_adapter(
        self, assessment_id: str, req: ImportQuestionSetRequest
    ) -> QuestionSetResponse:
        src = source_from_data(req.data)
        qset = load_question_set_via_adapter(
            src,
            adapter_name=req.adapter.name,
            adapter_kwargs=req.adapter.model_dump(exclude={"name"}),
        )
        try:
            blob_out = dump_question_set_to_blob(qset, serializer_name="yaml")
            self.repo.set_question_set_yaml(assessment_id, blob_out.data.decode("utf-8"))
        except NoResultFound as e:
            raise NotFoundError("Assessment not found") from e
        return QuestionSetResponse(question_set=qset)

    def get(self, assessment_id: str) -> QuestionSetResponse:
        try:
            data = self.repo.get_question_set_yaml(assessment_id)
        except NoResultFound as e:
            raise NotFoundError("Assessment not found") from e
        if not data:
            raise NotFoundError("Question set not set")
        blob = blob_from_str(data, media_type="application/yaml", ext="yaml")
        qset = load_question_set_from_blob(blob, serializer_name="yaml")
        return QuestionSetResponse(question_set=qset)

    def delete(self, assessment_id: str) -> None:
        try:
            self.repo.set_question_set_yaml(assessment_id, None)
        except NoResultFound as e:
            raise NotFoundError("Assessment not found") from e

    def infer(self, assessment_id: str, req: InferQuestionSetRequest) -> QuestionSetResponse:
        try:
            a = self.repo.get(assessment_id)
        except NoResultFound as e:
            raise NotFoundError("Assessment not found") from e

        raw_subs: list[RawSubmission]
        if req.use_stored_submissions:
            raw_subs = derive_raw_submissions(a)
        else:
            if not req.raw_submissions:
                raise BadRequestError(
                    "raw_submissions must be provided when use_stored_submissions=false"
                )
            raw_subs = req.raw_submissions

        qset = QuestionSet.infer(
            raw_subs,
            choice_delimiter=req.choice_delimiter,
            choice_option_limit=req.choice_option_limit,
            multi_value_delimiter=req.multi_value_delimiter,
        )
        if req.commit:
            blob_out = dump_question_set_to_blob(qset, serializer_name="yaml")
            self.repo.set_question_set_yaml(assessment_id, blob_out.data.decode("utf-8"))
        return QuestionSetResponse(question_set=qset)

    def parse(self, assessment_id: str, req: ParseSubmissionsRequest) -> ParseSubmissionsResponse:
        try:
            a = self.repo.get(assessment_id)
        except NoResultFound as e:
            raise NotFoundError("Assessment not found") from e

        if req.use_stored_question_set:
            data = a.question_set_yaml
            if not data:
                raise NotFoundError("Question set not set")
            blob = blob_from_str(data, media_type="application/yaml", ext="yaml")
            qset = load_question_set_from_blob(blob, serializer_name="yaml")
        else:
            if req.question_set is None:
                raise BadRequestError(
                    "question_set must be provided when use_stored_question_set=false"
                )
            qset = req.question_set

        if req.use_stored_submissions:
            raw_subs = derive_raw_submissions(a)
        else:
            if req.raw_submissions is None:
                raise BadRequestError(
                    "raw_submissions must be provided when use_stored_submissions=false"
                )
            raw_subs = req.raw_submissions

        try:
            submissions = qset.parse(raw_subs)
        except ValueError as e:
            raise BadRequestError(f"Failed to parse submissions: {e}") from e
        return ParseSubmissionsResponse(submissions=submissions)
