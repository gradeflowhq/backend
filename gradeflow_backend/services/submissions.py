import csv
from io import StringIO

import yaml
from gradeflow_engine.core import load_raw_submissions_via_adapter
from gradeflow_engine.submissions.models import RawSubmission
from sqlalchemy.exc import NoResultFound

from gradeflow_backend.models.assessment import Assessment
from gradeflow_backend.repositories.assessments import AssessmentRepository
from gradeflow_backend.schemas.submissions import (
    SourceDataResponse,
    SubmissionsImportConfig,
    SubmissionsResponse,
    UploadSourceDataRequest,
)
from gradeflow_backend.services.exceptions import NotFoundError
from gradeflow_backend.utils.io import source_from_data


def derive_raw_submissions(assessment: Assessment) -> list[RawSubmission]:
    """Re-derive raw submissions from stored source_data + submissions_config_yaml."""
    if not assessment.source_data:
        raise NotFoundError("No source data uploaded. Upload source data first.")
    config_data = (
        yaml.safe_load(assessment.submissions_config_yaml)
        if assessment.submissions_config_yaml
        else None
    )
    config = SubmissionsImportConfig.model_validate(config_data or {})
    src = source_from_data(assessment.source_data)
    adapter_kwargs: dict[str, object] = {
        "format": "csv",
        "student_id_column": assessment.source_student_id_column or "student_id",
    }
    if config.answer_columns is not None:
        adapter_kwargs["answer_columns"] = config.answer_columns
    if config.point_columns is not None:
        adapter_kwargs["point_columns"] = config.point_columns
    return load_raw_submissions_via_adapter(src, adapter_name="csv", adapter_kwargs=adapter_kwargs)


class SubmissionsService:
    def __init__(self, repo: AssessmentRepository) -> None:
        self.repo = repo

    def upload_source_data(
        self, assessment_id: str, req: UploadSourceDataRequest
    ) -> SourceDataResponse:
        try:
            self.repo.set_source(assessment_id, req.data, req.student_id_column)
        except NoResultFound as e:
            raise NotFoundError("Assessment not found") from e
        return self._parse_source_preview(req.data, req.student_id_column)

    def get_source_data(self, assessment_id: str) -> SourceDataResponse:
        try:
            data = self.repo.get_source_data(assessment_id)
            student_id_column = self.repo.get_source_student_id_column(assessment_id)
        except NoResultFound as e:
            raise NotFoundError("Assessment not found") from e
        if not data:
            raise NotFoundError("No source data uploaded")
        return self._parse_source_preview(data, student_id_column)

    def _parse_source_preview(
        self, data: str, student_id_column: str | None = None
    ) -> SourceDataResponse:
        reader = csv.reader(StringIO(data))
        all_rows = [row for row in reader if any(cell.strip() for cell in row)]
        headers = all_rows[0] if all_rows else []
        rows = all_rows[1:] if len(all_rows) > 1 else []
        return SourceDataResponse(
            headers=headers,
            rows=rows,
            total_rows=len(all_rows),
            student_id_column=student_id_column,
        )

    def save_import_config(
        self, assessment_id: str, config: SubmissionsImportConfig
    ) -> SubmissionsImportConfig:
        try:
            self.repo.set_submissions_config_yaml(
                assessment_id, yaml.safe_dump(config.model_dump())
            )
        except NoResultFound as e:
            raise NotFoundError("Assessment not found") from e
        return config

    def get_import_config(self, assessment_id: str) -> SubmissionsImportConfig:
        try:
            config_yaml = self.repo.get_submissions_config_yaml(assessment_id)
        except NoResultFound as e:
            raise NotFoundError("Assessment not found") from e
        if not config_yaml:
            return SubmissionsImportConfig()
        data = yaml.safe_load(config_yaml) or {}
        return SubmissionsImportConfig.model_validate(data)

    def set_by_adapter(self, assessment_id: str) -> SubmissionsResponse:
        try:
            a = self.repo.get(assessment_id)
        except NoResultFound as e:
            raise NotFoundError("Assessment not found") from e
        raw = derive_raw_submissions(a)
        return SubmissionsResponse(raw_submissions=raw)

    def get(self, assessment_id: str) -> SubmissionsResponse:
        try:
            a = self.repo.get(assessment_id)
        except NoResultFound as e:
            raise NotFoundError("Assessment not found") from e
        if not a.source_data:
            return SubmissionsResponse(raw_submissions=[])
        raw = derive_raw_submissions(a)
        return SubmissionsResponse(raw_submissions=raw)

    def delete(self, assessment_id: str) -> None:
        try:
            self.repo.set_source(assessment_id, None, None)
            self.repo.set_submissions_config_yaml(assessment_id, None)
        except NoResultFound as e:
            raise NotFoundError("Assessment not found") from e
