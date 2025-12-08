import yaml
from gradeflow_engine.core import (
    load_question_set_from_blob,
    load_rubric_from_blob,
    load_rubric_via_adapter,
)
from sqlalchemy.exc import NoResultFound

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
from gradeflow_backend.services.exceptions import BadRequestError, NotFoundError
from gradeflow_backend.utils.engine import model_dump_minimal
from gradeflow_backend.utils.io import blob_from_str, source_from_data


class RubricService:
    def __init__(self, repo: AssessmentRepository) -> None:
        self.repo = repo

    def set_by_model(self, assessment_id: str, req: SetRubricByModelRequest) -> RubricResponse:
        try:
            self.repo.set_rubric_yaml(assessment_id, yaml.safe_dump(model_dump_minimal(req.rubric)))
        except NoResultFound as e:
            raise NotFoundError("Assessment not found") from e
        return RubricResponse(rubric=req.rubric)

    def set_by_data(self, assessment_id: str, req: LoadRubricRequest) -> RubricResponse:
        blob_in = blob_from_str(
            req.data,
            media_type="application/octet-stream",
            ext=req.serializer.format,
        )
        rubric = load_rubric_from_blob(
            blob_in,
            serializer_name=req.serializer.format,
            serializer_kwargs=req.serializer.model_dump(exclude={"format"}),
        )
        try:
            self.repo.set_rubric_yaml(assessment_id, yaml.safe_dump(model_dump_minimal(rubric)))
        except NoResultFound as e:
            raise NotFoundError("Assessment not found") from e
        return RubricResponse(rubric=rubric)

    def set_by_adapter(self, assessment_id: str, req: ImportRubricRequest) -> RubricResponse:
        src = source_from_data(req.data)
        rubric = load_rubric_via_adapter(
            src,
            adapter_name=req.adapter.name,
            adapter_kwargs=req.adapter.model_dump(exclude={"name"}),
        )
        try:
            self.repo.set_rubric_yaml(assessment_id, yaml.safe_dump(model_dump_minimal(rubric)))
        except NoResultFound as e:
            raise NotFoundError("Assessment not found") from e
        return RubricResponse(rubric=rubric)

    def get(self, assessment_id: str) -> RubricResponse:
        try:
            data = self.repo.get_rubric_yaml(assessment_id)
        except NoResultFound as e:
            raise NotFoundError("Assessment not found") from e
        if not data:
            raise NotFoundError("Rubric not set")
        blob = blob_from_str(data, media_type="application/yaml", ext="yaml")
        rubric = load_rubric_from_blob(blob, serializer_name="yaml")
        return RubricResponse(rubric=rubric)

    def delete(self, assessment_id: str) -> None:
        try:
            self.repo.set_rubric_yaml(assessment_id, None)
        except NoResultFound as e:
            raise NotFoundError("Assessment not found") from e

    def validate(self, assessment_id: str, req: ValidateRubricRequest) -> ValidateRubricResponse:
        try:
            a = self.repo.get(assessment_id)
        except NoResultFound as e:
            raise NotFoundError("Assessment not found") from e

        if req.use_stored_rubric:
            data = a.rubric_yaml
            if not data:
                raise NotFoundError("Rubric not set")
            rubric_blob = blob_from_str(data, media_type="application/yaml", ext="yaml")
            rubric = load_rubric_from_blob(rubric_blob, serializer_name="yaml")
        else:
            if req.rubric is None:
                raise BadRequestError("rubric must be provided when use_stored_rubric=false")
            rubric = req.rubric

        if req.use_stored_question_set:
            qset_data = a.question_set_yaml
            if not qset_data:
                raise NotFoundError("Question set not set")
            qset_blob = blob_from_str(qset_data, media_type="application/yaml", ext="yaml")
            qset = load_question_set_from_blob(qset_blob, serializer_name="yaml")
        else:
            if req.question_set is None:
                raise BadRequestError(
                    "question_set must be provided when use_stored_question_set=false"
                )
            qset = req.question_set

        errors = rubric.validate_rubric(qset)
        return ValidateRubricResponse(errors=errors)

    def coverage(self, assessment_id: str, req: CoverageRequest) -> CoverageResponse:
        try:
            a = self.repo.get(assessment_id)
        except NoResultFound as e:
            raise NotFoundError("Assessment not found") from e

        if req.use_stored_rubric:
            data = a.rubric_yaml
            if not data:
                raise NotFoundError("Rubric not set")
            rubric_blob = blob_from_str(data, media_type="application/yaml", ext="yaml")
            rubric = load_rubric_from_blob(rubric_blob, serializer_name="yaml")
        else:
            if req.rubric is None:
                raise BadRequestError("rubric must be provided when use_stored_rubric=false")
            rubric = req.rubric

        if req.use_stored_question_set:
            qset_data = a.question_set_yaml
            if not qset_data:
                raise NotFoundError("Question set not set")
            qset_blob = blob_from_str(qset_data, media_type="application/yaml", ext="yaml")
            qset = load_question_set_from_blob(qset_blob, serializer_name="yaml")
        else:
            if req.question_set is None:
                raise BadRequestError(
                    "question_set must be provided when use_stored_question_set=false"
                )
            qset = req.question_set

        cov = rubric.get_coverage(qset)
        return CoverageResponse(coverage=cov)
