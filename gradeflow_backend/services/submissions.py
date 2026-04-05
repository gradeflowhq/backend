import csv
from io import StringIO

import yaml
from gradeflow_engine.core import load_raw_submissions_via_adapter
from gradeflow_engine.submissions.models import RawSubmission

from gradeflow_backend.models.assessment import Assessment
from gradeflow_backend.repositories.assessments import AssessmentRepository
from gradeflow_backend.schemas.submissions import (
    SourceDataResponse,
    SubmissionsImportConfig,
    SubmissionsResponse,
    UploadSourceDataRequest,
)
from gradeflow_backend.services.base import BaseService
from gradeflow_backend.services.exceptions import NotFoundError
from gradeflow_backend.utils.io import source_from_data


def derive_raw_submissions(assessment: Assessment) -> list[RawSubmission]:
    """Re-derive raw submissions from stored source_data + submissions_config_yaml."""
    if not assessment.source_data:
        raise NotFoundError("No source data uploaded. Upload source data first.")
    config = SubmissionsImportConfig.model_validate(
        yaml.safe_load(assessment.submissions_config_yaml)
        if assessment.submissions_config_yaml
        else {}
    )
    adapter_kwargs: dict[str, object] = {
        "format": "csv",
        "student_id_column": assessment.source_student_id_column or "student_id",
    }
    if config.answer_columns is not None:
        adapter_kwargs["answer_columns"] = config.answer_columns
    if config.point_columns is not None:
        adapter_kwargs["point_columns"] = config.point_columns
    return load_raw_submissions_via_adapter(
        source_from_data(assessment.source_data),
        adapter_name="csv",
        adapter_kwargs=adapter_kwargs,
    )


class SubmissionsService(BaseService):
    def __init__(self, repo: AssessmentRepository) -> None:
        super().__init__(repo)

    def _parse_source_preview(
        self, data: str, student_id_column: str | None = None
    ) -> SourceDataResponse:
        all_rows = [row for row in csv.reader(StringIO(data)) if any(cell.strip() for cell in row)]
        return SourceDataResponse(
            headers=all_rows[0] if all_rows else [],
            rows=all_rows[1:] if len(all_rows) > 1 else [],
            total_rows=max(0, len(all_rows) - 1),
            student_id_column=student_id_column,
        )

    def _submissions_response(self, a: Assessment) -> SubmissionsResponse:
        return SubmissionsResponse(
            raw_submissions=derive_raw_submissions(a) if a.source_data else [],
            updated_at=a.source_updated_at,
        )

    def upload_source_data(
        self, assessment_id: str, req: UploadSourceDataRequest
    ) -> SourceDataResponse:
        self._get_or_404(assessment_id)
        self.repo.set_source(assessment_id, req.data, req.student_id_column)
        return self._parse_source_preview(req.data, req.student_id_column)

    def get_source_data(self, assessment_id: str) -> SourceDataResponse:
        a = self._get_or_404(assessment_id)
        if not a.source_data:
            raise NotFoundError("No source data uploaded")
        return self._parse_source_preview(a.source_data, a.source_student_id_column)

    def save_import_config(
        self, assessment_id: str, config: SubmissionsImportConfig
    ) -> SubmissionsImportConfig:
        self._get_or_404(assessment_id)
        self.repo.set_submissions_config_yaml(assessment_id, yaml.safe_dump(config.model_dump()))
        return config

    def get_import_config(self, assessment_id: str) -> SubmissionsImportConfig:
        a = self._get_or_404(assessment_id)
        return SubmissionsImportConfig.model_validate(
            yaml.safe_load(a.submissions_config_yaml) if a.submissions_config_yaml else {}
        )

    def get(self, assessment_id: str) -> SubmissionsResponse:
        return self._submissions_response(self._get_or_404(assessment_id))

    def delete(self, assessment_id: str) -> None:
        self._get_or_404(assessment_id)
        self.repo.set_source(assessment_id, None, None)
        self.repo.set_submissions_config_yaml(assessment_id, None)
